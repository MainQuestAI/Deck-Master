use deck::error::Error;
use deck::model::{self, Brief, Deck, Evidence, Framing, Page};
use deck::{ops, store};
use rusqlite::Connection;
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

fn review_columns(path: &Path) -> Vec<String> {
    let store = store::Store::open(path).unwrap();
    let mut statement = store
        .connection
        .prepare("PRAGMA table_info(reviews)")
        .unwrap();
    statement
        .query_map([], |row| row.get::<_, String>(1))
        .unwrap()
        .collect::<Result<Vec<_>, _>>()
        .unwrap()
}

fn run_count(path: &Path) -> i64 {
    let store = store::Store::open(path).unwrap();
    store
        .connection
        .query_row("SELECT COUNT(*) FROM runs", [], |row| row.get(0))
        .unwrap()
}

fn strip_v7_fields(value: &mut Value) {
    if let Some(brief) = value.get_mut("brief").and_then(Value::as_object_mut) {
        brief.remove("decision");
        brief.remove("concerns");
        brief.remove("narrator");
    }
    if let Some(framing) = value.get_mut("framing").and_then(Value::as_object_mut) {
        framing.remove("storyline");
    }
    if let Some(pages) = value.get_mut("pages").and_then(Value::as_array_mut) {
        for page in pages {
            if let Some(page) = page.as_object_mut() {
                page.remove("kind");
                page.remove("argument");
                page.remove("revision");
            }
        }
    }
}

