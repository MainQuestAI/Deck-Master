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
            {"id":"p1","purpose":"说明交付","layout":"输入到输出","content":{"title":"交付"}},
            {"id":"p2","content":{"title":"下一步"}}
        ]}),
    );
}

fn bitmap(path: &Path, color: &str) {
    let output = Command::new(std::env::var_os("DECK_TOOLS_PYTHON").unwrap())
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
    store::append(&tx, &deck, "synthetic artifacts").unwrap();
    tx.commit().unwrap();
}

fn attached_run(path: &Path, kind: &str, expected: [Vec<&str>; 2]) -> i64 {
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
    for page in &deck.pages {
        for (kind, inputs) in [
            (
                "image",
                json!([page.content, page.layout, page.purpose, style]),
            ),
            (
                "svg",
                json!([page.content, page.image.as_ref().map(|i| &i.file), style]),
            ),
        ] {
            let original = format!("{:x}", Sha256::digest(serde_json::to_vec(&inputs).unwrap()));
            assert_eq!(ops::basis(kind, &deck, page).unwrap(), original);
        }
    }
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
fn scoped_stale_original_also_stales_svg_even_when_its_own_hash_matches() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let image = path.join("selected.png");
    bitmap(&image, "teal");
    seed_artifacts(path, &image);
    ops::asset_add(path, "selected-b", &image, &["p2".into()], "", "").unwrap();
    let mut store = Store::open(path).unwrap();
    let mut deck = store.current().unwrap().deck;
    // A current SVG hash alone must not hide an original made before this asset selection.
    deck.pages[1].svg.as_mut().unwrap().basis = ops::basis("svg", &deck, &deck.pages[1]).unwrap();
    let tx = store.transaction().unwrap();
    store::append(&tx, &deck, "synthetic current SVG basis").unwrap();
    tx.commit().unwrap();
    assert_stale(path, json!(["p2"]));
    let run = attached_run(path, "svg", [vec![], vec!["selected-b"]]);
    let pages = run_pages(path, run);
    assert_eq!(pages[0]["basis_changed"], false);
    assert_eq!(
        pages[1]["current_basis"],
        deck.pages[1].svg.as_ref().unwrap().basis
    );
    assert_eq!(pages[1]["basis_changed"], true);
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
fn cli_repeated_pages_and_metadata_replace_as_a_unit_and_missing_svg_tool_is_actionable() {
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
