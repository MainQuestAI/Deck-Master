use deck::error::Error;
use deck::model::Patch;
use deck::{ops, store};
use serde_json::{Value, json};
use std::path::Path;
use std::sync::{Arc, Barrier};

fn patch(value: Value) -> Patch {
    serde_json::from_value(value).unwrap()
}

fn two_pages(path: &Path) -> i64 {
    ops::new(path, "合成作品".into()).unwrap();
    ops::put(
        path,
        1,
        patch(json!({"order":["p1","p2"], "pages":[
            {"id":"p1","content":{"title":"起点"}}, {"id":"p2","notes":"原讲稿"}
        ]})),
    )
    .unwrap()
    .version
}

#[test]
fn incomplete_deck_can_add_reorder_delete_and_export() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    let base = two_pages(path);
    let reordered = ops::put(path, base, patch(json!({"order":["p2","p1"]}))).unwrap();
    assert_eq!(reordered.deck.pages[0].id, "p2");
    let removed = ops::put(
        path,
        reordered.version,
        patch(json!({"order":["p2"],"pages":[{"id":"p1"}]})),
    )
    .unwrap();
    assert_eq!(removed.deck.pages.len(), 1);
    let saved = ops::put(
        path,
        removed.version,
        patch(json!({"pages":[{"id":"p2","todo":["补证据"],"notes":"等待补充"}]})),
    )
    .unwrap();
    let md = ops::export_md(path).unwrap();
    assert!(md.contains("补证据") && md.contains("等待补充"));
    assert_eq!(saved.deck.pages[0].todo, ["补证据"]);
}

#[test]
fn independent_connections_merge_different_pages_and_retry_without_new_version() {
    let temp = tempfile::tempdir().unwrap();
    let base = two_pages(temp.path());
    let barrier = Arc::new(Barrier::new(2));
    let threads: Vec<_> = ["p1", "p2"]
        .into_iter()
        .map(|id| {
            let path = temp.path().to_path_buf();
            let barrier = barrier.clone();
            std::thread::spawn(move || {
                barrier.wait();
                ops::put(
                    &path,
                    base,
                    patch(json!({"pages":[{"id":id,"notes":format!("新讲稿 {id}")}]})),
                )
                .unwrap()
            })
        })
        .collect();
    for thread in threads {
        thread.join().unwrap();
    }
    let current = store::Store::open(temp.path()).unwrap().current().unwrap();
    assert_eq!(current.deck.pages[0].notes, "新讲稿 p1");
    assert_eq!(current.deck.pages[1].notes, "新讲稿 p2");
    let retry = ops::put(
        temp.path(),
        base,
        patch(json!({"pages":[{"id":"p1","notes":"新讲稿 p1"}]})),
    )
    .unwrap();
    assert_eq!(retry.version, current.version);
}

#[test]
fn same_page_conflict_is_atomic_and_reports_current_author_content() {
    let temp = tempfile::tempdir().unwrap();
    let base = two_pages(temp.path());
    let first = ops::put(
        temp.path(),
        base,
        patch(json!({"pages":[{"id":"p1","notes":"先保存"}]})),
    )
    .unwrap();
    let error = ops::put(
        temp.path(),
        base,
        patch(json!({"brief":{"title":"不应写入"},"pages":[{"id":"p1","purpose":"另一处修改"}]})),
    )
    .unwrap_err();
    assert_eq!(error.exit_code(), 5);
    let Error::Conflict(body) = error else {
        panic!("expected conflict")
    };
    let conflicts: Value = serde_json::from_str(&body).unwrap();
    assert_eq!(conflicts[0]["unit"], "pages/p1");
    assert_eq!(conflicts[0]["current"]["notes"], "先保存");
    let current = store::Store::open(temp.path()).unwrap().current().unwrap();
    assert_eq!(current.version, first.version);
    assert_eq!(current.deck.brief.title, "合成作品");
}

#[test]
fn partial_read_roundtrip_keeps_unseen_and_concurrently_changed_pages() {
    let temp = tempfile::tempdir().unwrap();
    let base = two_pages(temp.path());
    let mut partial = ops::get(temp.path(), Some(&["p1".into()])).unwrap();
    assert!(partial["deck"].get("order").is_none());
    assert_eq!(partial["deck"]["pages"].as_array().unwrap().len(), 1);
    partial["deck"]["pages"][0]["notes"] = json!("局部编辑");
    ops::put(
        temp.path(),
        base,
        patch(json!({"pages":[{"id":"p2","notes":"另一作者"}]})),
    )
    .unwrap();
    let saved = ops::put(temp.path(), base, patch(partial["deck"].take())).unwrap();
    assert_eq!(saved.deck.pages.len(), 2);
    assert_eq!(saved.deck.pages[1].notes, "另一作者");
}

