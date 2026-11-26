use deck::{
    model::{Artifact, Asset},
    ops,
    store::{self, Store},
};
use serde_json::{Value, json};
use sha2::{Digest, Sha256};
use std::{path::Path, process::Command};

fn edit(path: &Path, patch: Value) {
    let version = Store::open(path).unwrap().current().unwrap().version;
    ops::put(path, version, serde_json::from_value(patch).unwrap()).unwrap();
}

fn setup(path: &Path) {
    ops::new(path, "合成素材测试".into()).unwrap();
    edit(
        path,
        json!({"order":["p1","p2"],"pages":[
            {"id":"p1","purpose":"说明交付","layout":"输入到输出","kind":"explanation","content":{"title":"交付"}},
            {"id":"p2","purpose":"说明下一步","layout":"单栏","kind":"explanation","content":{"title":"下一步"}}
        ]}),
    );
}

fn bitmap(path: &Path, color: &str) {
    let python = std::env::var_os("DECK_TOOLS_PYTHON").expect(
        "DECK_TOOLS_PYTHON must be set to this worktree's .venv/bin/python (see AGENTS.md §3)",
    );
    let output = Command::new(python)
        .args(["-c", "from PIL import Image; import sys; Image.new('RGB',(1,1),sys.argv[2]).save(sys.argv[1])"])
        .arg(path)
        .arg(color)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
}

fn seed_artifacts(path: &Path, image: &Path) {
    let mut store = Store::open(path).unwrap();
    let mut deck = store.current().unwrap().deck;
    let image = store
        .add_file(&std::fs::read(image).unwrap(), "png")
        .unwrap();
    let svg = store
        .add_file(
            b"<svg xmlns='http://www.w3.org/2000/svg' width='1' height='1'/>",
            "svg",
        )
        .unwrap();
    for i in 0..deck.pages.len() {
        deck.pages[i].image = Some(Artifact {
            file: image.clone(),
            basis: ops::basis("image", &deck, &deck.pages[i]).unwrap(),
        });
        deck.pages[i].svg = Some(Artifact {
            file: svg.clone(),
            basis: ops::basis("svg", &deck, &deck.pages[i]).unwrap(),
        });
    }
    let tx = store.transaction().unwrap();
    store::append(&tx, &mut deck, "synthetic artifacts").unwrap();
    tx.commit().unwrap();
}

fn allow_runs(path: &Path) {
    let store = Store::open(path).unwrap();
    let snapshot = store.current().unwrap();
    let mut deck = snapshot.deck;
    let mut changed = false;
    if deck.brief.audience.trim().is_empty() {
        deck.brief.audience = "业务负责人".into();
        changed = true;
    }
    if deck.brief.decision.trim().is_empty() {
        deck.brief.decision = "是否采用该方案".into();
        changed = true;
    }
    if deck
        .brief
        .concerns
        .iter()
        .all(|item| item.trim().is_empty())
    {
        deck.brief.concerns = vec!["成本是否可控".into()];
        changed = true;
    }
    if deck.brief.narrator.role.trim().is_empty() {
        deck.brief.narrator.role = "项目负责人".into();
        changed = true;
    }
    if deck.brief.narrator.tone.trim().is_empty() {
        deck.brief.narrator.tone = "直接说明判断".into();
        changed = true;
    }
    if deck
        .framing
        .storyline
        .iter()
        .all(|item| item.trim().is_empty())
    {
        deck.framing.storyline = vec!["先说明问题，再给出判断".into()];
        changed = true;
    }
    // Fill generation-required page fields for non-gate asset fixtures.
    for page in &mut deck.pages {
        if page.content.title.trim().is_empty() {
            page.content.title = format!("{} 标题", page.id);
            changed = true;
        }
        if page.purpose.trim().is_empty() {
            page.purpose = format!("说明 {}", page.id);
            changed = true;
        }
        if page.layout.trim().is_empty() {
            page.layout = "左右分栏".into();
            changed = true;
        }
        if page.kind.trim().is_empty() {
            page.kind = "explanation".into();
            changed = true;
        }
    }
    if changed {
        store
            .connection
            .execute(
                "UPDATE versions SET deck_json=?1 WHERE id=?2",
                rusqlite::params![serde_json::to_string(&deck).unwrap(), snapshot.version],
            )
            .unwrap();
    }
}

