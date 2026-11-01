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
    let svg = store
        .add_file(
            b"<svg viewBox='0 0 1280 720'><text x='64' y='80' font-size='36' data-atom-id='atom:p1:title'>Decision</text></svg>",
            "svg",
        )
        .unwrap();
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
            "DROP TABLE run_pages; DROP TABLE runs; DROP TABLE builds; PRAGMA user_version=1;",
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
        2
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
            "DROP TABLE run_pages; DROP TABLE runs; DROP TABLE builds; PRAGMA user_version=1;",
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
