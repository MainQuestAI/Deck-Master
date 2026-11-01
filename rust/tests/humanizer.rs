use deck::{model::Patch, ops};
use serde_json::json;

#[test]
fn save_normalizes_visible_spacing_without_changing_author_notes_or_data() {
    let temporary = tempfile::tempdir().unwrap();
    ops::new(temporary.path(), "合成稿".into()).unwrap();
    let input = json!({"order":["p1"],"pages":[{"id":"p1","notes":"原稿  备注", "todo":["补充原始依据"],"content":{"title":"覆盖535  类标签", "body_blocks":[{"type":"paragraph","text":"连接CDP  、VOC；保留New Product与99%。"}]}}]});
    let patch: Patch = serde_json::from_value(input.clone()).unwrap();
    let result = ops::put(temporary.path(), 1, patch).unwrap();
    assert_eq!(result.deck.pages[0].content.title, "覆盖535类标签");
    assert_eq!(result.deck.pages[0].notes, "原稿  备注");
    assert_eq!(result.deck.pages[0].todo, ["补充原始依据"]);
    let retry = ops::put(temporary.path(), 1, serde_json::from_value(input).unwrap()).unwrap();
    assert_eq!(result.version, retry.version);
    let review = ops::humanize(temporary.path(), "pptx", None).unwrap();
    assert_eq!(review["version"], result.version);
    assert_eq!(
        review["deck"]["pages"][0]["content"],
        serde_json::to_value(result.deck.pages[0].content.clone()).unwrap()
    );
}

#[test]
fn draft_review_preserves_ids_numeric_values_and_claim_boundaries() {
    let temporary = tempfile::tempdir().unwrap();
    let input = json!({"pages":[{"id":"p 1","content":{"title":"设计目标99%  ，仅限试运行", "body_blocks":[{"id":"t 1","type":"table","columns":[{"id":"c 1","label":"数据量"}],"rows":[{"cells":[{"column_id":"c 1","value":"535  类","display_text":"535  类"}]}]}]}}]});
    let path = temporary.path().join("draft.json");
    std::fs::write(&path, serde_json::to_vec(&input).unwrap()).unwrap();
    let result = ops::humanize(temporary.path(), "content", Some(&path)).unwrap();
    let page = &result["deck"]["pages"][0];
    assert_eq!(page["id"], "p 1");
    assert_eq!(
        page["content"]["body_blocks"][0]["rows"][0]["cells"][0]["value"],
        "535  类"
    );
    assert_eq!(page["content"]["title"], "设计目标99%，仅限试运行");
    assert_eq!(
        std::fs::read(&path).unwrap(),
        serde_json::to_vec(&input).unwrap()
    );
}