fn downgrade_to_v6(path: &Path, strip_json: bool) {
    let store = store::Store::open(path).unwrap();
    if strip_json {
        let mut rows = store
            .connection
            .prepare("SELECT id, deck_json FROM versions")
            .unwrap();
        let saved: Vec<(i64, String)> = rows
            .query_map([], |row| Ok((row.get(0)?, row.get(1)?)))
            .unwrap()
            .collect::<Result<_, _>>()
            .unwrap();
        drop(rows);
        for (id, json) in saved {
            let mut value: Value = serde_json::from_str(&json).unwrap();
            strip_v7_fields(&mut value);
            store
                .connection
                .execute(
                    "UPDATE versions SET deck_json=?1 WHERE id=?2",
                    rusqlite::params![value.to_string(), id],
                )
                .unwrap();
        }
    }
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

fn frame_patch(title: &str) -> Value {
    json!({
        "brief": {
            "title": title,
            "audience": "业务负责人",
            "decision": "是否采用该方案",
            "concerns": ["成本是否可控"],
            "narrator": {"role": "项目负责人", "tone": "直接说明判断"}
        },
        "framing": {"storyline": ["先说明问题，再给出判断"]}
    })
}

#[test]
fn v6_json_uses_serde_defaults() {
    let brief: Brief = serde_json::from_str(r#"{"title":"合成","audience":"读者"}"#).unwrap();
    assert_eq!(brief.decision, "");
    assert!(brief.concerns.is_empty());
    assert_eq!(brief.narrator.role, "");
    assert_eq!(brief.narrator.tone, "");
    let framing: Framing = serde_json::from_str(r#"{"thesis":"主张"}"#).unwrap();
    assert!(framing.storyline.is_empty());
    let page: Page = serde_json::from_str(r#"{"id":"p1","content":{"title":"一页"}}"#).unwrap();
    assert_eq!(page.kind, "");
    assert_eq!(page.argument, None);
    assert_eq!(page.revision, 1);
    assert_eq!(Page::default().revision, 1);
}

#[test]
fn opening_v6_does_not_write_and_future_formats_still_ask_for_an_upgrade() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    ops::put(
        path,
        1,
        patch(json!({"order":["p1"],"pages":[{"id":"p1","content":{"title":"一页"}}]})),
    )
    .unwrap();
    downgrade_to_v6(path, true);
    let before = deck_json(path, 2);
    let columns = review_columns(path);
    assert!(!columns.iter().any(|name| name == "record_kind"));
    assert_eq!(user_version(path), 6);

    ops::get(path, None).unwrap();
    ops::show(path).unwrap();
    ops::workspace(path).unwrap();
    ops::review_list(path, None, None).unwrap();
    let _ = ops::doctor(&[]);
    let start = ops::run_start(path, "image", &["p1".into()], None);
    assert!(start.is_err());
    assert_eq!(run_count(path), 0);
    assert!(ops::build(path).is_err());
    assert!(ops::export_pptx(path).is_err());

    assert_eq!(user_version(path), 6);
    assert_eq!(deck_json(path, 2), before);
    assert_eq!(review_columns(path), columns);
    assert_eq!(
        store::Store::open(path).unwrap().history().unwrap().len(),
        2
    );

    let store = store::Store::open(path).unwrap();
    store
        .connection
        .pragma_update(None, "user_version", 8)
        .unwrap();
    drop(store);
    match store::Store::open(path) {
        Err(Error::Input(text)) => assert!(text.contains("请升级 deck")),
        Ok(_) => panic!("expected upgrade message"),
        Err(error) => panic!("expected upgrade message, got {error}"),
    }
}

#[test]
fn first_put_on_v6_upgrades_in_one_transaction_and_writes_revision_one() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    ops::put(
        path,
        1,
        patch(json!({"order":["p1"],"pages":[{"id":"p1","purpose":"说明","content":{"title":"一页"}}]})),
    )
    .unwrap();
    downgrade_to_v6(path, true);
    let previous = deck_json(path, 2);
    let saved = ops::put(
        path,
        2,
        patch(json!({"brief":{"title":"合成作品","audience":"读者"}})),
    )
    .unwrap();
    assert_eq!(saved.version, 3);
    assert_eq!(saved.deck.pages[0].revision, 1);
    assert_eq!(user_version(path), 7);
    let columns = review_columns(path);
    for name in ["record_kind", "snapshot_json", "checks_json"] {
        assert!(columns.iter().any(|column| column == name), "{name}");
    }
    assert_eq!(deck_json(path, 2), previous);
    let written: Value = serde_json::from_str(&deck_json(path, 3)).unwrap();
    assert_eq!(written["pages"][0]["revision"], 1);
    assert!(written["brief"].get("decision").is_some());
    assert!(written["framing"].get("storyline").is_some());
    let connection = Connection::open(path.join(".deck/deck.db")).unwrap();
    let definition: String = connection
        .query_row(
            "SELECT sql FROM sqlite_master WHERE name='reviews'",
            [],
            |row| row.get(0),
        )
        .unwrap();
    assert!(definition.contains("record_kind"));
    assert!(definition.contains("content_review"));
}

#[test]
fn revision_bumps_for_author_fields_and_not_for_image_or_preview() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    let created = ops::put(
        path,
        1,
        patch(json!({"order":["p1"],"pages":[{"id":"p1","purpose":"说明","content":{"title":"一页"}}]})),
    )
    .unwrap();
    assert_eq!(created.deck.pages[0].revision, 1);
    let noted = ops::put(
        path,
        created.version,
        patch(json!({"pages":[{"id":"p1","notes":"讲稿"}]})),
    )
    .unwrap();
    assert_eq!(noted.deck.pages[0].revision, 2);
    let mut store = store::Store::open(path).unwrap();
    let mut deck = store.current().unwrap().deck;
    deck.pages[0].image = Some(deck::model::Artifact {
        file: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.bin".into(),
        basis: "basis".into(),
    });
    deck.pages[0].preview = Some("preview.png".into());
    let tx = store.transaction().unwrap();
    store::append(&tx, &mut deck, "synthetic image").unwrap();
    tx.commit().unwrap();
    assert_eq!(deck.pages[0].revision, 2);
    let changed = ops::put(
        path,
        store.current().unwrap().version,
        patch(json!({"pages":[{"id":"p1","kind":"explanation"}]})),
    )
    .unwrap();
    assert_eq!(changed.deck.pages[0].revision, 3);
    assert_eq!(changed.deck.pages[0].kind, "explanation");
    assert!(changed.deck.pages[0].image.is_some());
}

#[test]
fn page_patch_rejects_revision_and_put_rejects_derived_output() {
    let error = serde_json::from_value::<deck::model::Patch>(json!({
        "pages":[{"id":"p1","revision":4}]
    }))
    .unwrap_err()
    .to_string();
    assert!(error.contains("revision"));
    assert!(error.contains("unknown field"));
    let rejected = ops::put_patch(
        json!({"writing_brief":"受众：读者","brief":{"title":"甲"}}),
        false,
    );
    assert!(matches!(rejected, Err(Error::Input(_))));
    let nested = ops::put_patch(
        json!({"version":1,"writing_brief":"x","outline":[],"deck":{"brief":{"title":"甲"}}}),
        true,
    );
    assert!(matches!(nested, Err(Error::Input(_))));
}

#[test]
fn illegal_kind_is_rejected_on_put_and_run_start_without_writing() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    let created = ops::put(
        path,
        1,
        patch(json!({"order":["p1"],"pages":[{"id":"p1","content":{"title":"一页"}}]})),
    )
    .unwrap();
    let before = deck_json(path, created.version);
    let rejected = ops::put(
        path,
        created.version,
        patch(json!({"pages":[{"id":"p1","kind":"判断"}]})),
    );
    assert!(matches!(rejected, Err(Error::Input(_))));
    assert_eq!(deck_json(path, created.version), before);
    assert_eq!(user_version(path), 7);
    ops::put(path, created.version, patch(frame_patch("合成作品"))).unwrap();
    let store = store::Store::open(path).unwrap();
    let version = store.current().unwrap().version;
    let mut value: Value = serde_json::from_str(&deck_json(path, version)).unwrap();
    value["pages"][0]["kind"] = json!("Judgment");
    store
        .connection
        .execute(
            "UPDATE versions SET deck_json=?1 WHERE id=?2",
            rusqlite::params![value.to_string(), version],
        )
        .unwrap();
    drop(store);
    let started = ops::run_start(path, "svg", &["p1".into()], None);
    match started {
        Err(Error::Input(text)) => assert!(text.contains("kind")),
        Ok(_) => panic!("expected kind error"),
        Err(error) => panic!("expected kind error, got {error}"),
    }
    assert_eq!(run_count(path), 0);
}

