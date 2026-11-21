use deck::error::Error;
use deck::model::{self, Argument, Evidence};
use deck::{ops, store};
use serde_json::{Value, json};
use std::path::Path;

fn patch(value: Value) -> deck::model::Patch {
    serde_json::from_value(value).unwrap()
}

fn user_version(path: &Path) -> i64 {
    store::Store::open(path)
        .unwrap()
        .connection
        .pragma_query_value(None, "user_version", |row| row.get(0))
        .unwrap()
}

fn deck_json(path: &Path, version: i64) -> String {
    let store = store::Store::open(path).unwrap();
    store
        .connection
        .query_row(
            "SELECT deck_json FROM versions WHERE id=?",
            [version],
            |row| row.get(0),
        )
        .unwrap()
}

fn table_count(path: &Path, table: &str) -> i64 {
    let store = store::Store::open(path).unwrap();
    store
        .connection
        .query_row(&format!("SELECT COUNT(*) FROM {table}"), [], |row| {
            row.get(0)
        })
        .unwrap()
}

fn review_has_record_kind(path: &Path) -> bool {
    let store = store::Store::open(path).unwrap();
    let mut statement = store
        .connection
        .prepare("PRAGMA table_info(reviews)")
        .unwrap();
    statement
        .query_map([], |row| row.get::<_, String>(1))
        .unwrap()
        .any(|name| name.unwrap() == "record_kind")
}

fn input_text(result: Result<Value, Error>) -> String {
    match result {
        Err(error) => {
            assert_eq!(error.exit_code(), 2);
            match error {
                Error::Input(text) => text,
                other => panic!("expected input error, got {other}"),
            }
        }
        Ok(_) => panic!("expected input error"),
    }
}

fn current_version(path: &Path) -> i64 {
    store::Store::open(path).unwrap().current().unwrap().version
}

fn framed_brief(title: &str) -> Value {
    json!({
        "title": title,
        "audience": "业务负责人",
        "decision": "是否采用该方案",
        "concerns": ["成本是否可控"],
        "narrator": {"role": "项目负责人", "tone": "直接说明判断"}
    })
}

fn storyline() -> Value {
    json!({"storyline": ["先说明问题，再给出判断"]})
}

fn write_deck(path: &Path, version: i64, value: &Value) {
    let store = store::Store::open(path).unwrap();
    store
        .connection
        .execute(
            "UPDATE versions SET deck_json=?1 WHERE id=?2",
            rusqlite::params![value.to_string(), version],
        )
        .unwrap();
}

fn downgrade_to_v6(path: &Path) {
    let store = store::Store::open(path).unwrap();
    store
        .connection
        .execute_batch(
            "CREATE TABLE reviews_v6 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id INTEGER NOT NULL, page_id TEXT,
                reviewer TEXT NOT NULL,
                method TEXT NOT NULL CHECK (method IN ('self_check','other_model','human')),
                text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved')),
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                resolved_at TEXT
            );
            INSERT INTO reviews_v6 (id,version_id,page_id,reviewer,method,text,status,created_at,resolved_at)
                SELECT id,version_id,page_id,reviewer,method,text,status,created_at,resolved_at FROM reviews;
            DROP TABLE reviews;
            ALTER TABLE reviews_v6 RENAME TO reviews;
            PRAGMA user_version = 6;",
        )
        .unwrap();
}

fn json_after(text: &str, marker: &str) -> Value {
    let snippet = text
        .split(marker)
        .nth(1)
        .unwrap_or_else(|| panic!("missing {marker} in {text}"));
    serde_json::from_str(snippet).unwrap_or_else(|error| panic!("{error} in {snippet}"))
}

