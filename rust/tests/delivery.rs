use deck::{
    model::Patch,
    ops,
    store::{self, Store},
};
use serde_json::{Value, json};
use std::path::Path;
use std::process::Command;

fn setup(path: &Path) {
    ops::new(path, "合成技术方案".into()).unwrap();
    let patch: Patch = serde_json::from_value(json!({"order":["p1","p2"],"pages":[{"id":"p1","content":{"title":"Decision"}},{"id":"p2","content":{"title":"Next"}}]})).unwrap();
    ops::put(path, 1, patch).unwrap();
}
fn edit(path: &Path, value: Value) {
    let base = Store::open(path).unwrap().current().unwrap().version;
    ops::put(path, base, serde_json::from_value(value).unwrap()).unwrap();
}
fn png(path: &Path) {
    let python = std::env::var_os("DECK_TOOLS_PYTHON").expect("install this worktree's deck-tools");
    assert!(Command::new(python).args(["-c", "from PIL import Image; import sys; Image.new('RGB',(16,16),'teal').save(sys.argv[1])"]).arg(path).status().unwrap().success());
}
fn start(path: &Path, max: i64) -> i64 {
    ops::run_start(path, "image", &["p1".into()], Some(max)).unwrap()["runs"][0]["id"]
        .as_i64()
        .unwrap()
}
#[test]
fn cancelled_late_result_is_saved_and_manual_adoption_keeps_author_edits() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let image = path.join("result.png");
    png(&image);
    let id = start(path, 2);
    ops::run_call(path, id, "p1", false).unwrap();
    ops::run_cancel(path, id).unwrap();
    assert!(ops::run_call(path, id, "p1", true).is_err());
    edit(path, json!({"pages":[{"id":"p1","notes":"作者新讲稿"}]}));
    let result = ops::run_result(path, id, "p1", &image).unwrap();
    assert_eq!(result["adopted"], false);
    let store = Store::open(path).unwrap();
    assert!(
        store
            .file(result["file"].as_str().unwrap())
            .unwrap()
            .is_file()
    );
    assert!(store.current().unwrap().deck.pages[0].image.is_none());
    assert_eq!(result["run"]["runs"][0]["pages"][0]["status"], "unadopted");
    ops::run_adopt(path, id, "p1").unwrap();
    let page = &Store::open(path).unwrap().current().unwrap().deck.pages[0];
    assert!(page.image.is_some());
    assert_eq!(page.notes, "作者新讲稿");
}
#[test]
fn changed_basis_is_not_adopted_but_notes_alone_do_not_stale_images() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let image = path.join("result.png");
    png(&image);
    let id = start(path, 2);
    ops::run_call(path, id, "p1", false).unwrap();
    edit(path, json!({"pages":[{"id":"p1","layout":"新布局"}]}));
    assert_eq!(
        ops::run_result(path, id, "p1", &image).unwrap()["adopted"],
        false
    );
    assert!(
        Store::open(path).unwrap().current().unwrap().deck.pages[0]
            .image
            .is_none()
    );
    ops::run_cancel(path, id).unwrap();
    let id = start(path, 2);
    ops::run_call(path, id, "p1", false).unwrap();
    edit(path, json!({"pages":[{"id":"p1","notes":"只改讲稿"}]}));
    assert_eq!(
        ops::run_result(path, id, "p1", &image).unwrap()["adopted"],
        true
    );
    let version = Store::open(path).unwrap().current().unwrap().version;
    ops::run_result(path, id, "p1", &image).unwrap();
    assert_eq!(
        Store::open(path).unwrap().current().unwrap().version,
        version
    );
    assert_eq!(
        ops::run_show(path, Some(id)).unwrap()["runs"][0]["status"],
        "done"
    );
}
#[test]
fn unknown_call_requires_explicit_retry_and_cannot_exceed_limit() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let id = start(path, 2);
    assert!(ops::run_start(path, "image", &["p2".into()], None).is_err());
    ops::run_call(path, id, "p1", false).unwrap();
    assert!(ops::run_call(path, id, "p1", false).is_err());
    assert_eq!(
        ops::run_show(path, Some(id)).unwrap()["runs"][0]["calls_used"],
        1
    );
    ops::run_call(path, id, "p1", true).unwrap();
    assert!(ops::run_call(path, id, "p1", true).is_err());
    assert_eq!(
        ops::run_show(path, Some(id)).unwrap()["runs"][0]["calls_used"],
        2
    );
}
#[test]
fn asset_bytes_are_attached_to_host_task_without_using_ids_as_paths() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let image = path.join("logo.png");
    png(&image);
    let asset = ops::asset_add(path, "../logo", &image).unwrap();
    let id = start(path, 2);
    let task = ops::run_show(path, Some(id)).unwrap();
    let directory = Path::new(task["runs"][0]["pages"][0]["work"].as_str().unwrap());
    let attachments: Value =
        serde_json::from_slice(&std::fs::read(directory.join("attachments.json")).unwrap())
            .unwrap();
    assert_eq!(attachments[0]["id"], "../logo");
    assert_eq!(
        std::fs::read(directory.join(attachments[0]["file"].as_str().unwrap())).unwrap(),
        std::fs::read(&image).unwrap()
    );
    assert_eq!(
        asset["asset"]["file"],
        Store::open(path)
            .unwrap()
            .current()
            .unwrap()
            .deck
            .style
            .assets[0]
            .file
    );
}
#[test]
fn failed_svg_and_corrupt_bitmap_publish_no_artifact() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let broken = path.join("broken.svg");
    std::fs::write(&broken, "<svg viewBox='0 0 100 100'><script/></svg>").unwrap();
    let run = ops::run_start(path, "svg", &["p1".into()], None).unwrap();
    let id = run["runs"][0]["id"].as_i64().unwrap();
    assert_eq!(
        ops::run_result(path, id, "p1", &broken)
            .unwrap_err()
            .exit_code(),
        4
    );
    assert!(
        Store::open(path).unwrap().current().unwrap().deck.pages[0]
            .svg
            .is_none()
    );
    let bad = path.join("broken.png");
    std::fs::write(&bad, b"not a bitmap").unwrap();
    let id = start(path, 1);
    ops::run_call(path, id, "p1", false).unwrap();
    assert!(ops::run_result(path, id, "p1", &bad).is_err());
    assert!(
        Store::open(path).unwrap().current().unwrap().deck.pages[0]
            .image
            .is_none()
    );
}
#[test]
fn build_retains_notes_reports_missing_and_export_compares_inputs_after_restore() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let mut store = Store::open(path).unwrap();
    let mut snapshot = store.current().unwrap();
    let font = Command::new("fc-match")
        .args(["-f", "%{family}", "sans-serif"])
        .output()
        .unwrap();
    assert!(font.status.success());
    let families = String::from_utf8(font.stdout).unwrap();
    let family = families.split(',').next().unwrap().trim();
    let svg_text = format!(
        "<svg viewBox='0 0 1280 720'><text x='64' y='80' font-size='36' font-family=\"{family}\" data-atom-id='atom:p1:title'>Decision</text></svg>"
    );
    let svg = store.add_file(svg_text.as_bytes(), "svg").unwrap();
    let basis = ops::basis("svg", &snapshot.deck, &snapshot.deck.pages[0]).unwrap();
    snapshot.deck.pages[0].svg = Some(deck::model::Artifact { file: svg, basis });
    snapshot.deck.pages[0].notes = "Speaker notes\n\nLast line\n".into();
    let tx = store.transaction().unwrap();
    let baseline = store::append(&tx, &snapshot.deck, "synthetic compiler fixture").unwrap();
    tx.commit().unwrap();
    let build = ops::build(path).unwrap();
    assert_eq!(build["missing_pages"], json!(["p2"]));
    assert!(Path::new(build["path"].as_str().unwrap()).is_file());
    assert_eq!(ops::export_pptx(path).unwrap()["input_changed"], false);
    edit(
        path,
        json!({"pages":[{"id":"p1","content":{"title":"Changed"}}]}),
    );
    let exported = ops::export_pptx(path).unwrap();
    assert_eq!(exported["input_changed"], false);
    assert_eq!(exported["stale_pages"], json!(["p1"]));
    edit(path, json!({"pages":[{"id":"p1","notes":"Changed notes"}]}));
    assert_eq!(ops::export_pptx(path).unwrap()["input_changed"], true);
    ops::restore(path, baseline).unwrap();
    assert_eq!(ops::export_pptx(path).unwrap()["input_changed"], false);
}
#[test]
fn version_one_database_keeps_versions_files_and_gains_delivery_tables() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let store = Store::open(path).unwrap();
    let file = store.add_file(b"retained", "txt").unwrap();
    let before = store.current().unwrap();
    store
        .connection
        .execute_batch(
            "DROP TABLE reviews; DROP TABLE run_pages; DROP TABLE runs; DROP TABLE builds; PRAGMA user_version=1;",
        )
        .unwrap();
    drop(store);
    let store = Store::open(path).unwrap();
    assert_eq!(store.current().unwrap().version, before.version);
    assert_eq!(store.current().unwrap().deck, before.deck);
    assert_eq!(
        std::fs::read(store.file(&file).unwrap()).unwrap(),
        b"retained"
    );
    assert_eq!(
        store
            .connection
            .pragma_query_value(None, "user_version", |r| r.get::<_, i64>(0))
            .unwrap(),
        3
    );
    start(path, 1);
}