fn attached_run(path: &Path, kind: &str, expected: [Vec<&str>; 2]) -> i64 {
    allow_runs(path);
    let result = ops::run_start(path, kind, &["p1".into(), "p2".into()], None).unwrap();
    let store = Store::open(path).unwrap();
    let style = store.current().unwrap().deck.style;
    for (i, page) in result["runs"][0]["pages"]
        .as_array()
        .unwrap()
        .iter()
        .enumerate()
    {
        let work = Path::new(page["work"].as_str().unwrap());
        let attachments: Vec<Value> =
            serde_json::from_slice(&std::fs::read(work.join("attachments.json")).unwrap()).unwrap();
        let mut ids: Vec<_> = attachments
            .iter()
            .filter_map(|a| a["id"].as_str())
            .collect();
        ids.sort();
        assert_eq!(ids, expected[i]);
        let mut files: Vec<_> = attachments
            .iter()
            .filter(|a| a["id"].is_string())
            .map(|a| a["file"].as_str().unwrap())
            .collect();
        files.sort();
        files.dedup();
        let copied: Vec<_> = std::fs::read_dir(work)
            .unwrap()
            .map(|e| e.unwrap().file_name().to_string_lossy().into_owned())
            .filter(|name| name.starts_with("asset-"))
            .collect();
        assert_eq!(files.len(), copied.len());
        for file in &copied {
            assert!(files.contains(&file.as_str()));
        }
        for attachment in attachments.iter().filter(|a| a["id"].is_string()) {
            let asset = style
                .assets
                .iter()
                .find(|a| a.id == attachment["id"].as_str().unwrap())
                .unwrap();
            assert_eq!(
                std::fs::read(work.join(attachment["file"].as_str().unwrap())).unwrap(),
                std::fs::read(store.file(&asset.file).unwrap()).unwrap()
            );
        }
        let supplied_style: Value =
            serde_json::from_slice(&std::fs::read(work.join("style.json")).unwrap()).unwrap();
        assert_eq!(supplied_style, serde_json::to_value(&style).unwrap());
        let task = std::fs::read_to_string(work.join("task.md")).unwrap();
        assert!(task.contains("attachments.json"));
        for asset in &style.assets {
            assert!(!task.contains(&asset.id));
        }
    }
    let id = result["runs"][0]["id"].as_i64().unwrap();
    ops::run_cancel(path, id).unwrap();
    id
}

fn run_pages(path: &Path, run: i64) -> Value {
    ops::run_show(path, Some(run)).unwrap()["runs"][0]["pages"].clone()
}

fn assert_stale(path: &Path, expected: Value) {
    let status = ops::get(path, None).unwrap()["artifact_status"].clone();
    assert_eq!(status["stale_images"], expected);
    assert_eq!(status["stale_pages"], expected);
}

