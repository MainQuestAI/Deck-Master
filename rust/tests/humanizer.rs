use deck::{model::Patch, ops};
use serde_json::json;

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