#[test]
fn blank_kind_is_listed_with_the_frame_and_the_snippet_can_start() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    let created = ops::put(
        path,
        1,
        patch(json!({
            "order": ["p1", "p2"],
            "brief": {"title": "合成作品", "goal": "保留目标", "audience": "  "},
            "framing": {"thesis": "保留主张", "storyline": [" "]},
            "pages": [
                {"id": "p1", "content": {"title": "一页"}, "notes": "保留讲稿"},
                {"id": "p2", "kind": "reference", "content": {"title": "查阅"}}
            ]
        })),
    )
    .unwrap();
    let text = input_text(ops::run_start(path, "image", &["p1".into()], None));
    let shown = format!("输入有误：{text}");
    assert!(shown.starts_with("输入有误：无法开始生成。当前作品缺少以下字段："));
    for field in [
        "brief.audience",
        "brief.decision",
        "brief.concerns",
        "brief.narrator.role",
        "brief.narrator.tone",
        "framing.storyline",
        "pages[p1].kind",
    ] {
        assert!(
            text.contains(&format!("- {field}")),
            "missing {field}: {text}"
        );
    }
    assert!(!text.contains("pages[p2].kind"), "{text}");
    assert!(!text.contains("判断页证据"), "{text}");
    assert!(text.contains(&format!("deck put --base {} payload.json", created.version)));
    assert_eq!(current_version(path), created.version);
    assert_eq!(table_count(path, "runs"), 0);
    assert_eq!(table_count(path, "run_pages"), 0);
    let snippet = json_after(&text, "payload.json 最小片段：\n");
    assert_eq!(
        snippet["pages"],
        json!([{"id": "p1", "kind": "explanation"}])
    );
    assert!(snippet["brief"]["goal"] == "保留目标");
    assert!(snippet["framing"]["thesis"] == "保留主张");
    let saved = ops::put(path, created.version, patch(snippet)).unwrap();
    assert_eq!(saved.deck.pages[0].content.title, "一页");
    assert_eq!(saved.deck.pages[0].notes, "保留讲稿");
    assert_eq!(saved.deck.pages[0].kind, "explanation");
    assert_eq!(saved.deck.pages[1].kind, "reference");
    assert_eq!(saved.deck.brief.goal, "保留目标");
    let started = ops::run_start(path, "image", &["p1".into()], None).unwrap();
    assert_eq!(started["runs"][0]["pages"][0]["status"], "pending");
    assert_eq!(table_count(path, "runs"), 1);
}

#[test]
fn v6_without_kind_is_rejected_in_place_and_a_complete_v6_start_does_not_upgrade() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    let created = ops::put(
        path,
        1,
        patch(json!({
            "brief": framed_brief("合成作品"),
            "framing": storyline(),
            "order": ["p1"],
            "pages": [{"id": "p1", "content": {"title": "旧页"}}]
        })),
    )
    .unwrap();
    downgrade_to_v6(path);
    let mut value: Value = serde_json::from_str(&deck_json(path, created.version)).unwrap();
    value["pages"][0].as_object_mut().unwrap().remove("kind");
    write_deck(path, created.version, &value);
    assert!(!review_has_record_kind(path));
    let text = input_text(ops::run_start(path, "svg", &["p1".into()], None));
    assert!(text.contains("- pages[p1].kind"), "{text}");
    assert!(!text.contains("- brief.audience"), "{text}");
    assert!(!text.contains("判断页证据"), "{text}");
    assert_eq!(user_version(path), 6);
    assert_eq!(table_count(path, "runs"), 0);
    assert_eq!(table_count(path, "run_pages"), 0);
    assert!(!review_has_record_kind(path));
    assert_eq!(
        store::Store::open(path).unwrap().history().unwrap().len(),
        2
    );

    let ready = tempfile::tempdir().unwrap();
    let ready_path = ready.path();
    ops::new(ready_path, "合成作品".into()).unwrap();
    let saved = ops::put(
        ready_path,
        1,
        patch(json!({
            "brief": framed_brief("合成作品"),
            "framing": storyline(),
            "order": ["p1"],
            "pages": [{"id": "p1", "kind": "explanation", "content": {"title": "可生成"}}]
        })),
    )
    .unwrap();
    downgrade_to_v6(ready_path);
    let started = ops::run_start(ready_path, "image", &["p1".into()], None).unwrap();
    assert_eq!(started["runs"][0]["status"], "open");
    assert_eq!(user_version(ready_path), 6);
    assert_eq!(current_version(ready_path), saved.version);
    assert!(!review_has_record_kind(ready_path));
    assert_eq!(table_count(ready_path, "runs"), 1);
    assert_eq!(table_count(ready_path, "run_pages"), 1);
}