#[test]
fn legacy_asset_payload_round_trips_and_public_style_keeps_both_hash_formulas() {
    let payload = r#"{"id":"legacy","file":"selected.png"}"#;
    let asset: Asset = serde_json::from_str(payload).unwrap();
    assert!(asset.pages.is_empty());
    assert!(asset.source.is_empty());
    assert!(asset.license.is_empty());
    assert_eq!(serde_json::to_string(&asset).unwrap(), payload);
    let temp = tempfile::tempdir().unwrap();
    setup(temp.path());
    let input = temp.path().join("selected.png");
    bitmap(&input, "teal");
    let file = Store::open(temp.path())
        .unwrap()
        .add_file(&std::fs::read(input).unwrap(), "png")
        .unwrap();
    let mut style = ops::get(temp.path(), None).unwrap()["deck"]["style"].clone();
    style["assets"] = json!([
        {"id":asset.id,"file":file},
        {"id":"modern-public","file":file,"source":"synthetic","license":"CC0"}]);
    edit(temp.path(), json!({"style":style}));
    let mut deck = Store::open(temp.path()).unwrap().current().unwrap().deck;
    deck.pages[0].image = Some(Artifact {
        file: "original.png".into(),
        basis: "unused".into(),
    });
    let mut reordered = deck.clone();
    reordered.style.assets.reverse();
    let mut stripped = deck.clone();
    for asset in &mut stripped.style.assets {
        asset.source.clear();
        asset.license.clear();
    }
    for page in &deck.pages {
        let image_basis = ops::basis("image", &deck, page).unwrap();
        let svg_basis = ops::basis("svg", &deck, page).unwrap();
        assert!(image_basis.starts_with("img-v2:"));
        assert!(svg_basis.starts_with("svg-v3:"));
        assert_eq!(ops::basis("image", &reordered, page).unwrap(), image_basis);
        assert_eq!(ops::basis("svg", &reordered, page).unwrap(), svg_basis);
        assert_eq!(ops::basis("image", &stripped, page).unwrap(), image_basis);
        assert_eq!(ops::basis("svg", &stripped, page).unwrap(), svg_basis);
    }
    // Verify legacy svg-v2 basis stored on deck stays non-stale under current explicit contract.
    let legacy_svg_v2 = format!(
        "svg-v2:{:x}",
        Sha256::digest(
            serde_json::to_vec(&json!([
                deck.pages[0].content,
                deck.pages[0].purpose,
                deck.pages[0].layout,
                deck.pages[0].image.as_ref().map(|i| &i.file),
                stripped.style
            ]))
            .unwrap()
        )
    );
    deck.pages[0].svg = Some(Artifact {
        file: "legacy-v2.svg".into(),
        basis: legacy_svg_v2,
    });
    assert_eq!(
        ops::artifact_status(&deck).unwrap()["stale_pages"],
        json!([])
    );
}

#[test]
fn asset_metadata_and_extra_page_binding_do_not_stale_existing_bound_page() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成素材元数据测试".into()).unwrap();
    edit(
        path,
        json!({"order":["p1","p2","p3"],"pages":[
            {"id":"p1","purpose":"说明交付","layout":"输入到输出","kind":"explanation","content":{"title":"交付"}},
            {"id":"p2","purpose":"说明中段","layout":"单栏","kind":"explanation","content":{"title":"中段"}},
            {"id":"p3","purpose":"说明收尾","layout":"单栏","kind":"explanation","content":{"title":"收尾"}}
        ]}),
    );
    let logo = path.join("logo.png");
    let generated = path.join("generated.png");
    bitmap(&logo, "teal");
    bitmap(&generated, "navy");
    ops::asset_add(path, "logo", &logo, &["p1".into()], "source-a", "MIT").unwrap();
    seed_artifacts(path, &logo);
    allow_runs(path);

    let before_deck = Store::open(path).unwrap().current().unwrap().deck;
    let p1_image_before = ops::basis("image", &before_deck, &before_deck.pages[0]).unwrap();
    let p1_svg_before = ops::basis("svg", &before_deck, &before_deck.pages[0]).unwrap();

    // Start an open image run for p1 before changing metadata and adding p3.
    let run = ops::run_start(path, "image", &["p1".into()], None).unwrap();
    let run_id = run["runs"][0]["id"].as_i64().unwrap();

    ops::asset_add(
        path,
        "logo",
        &logo,
        &["p1".into(), "p3".into()],
        "source-b",
        "CC0",
    )
    .unwrap();

    let after_deck = Store::open(path).unwrap().current().unwrap().deck;
    assert_eq!(
        ops::basis("image", &after_deck, &after_deck.pages[0]).unwrap(),
        p1_image_before
    );
    assert_eq!(
        ops::basis("svg", &after_deck, &after_deck.pages[0]).unwrap(),
        p1_svg_before
    );
    assert_stale(path, json!(["p3"]));

    // Because p1's effective asset file did not change, the in-flight run still auto-adopts.
    let result = ops::run_result(path, run_id, "p1", &generated).unwrap();
    assert_eq!(result["adopted"], true);
}