#[test]
fn frame_gate_lists_every_missing_field_then_start_passes_without_upgrading_v6() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    ops::put(
        path,
        1,
        patch(json!({
            "order":["p1"],
            "pages":[{"id":"p1","content":{"title":"一页"}}],
            "brief":{"title":"合成作品","goal":"保留目标","audience":"  ","concerns":["  "]},
            "framing":{"thesis":"保留主张","storyline":[" "]}
        })),
    )
    .unwrap();
    downgrade_to_v6(path, false);
    let before = deck_json(path, 2);
    for kind in ["image", "svg", "native"] {
        match ops::run_start(path, kind, &["p1".into()], None) {
            Err(Error::Input(text)) => {
                let shown = format!("输入有误：{text}");
                assert!(shown.starts_with("输入有误：无法开始生成。当前作品缺少以下字段："));
                assert!(text.contains("deck put --base 2 payload.json"), "{text}");
                assert!(text.contains("\"audience\": \"管理层\""), "{text}");
                assert!(
                    text.contains("\"decision\": \"本周需拍板的事项\""),
                    "{text}"
                );
                assert!(text.contains("\"关注点一\""), "{text}");
                assert!(text.contains("\"role\": \"资深顾问\""), "{text}");
                assert!(text.contains("\"tone\": \"结论先行，语气肯定\""), "{text}");
                assert!(text.contains("\"第一句主线\""), "{text}");
                assert!(text.contains("合成作品"), "{text}");
                assert!(text.contains("保留目标"), "{text}");
                assert!(text.contains("保留主张"), "{text}");
                assert!(text.contains("- pages[p1].kind"), "{text}");
                assert!(text.contains("\"kind\": \"explanation\""), "{text}");
                assert!(!text.contains("判断页证据"), "{text}");
                for field in [
                    "brief.audience",
                    "brief.decision",
                    "brief.concerns",
                    "brief.narrator.role",
                    "brief.narrator.tone",
                    "framing.storyline",
                ] {
                    assert!(
                        text.contains(&format!("- {field}")),
                        "{kind} missing {field}: {text}"
                    );
                }
            }
            Ok(_) => panic!("{kind} should be rejected"),
            Err(error) => panic!("{kind} should be rejected, got {error}"),
        }
    }
    assert_eq!(run_count(path), 0);
    assert_eq!(user_version(path), 6);
    assert_eq!(deck_json(path, 2), before);

    let Err(Error::Input(text)) = ops::run_start(path, "image", &["p1".into()], None) else {
        panic!("frame should still be missing");
    };
    let snippet = text
        .split("payload.json 最小片段：\n")
        .nth(1)
        .expect("snippet");
    let saved = ops::put(path, 2, patch(serde_json::from_str(snippet).unwrap())).unwrap();
    assert_eq!(saved.deck.brief.title, "合成作品");
    assert_eq!(saved.deck.brief.goal, "保留目标");
    assert_eq!(saved.deck.framing.thesis, "保留主张");
    assert_eq!(saved.deck.brief.decision, "本周需拍板的事项");
    assert_eq!(user_version(path), 7);
    let started = ops::run_start(path, "image", &["p1".into()], None).unwrap();
    assert_eq!(started["runs"][0]["pages"][0]["status"], "pending");
    assert_eq!(run_count(path), 1);
    assert_eq!(saved.deck.pages[0].kind, "explanation");
    assert!(
        ops::put(
            path,
            saved.version,
            patch(json!({"pages":[{"id":"p1","notes":"仍可保存"}]}))
        )
        .is_ok()
    );
}