#[test]
fn deleting_changed_page_and_divergent_order_conflict() {
    let temp = tempfile::tempdir().unwrap();
    let base = two_pages(temp.path());
    ops::put(
        temp.path(),
        base,
        patch(json!({"pages":[{"id":"p2","notes":"已更新"}]})),
    )
    .unwrap();
    assert_eq!(
        ops::put(
            temp.path(),
            base,
            patch(json!({"order":["p1"],"pages":[{"id":"p2"}]}))
        )
        .unwrap_err()
        .exit_code(),
        5
    );
    let current = store::Store::open(temp.path()).unwrap().current().unwrap();
    ops::put(
        temp.path(),
        current.version,
        patch(json!({"order":["p2","p1"]})),
    )
    .unwrap();
    assert_eq!(
        ops::put(
            temp.path(),
            current.version,
            patch(json!({"order":["p1"],"pages":[{"id":"p2"}]}))
        )
        .unwrap_err()
        .exit_code(),
        5
    );
}

#[test]
fn edit_of_deleted_page_conflicts_but_unchanged_snapshot_can_be_replayed() {
    let temp = tempfile::tempdir().unwrap();
    let base = two_pages(temp.path());
    let snapshot = ops::get(temp.path(), None).unwrap();
    let deleted = ops::put(
        temp.path(),
        base,
        patch(json!({"order":["p1"],"pages":[{"id":"p2"}]})),
    )
    .unwrap();
    assert_eq!(
        ops::put(
            temp.path(),
            base,
            patch(json!({"pages":[{"id":"p2","notes":"晚到编辑"}]}))
        )
        .unwrap_err()
        .exit_code(),
        5
    );
    assert_eq!(
        ops::put(temp.path(), base, patch(snapshot["deck"].clone()))
            .unwrap()
            .version,
        deleted.version
    );
}

#[test]
fn restore_appends_and_keeps_history_and_files() {
    let temp = tempfile::tempdir().unwrap();
    let base = two_pages(temp.path());
    let store = store::Store::open(temp.path()).unwrap();
    let file = store.add_file(b"synthetic original", "txt").unwrap();
    let restored = ops::restore(temp.path(), 1).unwrap();
    assert!(restored.version > base);
    assert!(restored.deck.pages.is_empty());
    assert_eq!(store::load(&store.connection, base).unwrap().pages.len(), 2);
    assert_eq!(store.history().unwrap().len(), 3);
    assert!(store.file(&file).unwrap().is_file());
}

#[test]
fn ids_are_repaired_including_nested_bullets_and_table_references_and_retry_is_safe() {
    let temp = tempfile::tempdir().unwrap();
    ops::new(temp.path(), String::new()).unwrap();
    let value = json!({"order":["p1"],"pages":[{"id":"p1","content":{
        "body_blocks":[
            {"type":"paragraph","id":"a1","text":"正文"},
            {"type":"bullets","id":"a1","items":[{"text":"父","children":[{"text":"子"}]}]},
            {"type":"table","columns":[{"id":"duplicate","label":"甲"},{"id":"duplicate","label":"乙"}],"rows":[{"cells":[{"column_id":"duplicate","display_text":"1"},{"column_id":"duplicate","display_text":"2"}]}]}
        ],"labels":[{"text":"标签"}],"footnotes":[{"text":"注"}],"callouts":[{"text":"提示","tone":"emphasis"}]
    }}]});
    let saved = ops::put(temp.path(), 1, patch(value.clone())).unwrap();
    let content = serde_json::to_value(&saved.deck.pages[0].content).unwrap();
    let table = &content["body_blocks"][2];
    assert_ne!(table["columns"][0]["id"], table["columns"][1]["id"]);
    assert_eq!(
        table["columns"][1]["id"],
        table["rows"][0]["cells"][1]["column_id"]
    );
    assert!(ops::export_md(temp.path()).unwrap().contains("| 1 | 2 |"));
    assert_eq!(
        ops::put(temp.path(), 1, patch(value)).unwrap().version,
        saved.version
    );
    let roundtrip = ops::get(temp.path(), None).unwrap();
    assert_eq!(
        ops::put(temp.path(), saved.version, patch(roundtrip["deck"].clone()))
            .unwrap()
            .version,
        saved.version
    );
}

#[test]
fn author_save_never_replaces_material_or_artifact_fields() {
    let temp = tempfile::tempdir().unwrap();
    let base = two_pages(temp.path());
    let mut store = store::Store::open(temp.path()).unwrap();
    let mut current = store.current().unwrap().deck;
    current.pages[0].image = Some(deck::model::Artifact {
        file: "synthetic-image".into(),
        basis: "basis".into(),
    });
    let tx = store.transaction().unwrap();
    store::append(&tx, &current, "test artifact arrival").unwrap();
    tx.commit().unwrap();
    let saved = ops::put(temp.path(), base, patch(json!({"materials":[],"pages":[{"id":"p1","notes":"改讲稿","image":{"file":"overwrite","basis":"old"},"svg":null,"preview":null}]}))).unwrap();
    assert_eq!(
        saved.deck.pages[0].image.as_ref().unwrap().file,
        "synthetic-image"
    );
}