#[test]
fn legacy_public_add_and_replace_attach_to_all_pages_and_change_both_bases() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let image = path.join("selected.png");
    bitmap(&image, "teal");
    seed_artifacts(path, &image);
    let runs = [
        attached_run(path, "image", [vec![], vec![]]),
        attached_run(path, "svg", [vec![], vec![]]),
    ];
    let before = runs.map(|id| run_pages(path, id));
    ops::asset_add(path, "public-mark", &image, &[], "", "").unwrap();
    assert_stale(path, json!(["p1", "p2"]));
    for (index, id) in runs.into_iter().enumerate() {
        let after = run_pages(path, id);
        for page in 0..2 {
            assert_ne!(
                after[page]["current_basis"],
                before[index][page]["current_basis"]
            );
            assert_eq!(after[page]["basis_changed"], true);
        }
    }
    for kind in ["image", "svg"] {
        attached_run(path, kind, [vec!["public-mark"], vec!["public-mark"]]);
    }
    seed_artifacts(path, &image);
    let before = Store::open(path).unwrap().current().unwrap().deck;
    bitmap(&image, "navy");
    ops::asset_add(path, "public-mark", &image, &[], "", "").unwrap();
    let after = Store::open(path).unwrap().current().unwrap().deck;
    for index in 0..2 {
        for kind in ["image", "svg"] {
            assert_ne!(
                ops::basis(kind, &before, &before.pages[index]).unwrap(),
                ops::basis(kind, &after, &after.pages[index]).unwrap()
            );
        }
    }
    assert_stale(path, json!(["p1", "p2"]));
}

#[test]
fn scoped_add_replace_and_notes_preserve_unaffected_page_and_public_assets_join_both() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let a = path.join("a.png");
    let b = path.join("b.png");
    bitmap(&a, "teal");
    bitmap(&b, "navy");
    ops::asset_add(path, "selected-a", &a, &["p1".into()], "synthetic-a", "CC0").unwrap();
    seed_artifacts(path, &a);
    let runs = [
        attached_run(path, "image", [vec!["selected-a"], vec![]]),
        attached_run(path, "svg", [vec!["selected-a"], vec![]]),
    ];
    let before = runs.map(|id| run_pages(path, id));
    edit(
        path,
        json!({"pages":[{"id":"p1","notes":"只改讲稿"},{"id":"p2","notes":"另一页讲稿"}]}),
    );
    assert_stale(path, json!([]));
    for (index, run) in runs.into_iter().enumerate() {
        assert_eq!(run_pages(path, run), before[index]);
    }
    for color in ["navy", "orange"] {
        let previous = runs.map(|id| run_pages(path, id));
        bitmap(&b, color);
        ops::asset_add(path, "selected-b", &b, &["p2".into()], "synthetic-b", "CC0").unwrap();
        assert_stale(path, json!(["p2"]));
        for (index, run) in runs.into_iter().enumerate() {
            let after = run_pages(path, run);
            assert_eq!(after[0]["current_basis"], before[index][0]["current_basis"]);
            assert_eq!(after[0]["basis_changed"], false);
            assert_ne!(after[1]["current_basis"], before[index][1]["current_basis"]);
            assert_ne!(
                after[1]["current_basis"],
                previous[index][1]["current_basis"]
            );
            assert_eq!(after[1]["basis_changed"], true);
        }
        for kind in ["image", "svg"] {
            attached_run(path, kind, [vec!["selected-a"], vec!["selected-b"]]);
        }
    }
    ops::asset_add(path, "public-mark", &a, &[], "", "").unwrap();
    for kind in ["image", "svg"] {
        attached_run(
            path,
            kind,
            [
                vec!["public-mark", "selected-a"],
                vec!["public-mark", "selected-b"],
            ],
        );
    }
    assert_stale(path, json!(["p1", "p2"]));
}