#[test]
fn snippet_for_only_a_missing_decision_keeps_the_rest_of_brief_and_framing() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    let created = ops::put(
        path,
        1,
        patch(json!({
            "brief": {
                "title": "合成作品",
                "goal": "保留目标",
                "audience": "已有读者",
                "concerns": ["已有关注"],
                "narrator": {"role": "已有角色", "tone": "已有语气"}
            },
            "framing": {
                "thesis": "保留主张",
                "pillars": [{"title": "范围", "points": ["先试点"]}],
                "storyline": ["已有主线"]
            },
            "order": ["p1"],
            "pages": [{"id": "p1", "content": {"title": "一页"}}]
        })),
    )
    .unwrap();
    let Err(Error::Input(text)) = ops::run_start(path, "image", &["p1".into()], None) else {
        panic!("decision should still be missing");
    };
    assert!(text.contains("- brief.decision"));
    assert!(!text.contains("- brief.audience"));
    assert!(text.contains("合成作品"));
    assert!(text.contains("保留目标"));
    assert!(text.contains("保留主张"));
    assert!(text.contains("已有读者"));
    assert!(text.contains("已有主线"));
    let snippet = text
        .split("payload.json 最小片段：\n")
        .nth(1)
        .expect("snippet");
    let saved = ops::put(
        path,
        created.version,
        patch(serde_json::from_str(snippet).unwrap()),
    )
    .unwrap();
    assert_eq!(saved.deck.brief.title, "合成作品");
    assert_eq!(saved.deck.brief.goal, "保留目标");
    assert_eq!(saved.deck.brief.audience, "已有读者");
    assert_eq!(saved.deck.brief.decision, "本周需拍板的事项");
    assert_eq!(saved.deck.framing.thesis, "保留主张");
    assert_eq!(saved.deck.framing.storyline, vec!["已有主线".to_string()]);
    assert_eq!(run_count(path), 0);
    assert!(ops::run_start(path, "image", &["p1".into()], None).is_ok());
}

