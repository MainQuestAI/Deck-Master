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
                "rows":[{"cells":[{"column_id":"c1","value":"535  类，CDP  、VOC","display_text":"535  类，CDP  、VOC"}]}]}]
        }}]
    }))
    .unwrap();
    let result = ops::put(temporary.path(), 1, patch).unwrap();
    let page = &result.deck.pages[0];
    assert_eq!(page.content.title, "覆盖535  类标签，连接CDP、VOC");
    assert_eq!(page.content.subtitle, "Windows 11 专业版");
    assert_eq!(page.notes, "原稿  备注");
    let content = serde_json::to_value(&page.content).unwrap();
    let cell = &content["body_blocks"][0]["rows"][0]["cells"][0];
    assert_eq!(cell["value"], "535  类，CDP  、VOC");
    assert_eq!(cell["display_text"], cell["value"]);
}

#[test]
fn put_keeps_author_spaces_between_digits_and_han() {
    let spaced = json!({
        "order": ["p1"],
        "pages": [{
            "id": "p1",
            "content": {
                "title": "1 数据与身份",
                "body_blocks": [
                    {"type": "paragraph", "text": "模块 2 已覆盖 535 类"},
                    {"type": "table", "columns": [{"label": "6 评估"}], "rows": [
                        {"cells": [{"display_text": "1 数据与身份"}]},
                        {"cells": [{"display_text": "6 评估与持续运营"}]},
                        {"cells": [{"display_text": "阶段\u{3000}3"}]},
                        {"cells": [{"display_text": "1数据与身份"}]}
                    ]}
                ]
            }
        }]
    });
    let mut collapsed = spaced.clone();
    let content = &mut collapsed["pages"][0]["content"];
    content["title"] = json!("1数据与身份");
    content["body_blocks"][0]["text"] = json!("模块2已覆盖535类");
    content["body_blocks"][1]["columns"][0]["label"] = json!("6评估");
    content["body_blocks"][1]["rows"][0]["cells"][0]["display_text"] = json!("1数据与身份");
    content["body_blocks"][1]["rows"][1]["cells"][0]["display_text"] = json!("6评估与持续运营");
    content["body_blocks"][1]["rows"][2]["cells"][0]["display_text"] = json!("阶段3");

    let spaced_dir = tempfile::tempdir().unwrap();
    let saved = save_page(spaced_dir.path(), &spaced);
    let stored = serde_json::to_value(&saved.deck.pages[0].content).unwrap();
    assert_eq!(stored["title"], "1 数据与身份");
    assert_eq!(stored["body_blocks"][0]["text"], "模块 2 已覆盖 535 类");
    assert_eq!(stored["body_blocks"][1]["columns"][0]["label"], "6 评估");
    assert_eq!(
        stored["body_blocks"][1]["rows"][0]["cells"][0]["display_text"],
        "1 数据与身份"
    );
    assert_eq!(
        stored["body_blocks"][1]["rows"][1]["cells"][0]["display_text"],
        "6 评估与持续运营"
    );
    assert_eq!(
        stored["body_blocks"][1]["rows"][2]["cells"][0]["display_text"],
        "阶段\u{3000}3"
    );
    assert_eq!(
        stored["body_blocks"][1]["rows"][3]["cells"][0]["display_text"],
        "1数据与身份"
    );

    let basis = ops::basis("svg", &saved.deck, &saved.deck.pages[0]).unwrap();
    let replay = ops::put(
        spaced_dir.path(),
        saved.version,
        serde_json::from_value(spaced.clone()).unwrap(),
    )
    .unwrap();
    assert_eq!(replay.version, saved.version);
    assert_eq!(replay.deck.pages[0].content, saved.deck.pages[0].content);
    assert_eq!(
        ops::basis("svg", &replay.deck, &replay.deck.pages[0]).unwrap(),
        basis
    );

    let collapsed_dir = tempfile::tempdir().unwrap();
    let plain = save_page(collapsed_dir.path(), &collapsed);
    let plain_stored = serde_json::to_value(&plain.deck.pages[0].content).unwrap();
    assert_eq!(plain_stored["title"], "1数据与身份");
    assert_eq!(content_ids(&stored), content_ids(&plain_stored));
    assert_ne!(
        ops::basis("svg", &plain.deck, &plain.deck.pages[0]).unwrap(),
        basis
    );
}

fn save_page(path: &std::path::Path, value: &serde_json::Value) -> deck::model::Snapshot {
    ops::new(path, "合成稿".into()).unwrap();
    ops::put(path, 1, serde_json::from_value(value.clone()).unwrap()).unwrap()
}

fn content_ids(content: &serde_json::Value) -> Vec<&str> {
    let mut ids = Vec::new();
    fn walk<'a>(value: &'a serde_json::Value, ids: &mut Vec<&'a str>) {
        match value {
            serde_json::Value::Array(items) => {
                for item in items {
                    walk(item, ids);
                }
            }
            serde_json::Value::Object(map) => {
                if let Some(serde_json::Value::String(id)) = map.get("id") {
                    ids.push(id.as_str());
                }
                for (key, child) in map {
                    if key != "id" {
                        walk(child, ids);
                    }
                }
            }
            _ => {}
        }
    }
    walk(content, &mut ids);
    ids
}