#[test]
fn scoped_stale_original_is_separate_from_current_svg() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let image = path.join("selected.png");
    bitmap(&image, "teal");
    seed_artifacts(path, &image);
    ops::asset_add(path, "selected-b", &image, &["p2".into()], "", "").unwrap();
    let mut store = Store::open(path).unwrap();
    let mut deck = store.current().unwrap().deck;
    // A rebuilt SVG is current even when the retained original has stale inputs.
    deck.pages[1].svg.as_mut().unwrap().basis = ops::basis("svg", &deck, &deck.pages[1]).unwrap();
    let tx = store.transaction().unwrap();
    store::append(&tx, &mut deck, "synthetic current SVG basis").unwrap();
    tx.commit().unwrap();
    let status = ops::artifact_status(&deck).unwrap();
    assert_eq!(status["stale_images"], json!(["p2"]));
    assert_eq!(status["stale_pages"], json!([]));
    let run = attached_run(path, "svg", [vec![], vec!["selected-b"]]);
    let pages = run_pages(path, run);
    assert_eq!(pages[0]["basis_changed"], false);
    assert_eq!(
        pages[1]["current_basis"],
        deck.pages[1].svg.as_ref().unwrap().basis
    );
    assert_eq!(pages[1]["basis_changed"], false);
}

#[test]
fn svg_registration_produces_decodable_png_or_reports_missing_renderer_and_never_keeps_svg() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let input = path.join("icon.SVG");
    std::fs::write(&input, "<svg xmlns='http://www.w3.org/2000/svg' width='2' height='2'><rect width='2' height='2' fill='teal'/></svg>").unwrap();
    match ops::asset_add(
        path,
        "rendered-icon",
        &input,
        &["p1".into()],
        "synthetic",
        "CC0",
    ) {
        Ok(result) => {
            let file = result["asset"]["file"].as_str().unwrap();
            assert!(file.ends_with(".png"));
            let store = Store::open(path).unwrap();
            let output = Command::new(std::env::var_os("DECK_TOOLS_PYTHON").unwrap())
                .args(["-c", "from PIL import Image; import sys; im=Image.open(sys.argv[1]); assert im.format=='PNG'; im.load(); assert im.size==(2,2)"])
                .arg(store.file(file).unwrap()).output().unwrap();
            assert!(
                output.status.success(),
                "{}",
                String::from_utf8_lossy(&output.stderr)
            );
            attached_run(path, "image", [vec!["rendered-icon"], vec![]]);
        }
        Err(deck::error::Error::NeedsTool(message)) => {
            assert!(message.contains("rsvg-convert"));
            assert!(
                Store::open(path)
                    .unwrap()
                    .current()
                    .unwrap()
                    .deck
                    .style
                    .assets
                    .is_empty()
            );
        }
        Err(error) => panic!("{error}"),
    }
    let before = ops::get(path, None).unwrap();
    std::fs::write(&input, "not SVG").unwrap();
    let error = ops::asset_add(path, "broken-icon", &input, &[], "", "").unwrap_err();
    assert!(matches!(
        error,
        deck::error::Error::Tool(_) | deck::error::Error::NeedsTool(_)
    ));
    assert_eq!(ops::get(path, None).unwrap(), before);
}

#[test]
fn comma_separated_asset_pages_apply_to_each_page_and_unknown_pages_do_not_replace() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let image = path.join("selected.png");
    bitmap(&image, "teal");
    for pages in [
        vec!["p1,p2".into()],
        vec![" p1, p2,".into(), "p1".into(), " , ".into()],
        vec!["p1,".into(), "p2,p2".into()],
    ] {
        let value = ops::asset_add(path, "selected", &image, &pages, "", "").unwrap();
        assert_eq!(value["asset"]["pages"], json!(["p1", "p2"]));
    }
    attached_run(path, "image", [vec!["selected"], vec!["selected"]]);
    let before = ops::get(path, None).unwrap();
    for pages in [
        vec!["p1,unknown".into()],
        vec!["p1".into(), "unknown".into()],
    ] {
        let error = ops::asset_add(path, "selected", &image, &pages, "changed", "").unwrap_err();
        assert!(matches!(error, deck::error::Error::Input(_)));
        assert!(error.to_string().contains("unknown"));
        assert!(error.to_string().contains("deck show"));
        assert_eq!(ops::get(path, None).unwrap(), before);
    }
}