#[test]
fn writing_brief_skips_blank_lines_and_outline_follows_page_order() {
    let deck = Deck {
        brief: Brief {
            title: "合成".into(),
            audience: " 业务负责人 ".into(),
            decision: "是否采用".into(),
            concerns: vec![" ".into(), "成本".into()],
            narrator: model::Narrator {
                role: "负责人".into(),
                tone: " ".into(),
            },
            ..Brief::default()
        },
        framing: Framing {
            storyline: vec!["先说明问题".into(), "  ".into(), "再给判断".into()],
            ..Framing::default()
        },
        pages: vec![
            Page {
                id: "p2".into(),
                kind: "reference".into(),
                content: deck::model::Content {
                    title: "查阅".into(),
                    ..Default::default()
                },
                ..Page::default()
            },
            Page {
                id: "p1".into(),
                content: deck::model::Content {
                    title: "封面".into(),
                    ..Default::default()
                },
                ..Page::default()
            },
        ],
        ..Deck::default()
    };
    let brief = model::writing_brief(&deck);
    assert_eq!(
        brief,
        "讲述人：负责人。\n待决事项：是否采用。\n读者关注点：\n- 成本"
    );
    assert!(!brief.contains("受众"));
    assert!(!brief.contains("故事线"));
    assert!(!brief.contains("先说明问题"));
    let mut both = deck.clone();
    both.brief.narrator.tone = "肯定".into();
    assert!(model::writing_brief(&both).starts_with("讲述人：负责人。语气：肯定。"));
    both.brief.narrator.role.clear();
    assert!(model::writing_brief(&both).starts_with("语气：肯定。"));
    both.brief.decision = "是否采用。".into();
    let decided = model::writing_brief(&both);
    assert!(decided.contains("待决事项：是否采用。"));
    assert!(!decided.contains("。。"));
    assert_eq!(
        model::outline(&deck.pages),
        json!([
            {"page_id":"p2","kind":"reference","title":"查阅"},
            {"page_id":"p1","kind":"","title":"封面"}
        ])
    );
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    ops::put(
        path,
        1,
        patch(json!({
            "brief": {
                "title":"合成作品",
                "audience":"业务负责人",
                "decision":"是否采用"
            },
            "order":["p1","p2"],
            "pages":[
                {"id":"p1","content":{"title":"封面"}},
                {"id":"p2","kind":"teaching","content":{"title":"讲解"}}
            ]
        })),
    )
    .unwrap();
    let got = ops::get(path, None).unwrap();
    assert_eq!(got["outline"][1]["kind"], "teaching");
    assert_eq!(got["outline"][0]["kind"], "");
    assert!(got["deck"].get("writing_brief").is_none());
    assert!(got["deck"].get("outline").is_none());
    let stored: Value =
        serde_json::from_str(&deck_json(path, got["version"].as_i64().unwrap())).unwrap();
    assert!(stored.get("writing_brief").is_none());
    let shown = ops::show(path).unwrap();
    assert_eq!(shown["outline"][0]["page_id"], "p1");
    assert_eq!(shown["writing_brief"], got["writing_brief"]);
    let partial = ops::get(path, Some(&["p2".into()])).unwrap();
    assert_eq!(
        partial["outline"],
        json!([{"page_id":"p2","kind":"teaching","title":"讲解"}])
    );
    let workspace = ops::workspace(path).unwrap();
    assert_eq!(workspace["writing_brief"], got["writing_brief"]);
    assert_eq!(workspace["outline"], got["outline"]);
}