#[test]
fn concurrent_open_migrates_the_old_database_only_once() {
    let temp = tempfile::tempdir().unwrap();
    setup(temp.path());
    let store = Store::open(temp.path()).unwrap();
    store
        .connection
        .execute_batch(
            "DROP TABLE reviews; DROP TABLE run_pages; DROP TABLE runs; DROP TABLE builds; PRAGMA user_version=1;",
        )
        .unwrap();
    drop(store);
    let barrier = std::sync::Arc::new(std::sync::Barrier::new(2));
    let threads: Vec<_> = (0..2)
        .map(|_| {
            let path = temp.path().to_path_buf();
            let barrier = barrier.clone();
            std::thread::spawn(move || {
                barrier.wait();
                Store::open(&path)
                    .unwrap()
                    .current()
                    .unwrap()
                    .deck
                    .pages
                    .len()
            })
        })
        .collect();
    for thread in threads {
        assert_eq!(thread.join().unwrap(), 2);
    }
}

#[test]
fn page_three_redo_and_notes_only_edits_preserve_other_pages_and_existing_build() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成三页方案".into()).unwrap();
    ops::put(
        path,
        1,
        serde_json::from_value(json!({
            "order":["p1","p2","p3"], "pages":[
                {"id":"p1","content":{"title":"Decision"}},
                {"id":"p2","content":{"title":"Decision"}},
                {"id":"p3","content":{"title":"Decision"}}
            ]
        }))
        .unwrap(),
    )
    .unwrap();
    let image = path.join("new.png");
    png(&image);
    let mut store = Store::open(path).unwrap();
    let mut snapshot = store.current().unwrap();
    let old_image = store
        .add_file(&std::fs::read(&image).unwrap(), "png")
        .unwrap();
    let preview = store
        .add_file(&std::fs::read(&image).unwrap(), "png")
        .unwrap();
    let font = Command::new("fc-match")
        .args(["-f", "%{family}", "sans-serif"])
        .output()
        .unwrap();
    assert!(font.status.success());
    let families = String::from_utf8(font.stdout).unwrap();
    let family = families.split(',').next().unwrap().trim();
    for index in 0..3 {
        let basis = ops::basis("image", &snapshot.deck, &snapshot.deck.pages[index]).unwrap();
        snapshot.deck.pages[index].image = Some(deck::model::Artifact {
            file: old_image.clone(),
            basis,
        });
        let page = &snapshot.deck.pages[index];
        let svg = format!(
            "<svg viewBox='0 0 1280 720'><text x='64' y='80' font-size='36' font-family=\"{family}\" data-atom-id='atom:{}:title'>Decision</text></svg>",
            page.id
        );
        let file = store.add_file(svg.as_bytes(), "svg").unwrap();
        let basis = ops::basis("svg", &snapshot.deck, page).unwrap();
        snapshot.deck.pages[index].svg = Some(deck::model::Artifact { file, basis });
        snapshot.deck.pages[index].preview = Some(preview.clone());
    }
    let tx = store.transaction().unwrap();
    let baseline = store::append(&tx, &snapshot.deck, "synthetic three-page fixture").unwrap();
    tx.commit().unwrap();
    let build = ops::build(path).unwrap();
    let build_bytes = std::fs::read(build["path"].as_str().unwrap()).unwrap();
    let build_rows = || {
        let store = Store::open(path).unwrap();
        let mut query = store.connection.prepare("SELECT id,version_id,input_digest,pptx_file,findings_json,missing_pages,created_at FROM builds ORDER BY id").unwrap();
        query
            .query_map([], |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, i64>(1)?,
                    (2..7)
                        .map(|i| row.get::<_, String>(i).unwrap())
                        .collect::<Vec<_>>(),
                ))
            })
            .unwrap()
            .collect::<std::result::Result<Vec<_>, _>>()
            .unwrap()
    };
    let original_builds = build_rows();
    let original_files: Vec<_> = std::fs::read_dir(path.join(".deck/files"))
        .unwrap()
        .map(|entry| {
            let file = entry.unwrap().path();
            let bytes = std::fs::read(&file).unwrap();
            (file, bytes)
        })
        .collect();
    let python = std::env::var_os("DECK_TOOLS_PYTHON").unwrap();
    assert!(Command::new(python).args(["-c", "from PIL import Image; import sys; Image.new('RGB',(16,16),'navy').save(sys.argv[1])"]).arg(&image).status().unwrap().success());
    let run = ops::run_start(path, "image", &["p3".into()], None).unwrap();
    let id = run["runs"][0]["id"].as_i64().unwrap();
    assert_eq!(run["runs"][0]["pages"].as_array().unwrap().len(), 1);
    assert_eq!(
        Store::open(path).unwrap().current().unwrap().version,
        baseline
    );
    ops::run_call(path, id, "p3", false).unwrap();
    let result = ops::run_result(path, id, "p3", &image).unwrap();
    assert_eq!(result["adopted"], true);
    let after = Store::open(path).unwrap().current().unwrap();
    let mut expected = snapshot.deck.clone();
    expected.pages[2].image.as_mut().unwrap().file = result["file"].as_str().unwrap().into();
    assert_eq!(after.deck, expected);
    assert_eq!(after.version, baseline + 1);
    let exported = ops::export_pptx(path).unwrap();
    assert_eq!(exported["input_changed"], false);
    assert_eq!(exported["missing_pages"], json!([]));
    assert_eq!(exported["stale_pages"], json!(["p3"]));
    assert_eq!(build_rows(), original_builds);
    assert_eq!(
        std::fs::read(exported["path"].as_str().unwrap()).unwrap(),
        build_bytes
    );

    // Isolate a notes-only edit from the intentional stale SVG after image redo.
    let restored = ops::restore(path, baseline).unwrap();
    assert_eq!(ops::export_pptx(path).unwrap()["input_changed"], false);
    let edited = ops::put(
        path,
        restored.version,
        serde_json::from_value(json!({"pages":[{"id":"p3","notes":"只改第三页讲稿"}]})).unwrap(),
    )
    .unwrap();
    let mut expected = snapshot.deck;
    expected.pages[2].notes = "只改第三页讲稿".into();
    assert_eq!(edited.deck, expected);
    let status = ops::export_pptx(path).unwrap();
    assert_eq!(status["input_changed"], true);
    assert_eq!(status["missing_pages"], json!([]));
    assert_eq!(status["stale_pages"], json!([]));
    assert_eq!(
        ops::artifact_status(&edited.deck).unwrap()["stale_images"],
        json!([])
    );
    assert_eq!(build_rows(), original_builds);
    assert_eq!(
        std::fs::read(status["path"].as_str().unwrap()).unwrap(),
        build_bytes
    );
    for (file, bytes) in original_files {
        assert_eq!(std::fs::read(file).unwrap(), bytes);
    }
}