#[test]
fn cli_empty_page_segments_fail_while_trailing_comma_and_absent_page_keep_scope() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let image = path.join("selected.png");
    bitmap(&image, "teal");
    let before = ops::get(path, None).unwrap();
    for pages in [",", " , "] {
        let output = Command::new(env!("CARGO_BIN_EXE_deck"))
            .arg("--project")
            .arg(path)
            .args(["asset", "add", "selected"])
            .arg(&image)
            .args(["--page", pages])
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(2), "page scope: {pages:?}");
        assert!(!output.stderr.is_empty());
        assert_eq!(ops::get(path, None).unwrap(), before);
        assert_eq!(
            std::fs::read_dir(path.join(".deck/files")).unwrap().count(),
            0
        );
    }
    for (args, expected) in [(vec!["--page", "p1,"], vec!["p1"]), (vec![], vec![])] {
        let output = Command::new(env!("CARGO_BIN_EXE_deck"))
            .arg("--project")
            .arg(path)
            .args(["asset", "add", "selected"])
            .arg(&image)
            .args(args)
            .output()
            .unwrap();
        assert!(
            output.status.success(),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        let value: Value = serde_json::from_slice(&output.stdout).unwrap();
        let asset: Asset = serde_json::from_value(value["asset"].clone()).unwrap();
        assert_eq!(asset.pages, expected);
        assert_eq!(
            Store::open(path)
                .unwrap()
                .current()
                .unwrap()
                .deck
                .style
                .assets,
            vec![asset]
        );
    }
}

#[test]
fn cli_comma_and_repeated_pages_replace_as_a_unit_and_missing_svg_tool_is_actionable() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let image = path.join("selected.png");
    bitmap(&image, "teal");
    let output = Command::new(env!("CARGO_BIN_EXE_deck"))
        .arg("--project")
        .arg(path)
        .args(["asset", "add", "selected-icon"])
        .arg(&image)
        .args([
            "--page",
            "p1",
            "--page",
            "p2",
            "--source",
            "synthetic",
            "--license",
            "CC0",
        ])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let value: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(value["asset"]["pages"], json!(["p1", "p2"]));
    assert_eq!(value["asset"]["source"], "synthetic");
    assert_eq!(value["asset"]["license"], "CC0");
    edit(
        path,
        json!({"order":["p1","p2","p3"],"pages":[{"id":"p3"}]}),
    );
    for (args, pages) in [
        (vec!["--page", "p1,p2"], json!(["p1", "p2"])),
        (vec!["--page", "p1", "--page", "p2"], json!(["p1", "p2"])),
        (
            vec!["--page", "p1,p2", "--page", "p3"],
            json!(["p1", "p2", "p3"]),
        ),
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_deck"))
            .arg("--project")
            .arg(path)
            .args(["asset", "add", "selected-icon"])
            .arg(&image)
            .args(args)
            .output()
            .unwrap();
        assert!(output.status.success());
        let value: Value = serde_json::from_slice(&output.stdout).unwrap();
        assert_eq!(value["asset"]["pages"], pages);
    }
    let before = ops::get(path, None).unwrap();
    for args in [
        vec!["--page", "p1,unknown"],
        vec!["--page", "p1", "--page", "unknown"],
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_deck"))
            .arg("--project")
            .arg(path)
            .args(["asset", "add", "selected-icon"])
            .arg(&image)
            .args(args)
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(2));
        let message = String::from_utf8_lossy(&output.stderr);
        assert!(message.contains("unknown"));
        assert!(message.contains("deck show"));
        assert_eq!(ops::get(path, None).unwrap(), before);
    }
    let output = Command::new(env!("CARGO_BIN_EXE_deck"))
        .arg("--project")
        .arg(path)
        .args(["asset", "add", "selected-icon"])
        .arg(&image)
        .output()
        .unwrap();
    assert!(output.status.success());
    let replaced: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(
        replaced["asset"],
        json!({"id":"selected-icon","file":value["asset"]["file"]})
    );
    assert_eq!(
        Store::open(path)
            .unwrap()
            .current()
            .unwrap()
            .deck
            .style
            .assets
            .len(),
        1
    );
    let input = path.join("icon.svg");
    std::fs::write(
        &input,
        "<svg xmlns='http://www.w3.org/2000/svg' width='1' height='1'/>",
    )
    .unwrap();
    let empty_path = path.join("empty-bin");
    std::fs::create_dir(&empty_path).unwrap();
    let before = ops::get(path, None).unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_deck"))
        .arg("--project")
        .arg(path)
        .args(["asset", "add", "missing-renderer"])
        .arg(&input)
        .env("PATH", empty_path)
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(3));
    assert!(String::from_utf8_lossy(&output.stderr).contains("rsvg-convert"));
    assert_eq!(ops::get(path, None).unwrap(), before);
}