#[test]
fn frame_is_checked_before_kind_and_blank_kind_is_not_a_judgment_page() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    let created = ops::put(
        path,
        1,
        patch(json!({
            "order": ["p1", "late"],
            "pages": [
                {"id": "p1", "kind": "explanation", "content": {"title": "一页"}},
                {"id": "late", "content": {"title": "未选"}}
            ]
        })),
    )
    .unwrap();
    let mut value: Value = serde_json::from_str(&deck_json(path, created.version)).unwrap();
    value["pages"][0]["kind"] = json!("poster");
    write_deck(path, created.version, &value);
    let text = input_text(ops::run_start(path, "native", &["p1".into()], None));
    assert!(text.contains("- brief.audience"), "{text}");
    assert!(!text.contains("只接受"), "{text}");
    assert!(!text.contains("poster"), "{text}");
    assert!(!text.contains("pages[late]"), "{text}");
    assert_eq!(current_version(path), created.version);
    assert_eq!(table_count(path, "runs"), 0);
    assert_eq!(table_count(path, "run_pages"), 0);

    let snippet = json_after(&text, "payload.json 最小片段：\n");
    assert!(snippet.get("pages").is_none(), "{snippet}");
    let framed = ops::put(path, created.version, patch(snippet)).unwrap();
    let illegal = input_text(ops::run_start(path, "image", &["p1".into()], None));
    assert!(illegal.contains("只接受"), "{illegal}");
    assert!(illegal.contains("poster"), "{illegal}");
    assert!(!illegal.contains("判断页证据"), "{illegal}");
    assert_eq!(table_count(path, "runs"), 0);

    let mut current: Value = serde_json::from_str(&deck_json(path, framed.version)).unwrap();
    current["pages"][0]["kind"] = json!("  ");
    current["pages"][0]["argument"] = json!(null);
    write_deck(path, framed.version, &current);
    let blank = input_text(ops::run_start(path, "image", &["p1".into()], None));
    assert!(blank.contains("- pages[p1].kind"), "{blank}");
    assert!(!blank.contains("判断页证据"), "{blank}");
    assert!(!blank.contains("只接受"), "{blank}");
    assert_eq!(table_count(path, "runs"), 0);

    let rejected = ops::put(
        path,
        framed.version,
        patch(json!({"pages":[{"id":"p1","kind":"  "}]})),
    );
    let rejected = input_text(rejected.map(|_| Value::Null));
    assert!(rejected.contains("kind"), "{rejected}");
}

#[test]
fn judgment_evidence_must_name_ref_or_gap_and_the_snippet_can_start() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    let created = ops::put(
        path,
        1,
        patch(json!({
            "brief": framed_brief("合成作品"),
            "framing": storyline(),
            "order": ["p1", "p2", "p3", "explain", "lookup", "teach"],
            "pages": [
                {"id": "p1", "kind": "judgment", "content": {"title": "待证主张"}},
                {
                    "id": "p2",
                    "kind": "judgment",
                    "content": {"title": "已有理由"},
                    "argument": {
                        "reasons": ["已有理由"],
                        "evidence": [],
                        "reasoning": "已有推理",
                        "rebuttal": ""
                    }
                },
                {
                    "id": "p3",
                    "kind": "judgment",
                    "content": {"title": "第三条"},
                    "argument": {
                        "evidence": [
                            {"text": "有出处", "ref": "m1"},
                            {"text": "一句"},
                            {"text": "  ", "ref": "  ", "gap": "   "}
                        ]
                    }
                },
                {"id": "explain", "kind": "explanation", "argument": {"evidence": [{"text": ""}]}},
                {"id": "lookup", "kind": "reference"},
                {"id": "teach", "kind": "teaching"}
            ]
        })),
    )
    .unwrap();
    let open = ops::run_start(
        path,
        "image",
        &["explain".into(), "lookup".into(), "teach".into()],
        None,
    )
    .unwrap();
    assert_eq!(open["runs"][0]["pages"].as_array().unwrap().len(), 3);
    ops::run_cancel(path, open["runs"][0]["id"].as_i64().unwrap()).unwrap();

    let text = input_text(ops::run_start(
        path,
        "svg",
        &["p3".into(), "p1".into(), "p2".into(), "explain".into()],
        None,
    ));
    assert_eq!(current_version(path), created.version);
    assert_eq!(table_count(path, "runs"), 1);
    assert_eq!(table_count(path, "run_pages"), 3);
    let mut parts = text.split("\n\n");
    assert_eq!(
        parts.next().unwrap(),
        "无法开始生成。判断页证据不完整：\n- pages[p1].argument.evidence 为空，请至少提供一条带 ref 或 gap 的证据\n- pages[p2].argument.evidence 为空，请至少提供一条带 ref 或 gap 的证据\n- pages[p3].argument.evidence[1] 既没有 ref 也没有 gap\n- pages[p3].argument.evidence[2] 既没有 ref 也没有 gap\n请用 deck put 补全，例如："
    );
    assert_eq!(
        parts.next().unwrap(),
        format!("  deck put --base {} payload.json", created.version)
    );
    let snippet: Value = serde_json::from_str(parts.next().unwrap()).unwrap();
    assert!(parts.next().is_none());
    assert!(snippet.get("brief").is_none());
    assert_eq!(
        snippet["pages"][0]["argument"],
        json!({
            "reasons": ["理由一", "理由二"],
            "evidence": [{"text": "出处或待补说明", "gap": "待补：需补充口径"}],
            "reasoning": "",
            "rebuttal": ""
        })
    );
    assert_eq!(
        snippet["pages"][1]["argument"]["reasons"],
        json!(["已有理由"])
    );
    assert_eq!(snippet["pages"][1]["argument"]["reasoning"], "已有推理");
    assert_eq!(
        snippet["pages"][2]["argument"]["evidence"][0],
        json!({"text": "有出处", "ref": "m1"})
    );
    assert_eq!(
        snippet["pages"][2]["argument"]["evidence"][1],
        json!({"text": "一句", "gap": "待补：需补充口径"})
    );
    assert_eq!(
        snippet["pages"][2]["argument"]["evidence"][2]["text"],
        "出处或待补说明"
    );
    let saved = ops::put(path, created.version, patch(snippet)).unwrap();
    assert_eq!(saved.deck.pages[0].content.title, "待证主张");
    assert_eq!(saved.deck.pages[2].content.title, "第三条");
    let started = ops::run_start(
        path,
        "image",
        &[
            "p1".into(),
            "p2".into(),
            "p3".into(),
            "explain".into(),
            "lookup".into(),
            "teach".into(),
        ],
        None,
    )
    .unwrap();
    assert_eq!(started["runs"][0]["status"], "open");
}