#[test]
fn older_database_migrates_without_losing_versions_and_newer_database_is_refused() {
    let temp = tempfile::tempdir().unwrap();
    two_pages(temp.path());
    let store = store::Store::open(temp.path()).unwrap();
    store
        .connection
        .execute_batch(
            "DROP TABLE run_pages; DROP TABLE runs; DROP TABLE builds; PRAGMA user_version=0;",
        )
        .unwrap();
    drop(store);
    let store = store::Store::open(temp.path()).unwrap();
    assert_eq!(store.current().unwrap().deck.pages.len(), 2);
    assert_eq!(
        store
            .connection
            .pragma_query_value(None, "user_version", |r| r.get::<_, i64>(0))
            .unwrap(),
        store::FORMAT_VERSION
    );
    store
        .connection
        .pragma_update(None, "user_version", 99)
        .unwrap();
    drop(store);
    assert!(matches!(
        store::Store::open(temp.path()),
        Err(Error::Input(_))
    ));
}

#[test]
fn invalid_patch_does_not_write_and_existing_project_is_never_reinitialized() {
    let temp = tempfile::tempdir().unwrap();
    let base = two_pages(temp.path());
    assert!(ops::new(temp.path(), String::new()).is_err());
    for invalid in [
        json!({"order":["p1","p1"]}),
        json!({"pages":[{"id":"p3"}]}),
        json!({"order":["p3"]}),
        json!({"order":[]}),
        json!({"pages":[{"id":"p1"},{"id":"p1"}]}),
    ] {
        assert_eq!(
            ops::put(temp.path(), base, patch(invalid))
                .unwrap_err()
                .exit_code(),
            2
        );
    }
    assert_eq!(
        store::Store::open(temp.path())
            .unwrap()
            .current()
            .unwrap()
            .version,
        base
    );
}

#[test]
fn current_format_read_does_not_wait_for_or_take_a_write_lock() {
    let temp = tempfile::tempdir().unwrap();
    two_pages(temp.path());
    let mut writer = store::Store::open(temp.path()).unwrap();
    let tx = writer.transaction().unwrap();
    let path = temp.path().to_path_buf();
    let (send, receive) = std::sync::mpsc::channel();
    let reader = std::thread::spawn(move || {
        send.send(ops::get(&path, None)).unwrap();
    });
    let result = receive.recv_timeout(std::time::Duration::from_secs(2));
    // Release the writer even on failure, so the regression fails promptly.
    tx.commit().unwrap();
    reader.join().unwrap();
    assert_eq!(
        result.unwrap().unwrap()["deck"]["pages"]
            .as_array()
            .unwrap()
            .len(),
        2
    );
}

#[test]
fn attachment_deduplication_does_not_rewrite_original() {
    let temp = tempfile::tempdir().unwrap();
    ops::new(temp.path(), String::new()).unwrap();
    let store = store::Store::open(temp.path()).unwrap();
    let one = store.add_file(b"same bytes", "txt").unwrap();
    let two = store.add_file(b"same bytes", "txt").unwrap();
    assert_eq!(one, two);
    assert_eq!(
        std::fs::read_dir(store.root.join("files")).unwrap().count(),
        1
    );
    assert_eq!(
        std::fs::read(store.file(&one).unwrap()).unwrap(),
        b"same bytes"
    );
    assert!(store.file("../../outside").is_err());
}

#[test]
fn all_three_way_cases_apply_to_brief_framing_and_style() {
    let temp = tempfile::tempdir().unwrap();
    ops::new(temp.path(), String::new()).unwrap();
    let first = ops::put(temp.path(), 1, patch(json!({"brief":{"title":"甲"}}))).unwrap();
    let next = ops::put(
        temp.path(),
        1,
        patch(json!({"brief":{},"framing":{"thesis":"主张"},"style":{"fonts":["sans-serif"]}})),
    )
    .unwrap();
    assert_eq!(next.deck.brief.title, "甲");
    assert_eq!(next.deck.framing.thesis, "主张");
    assert!(next.version > first.version);
    assert_eq!(
        ops::put(temp.path(), 1, patch(json!({"brief":{"title":"甲"}})))
            .unwrap()
            .version,
        next.version
    );
    assert_eq!(
        ops::put(temp.path(), 1, patch(json!({"style":{"fonts":["serif"]}})))
            .unwrap_err()
            .exit_code(),
        5
    );
    assert_eq!(
        ops::put(
            temp.path(),
            1,
            patch(json!({"framing":{"thesis":"另一主张"}}))
        )
        .unwrap_err()
        .exit_code(),
        5
    );
}