#[test]
fn png_and_jpeg_registration_preserve_original_bytes() {
    let temp = tempfile::tempdir().unwrap();
    setup(temp.path());
    let store = Store::open(temp.path()).unwrap();
    for ext in ["png", "jpeg"] {
        let input = temp.path().join(format!("selected.{ext}"));
        bitmap(&input, "teal");
        let result = ops::asset_add(temp.path(), ext, &input, &[], "", "").unwrap();
        let file = result["asset"]["file"].as_str().unwrap();
        assert!(file.ends_with(ext));
        assert_eq!(
            std::fs::read(store.file(file).unwrap()).unwrap(),
            std::fs::read(input).unwrap()
        );
    }
}

#[test]
fn unknown_asset_pages_leave_no_files_or_conversion() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let before = ops::get(path, None).unwrap();
    let files = path.join(".deck/files");
    let before_files: Vec<_> = std::fs::read_dir(&files)
        .unwrap()
        .map(|e| e.unwrap().file_name())
        .collect();
    let image = path.join("selected.png");
    bitmap(&image, "teal");
    let output = Command::new(env!("CARGO_BIN_EXE_deck"))
        .arg("--project")
        .arg(path)
        .args(["asset", "add", "unknown-page"])
        .arg(&image)
        .args(["--page", "p1, unknown"])
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&output.stderr).contains("unknown"));
    assert_eq!(ops::get(path, None).unwrap(), before);
    let after_files: Vec<_> = std::fs::read_dir(&files)
        .unwrap()
        .map(|e| e.unwrap().file_name())
        .collect();
    assert_eq!(after_files, before_files);

    // A converter that would fail proves preflight wins over external work.
    let bin = path.join("bin");
    std::fs::create_dir(&bin).unwrap();
    let marker = path.join("converted");
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        let converter = bin.join("rsvg-convert");
        std::fs::write(
            &converter,
            "#!/bin/sh\nprintf called > \"$DECK_TEST_MARKER\"\nexit 42\n",
        )
        .unwrap();
        std::fs::set_permissions(&converter, std::fs::Permissions::from_mode(0o755)).unwrap();
    }
    let svg = path.join("icon.svg");
    std::fs::write(&svg, "<svg xmlns='http://www.w3.org/2000/svg'/>").unwrap();
    let output = Command::new(env!("CARGO_BIN_EXE_deck"))
        .arg("--project")
        .arg(path)
        .args(["asset", "add", "unknown-svg"])
        .arg(&svg)
        .args(["--page", "unknown"])
        .env("PATH", &bin)
        .env("DECK_TEST_MARKER", &marker)
        .output()
        .unwrap();
    assert_eq!(output.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&output.stderr).contains("unknown"));
    assert!(!marker.exists());
    assert_eq!(ops::get(path, None).unwrap(), before);
    let after_files: Vec<_> = std::fs::read_dir(&files)
        .unwrap()
        .map(|e| e.unwrap().file_name())
        .collect();
    assert_eq!(after_files, before_files);
}