#[test]
fn whitespace_ref_or_gap_is_absent_and_both_real_values_stay_illegal() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    let created = ops::put(
        path,
        1,
        patch(json!({
            "brief": framed_brief("合成作品"),
            "framing": storyline(),
            "order": ["p1", "p2"],
            "pages": [
                {"id": "p1", "kind": "judgment"},
                {"id": "p2", "kind": "explanation"}
            ]
        })),
    )
    .unwrap();
    let both = ops::put(
        path,
        created.version,
        patch(
            json!({"pages":[{"id":"p1","argument":{"evidence":[{"text":"一句","ref":" m1 ","gap":" 缺口 "}]}}]}),
        ),
    );
    let both = input_text(both.map(|_| Value::Null));
    assert!(both.contains("第 1 项"), "{both}");
    assert!(both.contains("二者互斥"), "{both}");

    let gap_only = ops::put(
        path,
        created.version,
        patch(json!({"pages":[{"id":"p1","argument":{"evidence":[{"text":"对比基数","ref":"  ","gap":"缺数"}]}}]})),
    )
    .unwrap();
    let stored = &gap_only.deck.pages[0].argument.as_ref().unwrap().evidence[0];
    assert_eq!(stored.r#ref.as_deref(), Some("  "));
    assert_eq!(stored.gap.as_deref(), Some("缺数"));
    assert!(stored.has_gap());
    assert!(!stored.has_ref());
    let started = ops::run_start(path, "image", &["p1".into()], None).unwrap();
    assert_eq!(
        ops::get(path, None).unwrap()["gap_list"],
        json!([{
            "page_id": "p1",
            "source": "evidence",
            "text": "对比基数",
            "gap": "缺数"
        }])
    );
    ops::run_cancel(path, started["runs"][0]["id"].as_i64().unwrap()).unwrap();

    let blank = ops::put(
        path,
        gap_only.version,
        patch(json!({"pages":[{"id":"p1","argument":{"evidence":[{"text":"","ref":"  ","gap":"  "}]}}]})),
    )
    .unwrap();
    assert_eq!(
        blank.deck.pages[0].argument.as_ref().unwrap().evidence[0],
        Evidence {
            text: String::new(),
            r#ref: Some("  ".into()),
            gap: Some("  ".into()),
        }
    );
    let before = deck_json(path, blank.version);
    let text = input_text(ops::run_start(path, "native", &["p1".into()], None));
    assert!(
        text.contains("- pages[p1].argument.evidence[0] 既没有 ref 也没有 gap"),
        "{text}"
    );
    assert_eq!(current_version(path), blank.version);
    assert_eq!(table_count(path, "runs"), 1);

    let mut injected: Value = serde_json::from_str(&before).unwrap();
    injected["pages"][0]["argument"]["evidence"][0] =
        json!({"text":"一句","ref":"m1","gap":"缺数"});
    write_deck(path, blank.version, &injected);
    let exclusive = input_text(ops::run_start(path, "image", &["p1".into()], None));
    assert!(exclusive.contains("第 1 项"), "{exclusive}");
    assert!(exclusive.contains("二者互斥"), "{exclusive}");
    assert!(!exclusive.contains("判断页证据不完整"), "{exclusive}");
    assert_eq!(table_count(path, "runs"), 1);

    injected["pages"][1]["argument"] =
        json!({"evidence":[{"text":"说明页","ref":"m1","gap":"缺数"}]});
    injected["pages"][0]["argument"]["evidence"][0] = json!({"text":"对比基数","gap":"缺数"});
    write_deck(path, blank.version, &injected);
    assert!(ops::run_start(path, "image", &["p2".into()], None).is_ok());
}

