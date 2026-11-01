use deck::{model::Patch, ops};
use serde_json::json;

#[test]
fn notes_only_patch_preserves_older_content_and_svg_basis() {
    use deck::{
        model::Artifact,
        store::{self, Store},
    };

    let temporary = tempfile::tempdir().unwrap();
    let path = temporary.path();
    ops::new(path, "合成稿".into()).unwrap();
    let patch = serde_json::from_value(json!({
        "order":["p1"], "pages":[{"id":"p1","content":{"title":"原稿"}}]
    }))
    .unwrap();
    ops::put(path, 1, patch).unwrap();
    let mut store = Store::open(path).unwrap();
    let mut snapshot = store.current().unwrap();
    snapshot.deck.pages[0].content.title = "覆盖 535 类".into();
    let basis = ops::basis("svg", &snapshot.deck, &snapshot.deck.pages[0]).unwrap();
    let file = store
        .add_file(b"<svg viewBox='0 0 1280 720'/>", "svg")
        .unwrap();
    snapshot.deck.pages[0].svg = Some(Artifact { file, basis });
    let tx = store.transaction().unwrap();
    let base = store::append(&tx, &snapshot.deck, "older content fixture").unwrap();
    tx.commit().unwrap();
    let patch = serde_json::from_value(json!({"pages":[{"id":"p1","notes":"新讲稿"}]})).unwrap();
    let result = ops::put(path, base, patch).unwrap();
    let page = &result.deck.pages[0];
    assert_eq!(page.content, snapshot.deck.pages[0].content);
    assert_eq!(page.notes, "新讲稿");
    assert_eq!(page.svg, snapshot.deck.pages[0].svg);
    assert_eq!(
        ops::basis("svg", &result.deck, page).unwrap(),
        page.svg.as_ref().unwrap().basis
    );
}

#[test]
fn save_normalizes_spacing_without_changing_notes_or_cell_values() {
    let temporary = tempfile::tempdir().unwrap();
    ops::new(temporary.path(), "合成稿".into()).unwrap();
    let patch: Patch = serde_json::from_value(json!({
        "order":["p1"],
        "pages":[{"id":"p1","notes":"原稿  备注","content":{
            "title":"覆盖535  类标签，连接CDP  、VOC",
            "subtitle":"Windows 11 专业版",
            "body_blocks":[{"type":"table","columns":[{"id":"c1","label":"数量"}],
                "rows":[{"cells":[{"column_id":"c1","value":"535  类","display_text":"535  类"}]}]}]
        }}]
    }))
    .unwrap();
    let result = ops::put(temporary.path(), 1, patch).unwrap();
    let page = &result.deck.pages[0];
    assert_eq!(page.content.title, "覆盖535类标签，连接CDP、VOC");
    assert_eq!(page.content.subtitle, "Windows 11 专业版");
    assert_eq!(page.notes, "原稿  备注");
    let content = serde_json::to_value(&page.content).unwrap();
    let cell = &content["body_blocks"][0]["rows"][0]["cells"][0];
    assert_eq!(cell["value"], "535  类");
    assert_eq!(cell["display_text"], cell["value"]);
}