#[cfg(unix)]
#[test]
fn asset_registration_rechecks_pages_deleted_during_conversion() {
    use std::os::unix::fs::PermissionsExt;
    for existing in ["new", "preexisting", "shared"] {
        let temp = tempfile::tempdir().unwrap();
        let path = temp.path();
        setup(path);
        let patch = path.join("remove.json");
        std::fs::write(&patch, r#"{"order":["p1"],"pages":[{"id":"p2"}]}"#).unwrap();
        let image = path.join("selected.png");
        bitmap(&image, "teal");
        if existing == "preexisting" {
            Store::open(path)
                .unwrap()
                .add_file(&std::fs::read(&image).unwrap(), "png")
                .unwrap();
        } else if existing == "shared" {
            for id in ["shared-a", "shared-b"] {
                ops::asset_add(path, id, &image, &[], "", "").unwrap();
            }
        }
        let snapshot_before = Store::open(path).unwrap().current().unwrap();
        let before = snapshot_before.version;
        let file_contents = || {
            std::fs::read_dir(path.join(".deck/files"))
                .unwrap()
                .map(|entry| {
                    let entry = entry.unwrap();
                    (entry.file_name(), std::fs::read(entry.path()).unwrap())
                })
                .collect::<std::collections::BTreeMap<_, _>>()
        };
        let before_files = file_contents();
        let svg = path.join("icon.svg");
        std::fs::write(&svg, "<svg xmlns='http://www.w3.org/2000/svg'/>").unwrap();
        let bin = path.join("bin");
        std::fs::create_dir(&bin).unwrap();
        let converter = bin.join("rsvg-convert");
        // Remove the preflighted page through a second process before returning PNG bytes.
        std::fs::write(&converter, "#!/bin/sh\n\"$DECK_TEST_BIN\" --project \"$DECK_TEST_PROJECT\" put --base \"$DECK_TEST_BASE\" \"$DECK_TEST_PATCH\" >/dev/null || exit 1\n/bin/cat \"$DECK_TEST_IMAGE\"\n").unwrap();
        std::fs::set_permissions(&converter, std::fs::Permissions::from_mode(0o755)).unwrap();
        let output = Command::new(env!("CARGO_BIN_EXE_deck"))
            .arg("--project")
            .arg(path)
            .args(["asset", "add", "raced-icon"])
            .arg(&svg)
            .args(["--page", "p2"])
            .env("PATH", &bin)
            .env("DECK_TEST_BIN", env!("CARGO_BIN_EXE_deck"))
            .env("DECK_TEST_PROJECT", path)
            .env("DECK_TEST_BASE", before.to_string())
            .env("DECK_TEST_PATCH", &patch)
            .env("DECK_TEST_IMAGE", &image)
            .output()
            .unwrap();
        assert_eq!(
            output.status.code(),
            Some(2),
            "{}",
            String::from_utf8_lossy(&output.stderr)
        );
        assert!(String::from_utf8_lossy(&output.stderr).contains("p2"));
        let snapshot = Store::open(path).unwrap().current().unwrap();
        assert_eq!(snapshot.deck.pages.len(), 1);
        assert_eq!(
            snapshot.deck.style.assets,
            snapshot_before.deck.style.assets
        );
        assert_eq!(snapshot.version, before + 1);
        assert_eq!(
            file_contents(),
            before_files,
            "existing content: {existing}"
        );
    }
}

#[test]
fn exif_rotated_jpeg_asset_is_transposed_at_intake_and_passes_export_sanitize() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let rotated = path.join("portrait.jpg");
    // Create a 20x10 JPEG with EXIF Orientation=6 (90 deg CW -> visual 10x20).
    let output = Command::new(std::env::var_os("DECK_TOOLS_PYTHON").unwrap())
        .args([
            "-c",
            "from PIL import Image; import sys; im=Image.new('RGB',(20,10),'teal'); ex=im.getexif(); ex[274]=6; im.save(sys.argv[1], format='JPEG', exif=ex.tobytes())",
        ])
        .arg(&rotated)
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );

    let added = ops::asset_add(path, "portrait", &rotated, &["p1".into()], "", "").unwrap();
    let stored_name = added["asset"]["file"].as_str().unwrap();
    let stored_path = Store::open(path).unwrap().file(stored_name).unwrap();

    // Verify pixels were transposed to 10x20, orientation is 1, and sanitize accepts it.
    let verify = Command::new(std::env::var_os("DECK_TOOLS_PYTHON").unwrap())
        .args([
            "-c",
            "from PIL import Image; from pathlib import Path; import sys; from deck_tools.sanitize import jpeg; p=Path(sys.argv[1]); im=Image.open(p); assert im.size==(10,20), im.size; assert im.getexif().get(274,1)==1; cleaned=jpeg(p.read_bytes(),'portrait.jpg'); assert cleaned.startswith(b'\\xff\\xd8')",
        ])
        .arg(&stored_path)
        .output()
        .unwrap();
    assert!(
        verify.status.success(),
        "{}",
        String::from_utf8_lossy(&verify.stderr)
    );
}