#[test]
fn gap_list_follows_page_order_and_cannot_be_written() {
    let deck = deck::model::Deck {
        pages: vec![
            deck::model::Page {
                id: "p2".into(),
                todo: vec![" ".into(), "页面待办原文".into(), "页面待办原文".into()],
                ..deck::model::Page::default()
            },
            deck::model::Page {
                id: "p1".into(),
                kind: "judgment".into(),
                todo: vec!["封面待办".into()],
                argument: Some(Argument {
                    evidence: vec![
                        Evidence {
                            text: "有出处".into(),
                            r#ref: Some("m1".into()),
                            gap: Some("  ".into()),
                        },
                        Evidence {
                            text: "材料未给出的对比基数".into(),
                            r#ref: Some("  ".into()),
                            gap: Some(" 待补：需披露口径与年份 ".into()),
                        },
                        Evidence {
                            text: "材料未给出的对比基数".into(),
                            r#ref: None,
                            gap: Some(" 待补：需披露口径与年份 ".into()),
                        },
                    ],
                    ..Argument::default()
                }),
                ..deck::model::Page::default()
            },
        ],
        ..deck::model::Deck::default()
    };
    assert_eq!(
        model::gap_list(&deck.pages),
        json!([
            {"page_id":"p2","source":"todo","text":"页面待办原文"},
            {"page_id":"p2","source":"todo","text":"页面待办原文"},
            {
                "page_id":"p1",
                "source":"evidence",
                "text":"材料未给出的对比基数",
                "gap":" 待补：需披露口径与年份 "
            },
            {
                "page_id":"p1",
                "source":"evidence",
                "text":"材料未给出的对比基数",
                "gap":" 待补：需披露口径与年份 "
            },
            {"page_id":"p1","source":"todo","text":"封面待办"}
        ])
    );
    assert!(model::gap_list(&deck.pages)[0].get("gap").is_none());

    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    ops::put(
        path,
        1,
        patch(json!({
            "order": ["p2", "p1"],
            "pages": [
                {"id": "p2", "todo": ["页面待办原文"]},
                {
                    "id": "p1",
                    "kind": "judgment",
                    "todo": ["封面待办"],
                    "argument": {"evidence": [{"text": "材料未给出的对比基数", "gap": "待补：需披露口径与年份"}]}
                }
            ]
        })),
    )
    .unwrap();
    let got = ops::get(path, None).unwrap();
    assert_eq!(got["gap_list"][0]["page_id"], "p2");
    assert_eq!(got["gap_list"][0]["source"], "todo");
    assert_eq!(got["gap_list"][1]["source"], "evidence");
    assert!(got["deck"].get("gap_list").is_none());
    let stored: Value =
        serde_json::from_str(&deck_json(path, got["version"].as_i64().unwrap())).unwrap();
    assert!(stored.get("gap_list").is_none());
    assert!(stored["pages"][1].get("gap_list").is_none());
    let shown = ops::show(path).unwrap();
    assert_eq!(shown["gap_list"], got["gap_list"]);
    let workspace = ops::workspace(path).unwrap();
    assert_eq!(workspace["gap_list"], got["gap_list"]);
    let partial = ops::get(path, Some(&["p1".into()])).unwrap();
    assert_eq!(
        partial["gap_list"],
        json!([got["gap_list"][1].clone(), got["gap_list"][2].clone()])
    );

    let version = got["version"].as_i64().unwrap();
    for (value, unwrap_deck) in [
        (json!({"gap_list": [], "brief": {"title": "甲"}}), false),
        (
            json!({"version": version, "gap_list": [], "deck": {"brief": {"title": "甲"}}}),
            true,
        ),
        (
            json!({"outline": [], "gap_list": [{"page_id": "p1", "source": "todo", "text": "改写"}]}),
            false,
        ),
    ] {
        assert!(matches!(
            ops::put_patch(value, unwrap_deck),
            Err(Error::Input(_))
        ));
    }
    assert_eq!(current_version(path), version);
}