#[test]
fn get_and_show_return_writing_brief_from_narrator_decision_and_concerns() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    ops::put(
        path,
        1,
        patch(json!({
            "brief": {
                "title": "合成作品",
                "audience": "业务负责人",
                "decision": "是否采用该方案",
                "concerns": ["成本是否可控", "  ", "口径是否一致"],
                "narrator": {"role": "资深顾问", "tone": "结论先行"}
            },
            "order": ["p1"],
            "pages": [{"id": "p1", "content": {"title": "封面"}}]
        })),
    )
    .unwrap();
    let expected = "讲述人：资深顾问。语气：结论先行。\n待决事项：是否采用该方案。\n读者关注点：\n- 成本是否可控\n- 口径是否一致";
    let got = ops::get(path, None).unwrap();
    let shown = ops::show(path).unwrap();
    assert_eq!(got["writing_brief"], expected);
    assert_eq!(shown["writing_brief"], expected);
    assert_eq!(
        ops::get(path, Some(&["p1".into()])).unwrap()["writing_brief"],
        expected
    );
    assert!(got["deck"].get("writing_brief").is_none());
    let stored: Value =
        serde_json::from_str(&deck_json(path, got["version"].as_i64().unwrap())).unwrap();
    assert!(stored.get("writing_brief").is_none());
    assert!(stored["brief"].get("writing_brief").is_none());
}

#[test]
fn argument_shape_is_checked_on_put_and_empty_evidence_is_stored() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    let created = ops::put(
        path,
        1,
        patch(json!({"order":["p1"],"pages":[{"id":"p1"}]})),
    )
    .unwrap();
    let bad = ops::put(
        path,
        created.version,
        patch(
            json!({"pages":[{"id":"p1","argument":{"evidence":[{"text":"一句","ref":"m1","gap":"缺数"}]}}]}),
        ),
    );
    assert!(matches!(bad, Err(Error::Input(_))));
    let missing = ops::put(
        path,
        created.version,
        patch(json!({"pages":[{"id":"p1","argument":{"evidence":[{"text":"一句"}]}}]})),
    )
    .unwrap();
    assert!(missing.deck.pages[0].argument.is_some());
    let blank_ref = ops::put(
        path,
        missing.version,
        patch(
            json!({"pages":[{"id":"p1","argument":{"evidence":[{"text":"一句","ref":"","gap":"缺数"}]}}]}),
        ),
    )
    .unwrap();
    assert_eq!(
        blank_ref.deck.pages[0].argument.as_ref().unwrap().evidence[0]
            .gap
            .as_deref(),
        Some("缺数")
    );
    let saved = ops::put(
        path,
        blank_ref.version,
        patch(json!({"pages":[{"id":"p1","argument":{
            "reasons":["因为范围已定"],
            "evidence":[{"text":"材料写了范围","ref":"m1"}],
            "reasoning":"所以先试点",
            "rebuttal":"范围仍可能变"
        }}]})),
    )
    .unwrap();
    let argument = saved.deck.pages[0].argument.as_ref().unwrap();
    assert_eq!(
        argument.evidence,
        vec![Evidence {
            text: "材料写了范围".into(),
            r#ref: Some("m1".into()),
            gap: None,
        }]
    );
    assert_eq!(argument.reasons, vec!["因为范围已定".to_string()]);
    let cleared = ops::put(
        path,
        saved.version,
        patch(json!({"pages":[{"id":"p1","argument":null}]})),
    )
    .unwrap();
    assert_eq!(cleared.deck.pages[0].argument, None);
    assert!(cleared.deck.pages[0].revision > saved.deck.pages[0].revision);
}

#[test]
fn new_project_is_format_7_and_put_does_not_require_the_frame() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    assert_eq!(user_version(path), 7);
    assert!(
        review_columns(path)
            .iter()
            .any(|name| name == "record_kind")
    );
    let saved = ops::put(
        path,
        1,
        patch(json!({"order":["p1"],"pages":[{"id":"p1","content":{"title":"一页"}}]})),
    )
    .unwrap();
    assert_eq!(saved.deck.pages[0].revision, 1);
    assert!(ops::build(path).is_err());
    assert_eq!(user_version(path), 7);
}
