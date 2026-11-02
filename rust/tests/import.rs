use deck::ops;
use serde_json::{Value, json};
use std::fs;
use std::path::Path;
use std::process::Command;

fn pptx_fixture(action: &str, path: &Path, variant: &str) -> Value {
    let output = Command::new(std::env::var_os("DECK_TOOLS_PYTHON").expect("install deck-tools"))
        .arg(
            Path::new(env!("CARGO_MANIFEST_DIR"))
                .join("../deck-tools/tests/legacy_pptx_fixture.py"),
        )
        .args([action, path.to_str().unwrap(), variant])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    if action == "inspect" {
        serde_json::from_slice(&output.stdout).unwrap()
    } else {
        Value::Null
    }
}

fn write_file(root: &Path, name: &str, data: &[u8]) {
    fs::create_dir_all(root.join("files")).unwrap();
    fs::write(root.join("files").join(name), data).unwrap();
}

fn archive(root: &Path) -> Value {
    write_file(root, "material.txt", b"synthetic material\n");
    write_file(root, "page.png", b"\x89PNG\r\n\x1a\nsynthetic");
    write_file(
        root,
        "page.svg",
        b"<svg xmlns=\"http://www.w3.org/2000/svg\"></svg>",
    );
    pptx_fixture("make", &root.join("files/deck.pptx"), "metadata");
    json!({
        "format": "legacy-export.v1",
        "source": {"project_id": "synthetic-export", "revision_id": "rev-1"},
        "brief": {
            "title": "合成导入",
            "audience": "测试读者",
            "task_type": "首提",
            "goal": "说明导入",
            "constraints": ["只用合成材料"],
            "page_limit": null
        },
        "materials": [{
            "id": "s1",
            "name": "material.txt",
            "file": "material.txt",
            "text_file": "material.txt",
            "status": "read"
        }],
        "framing": {
            "thesis": "先导入再改稿",
            "pillars": [{"title": "材料保留", "points": ["原文进 files"]}],
            "facts": [],
            "assumptions": [],
            "questions": ["待补一项"]
        },
        "style": {
            "canvas": {
                "width_px": 1600,
                "height_px": 900,
                "slide_width_in": 13.333,
                "slide_height_in": 7.5
            },
            "palette": ["#FFFFFF", "#14213D"],
            "fonts": ["Noto Sans CJK SC"],
            "assets": []
        },
        "pages": [{
            "id": "p1",
            "purpose": "说明材料如何进入正文",
            "layout": "先结论后材料",
            "content": {
                "title": "合成页标题",
                "subtitle": "副题",
                "body_blocks": [{"type": "paragraph", "id": "b1", "text": "合成正文"}],
                "labels": [],
                "footnotes": [],
                "callouts": []
            },
            "notes": "合成讲稿",
            "todo": ["待补一项"],
            "refs": ["s1 L1"],
            "image": {"file": "page.png"},
            "svg": {"file": "page.svg"},
            "preview": null
        }],
        "last_export": {"file": "deck.pptx"},
        "reviews": [{"review_id": "rev-synth", "kind": "content", "status": "fail"}],
        "authorizations": [{"authorization_id": "auth-synth", "status": "active"}],
        "open_calls": [{
            "task_id": "task-synth",
            "allowance_id": "call-1",
            "state": "in_flight",
            "kind": "blueprint"
        }],
        "unmapped": [{
            "kind": "visual_spec",
            "id": "p1",
            "reason": "页上关系图不映射到新作品"
        }]
    })
}

fn write_archive(root: &Path) {
    let manifest = archive(root);
    fs::write(
        root.join("manifest.json"),
        serde_json::to_vec_pretty(&manifest).unwrap(),
    )
    .unwrap();
}

#[test]
fn import_maps_archive_and_lists_unmapped_and_open_calls() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("archive");
    fs::create_dir(&source).unwrap();
    write_archive(&source);
    let dest = temp.path().join("new-deck");
    let report = ops::import(&source, &dest).unwrap();
    assert_eq!(report["pages"], 1);
    assert_eq!(report["materials"], 1);
    assert_eq!(report["last_export"], true);
    assert_eq!(report["open_calls"][0]["state"], "in_flight");
    let kinds: Vec<_> = report["unmapped"]
        .as_array()
        .unwrap()
        .iter()
        .map(|item| item["kind"].as_str().unwrap())
        .collect();
    assert!(kinds.contains(&"visual_spec"));
    assert!(kinds.contains(&"review"));
    assert!(kinds.contains(&"authorization"));
    let snapshot = ops::get(&dest, None).unwrap();
    assert_eq!(snapshot["deck"]["brief"]["title"], "合成导入");
    assert_eq!(snapshot["deck"]["framing"]["thesis"], "先导入再改稿");
    assert_eq!(snapshot["deck"]["style"]["canvas"]["width_px"], 1600);
    assert_eq!(snapshot["deck"]["style"]["canvas"]["height_px"], 900);
    assert_eq!(
        snapshot["deck"]["style"]["palette"],
        json!(["#FFFFFF", "#14213D"])
    );
    assert_eq!(
        snapshot["deck"]["style"]["fonts"],
        json!(["Noto Sans CJK SC"])
    );
    assert_eq!(snapshot["deck"]["pages"][0]["layout"], "先结论后材料");
    assert_eq!(snapshot["deck"]["pages"][0]["image"]["basis"], "imported");
    assert_eq!(snapshot["deck"]["pages"][0]["svg"]["basis"], "imported");
    assert_eq!(
        snapshot["deck"]["pages"][0]["content"]["title"],
        "合成页标题"
    );
    assert_eq!(snapshot["deck"]["pages"][0]["notes"], "合成讲稿");
    let material = &snapshot["deck"]["materials"][0];
    let file = dest
        .join(".deck/files")
        .join(material["file"].as_str().unwrap());
    assert_eq!(fs::read_to_string(file).unwrap(), "synthetic material\n");
    let image = dest.join(".deck/files").join(
        snapshot["deck"]["pages"][0]["image"]["file"]
            .as_str()
            .unwrap(),
    );
    assert!(fs::read(image).unwrap().starts_with(b"\x89PNG"));
    let store = deck::store::Store::open(&dest).unwrap();
    let runs: i64 = store
        .connection
        .query_row("SELECT count(*) FROM runs", [], |row| row.get(0))
        .unwrap();
    assert_eq!(runs, 0);
    let reviews: i64 = store
        .connection
        .query_row("SELECT count(*) FROM reviews", [], |row| row.get(0))
        .unwrap();
    assert_eq!(reviews, 0);
    let exported = ops::export_pptx(&dest).unwrap();
    assert_eq!(exported["input_changed"], true);
    let original = pptx_fixture("inspect", &source.join("files/deck.pptx"), "");
    let cleaned = pptx_fixture("inspect", Path::new(exported["path"].as_str().unwrap()), "");
    assert_eq!(cleaned["slides"], original["slides"]);
    assert_eq!(cleaned["notes"], original["notes"]);
    assert_eq!(cleaned["private"], false);
    assert_eq!(cleaned["atoms"], false);
    let shown = ops::show(&dest).unwrap();
    assert_eq!(shown["artifact_status"]["stale_images"], json!(["p1"]));
    assert_eq!(shown["artifact_status"]["stale_pages"], json!(["p1"]));
}

fn run_import(source: &Path, dest: &Path) -> std::process::Output {
    Command::new(env!("CARGO_BIN_EXE_deck"))
        .args(["import", source.to_str().unwrap(), dest.to_str().unwrap()])
        .output()
        .unwrap()
}

#[test]
fn unsafe_or_unavailable_last_export_does_not_block_editable_content() {
    use sha2::{Digest, Sha256};
    for variant in ["private-notes", "private-title", "damaged", "missing-tool"] {
        let temp = tempfile::tempdir().unwrap();
        let source = temp.path().join("archive");
        fs::create_dir(&source).unwrap();
        write_archive(&source);
        let original = source.join("files/deck.pptx");
        if variant == "damaged" {
            fs::write(&original, b"damaged PPTX package").unwrap();
        } else if variant != "missing-tool" {
            pptx_fixture("make", &original, variant);
        }
        let bytes = fs::read(&original).unwrap();
        let digest = format!("{:x}", Sha256::digest(&bytes));
        let dest = temp.path().join("new-deck");
        let mut command = Command::new(env!("CARGO_BIN_EXE_deck"));
        command.arg("import").arg(&source).arg(&dest);
        if variant == "missing-tool" {
            command.env("DECK_TOOLS_PYTHON", temp.path().join("missing-python"));
        }
        let output = command.output().unwrap();
        assert!(
            output.status.success(),
            "{variant}: {}",
            String::from_utf8_lossy(&output.stderr)
        );
        let report: Value = serde_json::from_slice(&output.stdout).unwrap();
        assert_eq!(report["last_export"], false, "{variant}");
        let reason = report["unmapped"]
            .as_array()
            .unwrap()
            .iter()
            .find(|row| row["kind"] == "last_export")
            .unwrap()["reason"]
            .as_str()
            .unwrap();
        if variant.starts_with("private-") {
            assert!(
                reason.contains("第 2 页") && reason.contains("本机路径"),
                "{reason}"
            );
            assert!(!reason.contains("TypeError"));
        }
        assert!(ops::project_file(&dest, &digest).is_err());
        assert!(ops::export_pptx(&dest).is_err());
        let snapshot = ops::get(&dest, None).unwrap();
        assert_eq!(snapshot["deck"]["pages"][0]["notes"], "合成讲稿");
        ops::put(
            &dest,
            report["version"].as_i64().unwrap(),
            serde_json::from_value(json!({"pages":[{"id":"p1","notes":"导入后继续编辑"}]}))
                .unwrap(),
        )
        .unwrap();
        assert!(ops::export_md(&dest).unwrap().contains("导入后继续编辑"));
        assert_eq!(fs::read(original).unwrap(), bytes);
    }
}

#[test]
fn empty_optional_last_export_is_reported_and_required_filenames_are_rejected() {
    for field in ["last_export", "image", "preview", "asset"] {
        let temp = tempfile::tempdir().unwrap();
        let source = temp.path().join("archive");
        fs::create_dir(&source).unwrap();
        let mut manifest = archive(&source);
        match field {
            "last_export" => manifest["last_export"]["file"] = json!(""),
            "image" => manifest["pages"][0]["image"]["file"] = json!(""),
            "preview" => manifest["pages"][0]["preview"] = json!(""),
            _ => manifest["style"]["assets"] = json!([{"id":"asset","file":""}]),
        }
        fs::write(
            source.join("manifest.json"),
            serde_json::to_vec(&manifest).unwrap(),
        )
        .unwrap();
        let dest = temp.path().join("new-deck");
        let output = run_import(&source, &dest);
        if field == "last_export" {
            assert!(
                output.status.success(),
                "{}",
                String::from_utf8_lossy(&output.stderr)
            );
            let report: Value = serde_json::from_slice(&output.stdout).unwrap();
            assert_eq!(report["last_export"], false);
            assert!(
                report["unmapped"]
                    .as_array()
                    .unwrap()
                    .iter()
                    .any(|row| row["kind"] == "last_export")
            );
        } else {
            assert_import_rejected(&output, &dest, temp.path());
        }
    }
}

fn assert_import_rejected(output: &std::process::Output, dest: &Path, parent: &Path) {
    assert_eq!(
        output.status.code(),
        Some(2),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    assert!(!dest.exists());
    let leftovers: Vec<_> = fs::read_dir(parent)
        .unwrap()
        .filter_map(|entry| entry.ok())
        .map(|entry| entry.file_name())
        .filter(|name| {
            name.to_str()
                .is_some_and(|text| text.starts_with(".deck-import-"))
        })
        .collect();
    assert!(leftovers.is_empty(), "{leftovers:?}");
}

#[test]
fn import_missing_file_exits_2_without_destination() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("archive");
    fs::create_dir(&source).unwrap();
    write_archive(&source);
    fs::remove_file(source.join("files").join("page.png")).unwrap();
    let dest = temp.path().join("new-deck");
    let output = run_import(&source, &dest);
    assert_import_rejected(&output, &dest, temp.path());
    assert!(String::from_utf8_lossy(&output.stderr).contains("page.png"));
}

#[test]
fn import_wrong_format_exits_2_without_destination() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("archive");
    fs::create_dir(&source).unwrap();
    let mut manifest = archive(&source);
    manifest["format"] = json!("legacy-export.v0");
    fs::write(
        source.join("manifest.json"),
        serde_json::to_vec_pretty(&manifest).unwrap(),
    )
    .unwrap();
    let dest = temp.path().join("new-deck");
    let output = run_import(&source, &dest);
    assert_import_rejected(&output, &dest, temp.path());
    assert!(String::from_utf8_lossy(&output.stderr).contains("legacy-export.v0"));
}

#[test]
fn import_parent_path_filename_exits_2_without_destination() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("archive");
    fs::create_dir(&source).unwrap();
    let mut manifest = archive(&source);
    manifest["materials"][0]["file"] = json!("../secret.txt");
    fs::write(
        source.join("manifest.json"),
        serde_json::to_vec_pretty(&manifest).unwrap(),
    )
    .unwrap();
    let dest = temp.path().join("new-deck");
    let output = run_import(&source, &dest);
    assert_import_rejected(&output, &dest, temp.path());
    let stderr = String::from_utf8_lossy(&output.stderr);
    assert!(stderr.contains("../secret.txt"), "{stderr}");
}

#[test]
fn import_refuses_existing_destination() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("archive");
    fs::create_dir(&source).unwrap();
    write_archive(&source);
    let dest = temp.path().join("new-deck");
    fs::create_dir(&dest).unwrap();
    let error = ops::import(&source, &dest).unwrap_err();
    assert_eq!(error.exit_code(), 2);
    assert!(error.to_string().contains("目标已存在"));
}

#[test]
fn import_cli_writes_report_json() {
    let temp = tempfile::tempdir().unwrap();
    let source = temp.path().join("archive");
    fs::create_dir(&source).unwrap();
    write_archive(&source);
    let dest = temp.path().join("new-deck");
    let output = Command::new(env!("CARGO_BIN_EXE_deck"))
        .args(["import", source.to_str().unwrap(), dest.to_str().unwrap()])
        .output()
        .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    let report: Value = serde_json::from_slice(&output.stdout).unwrap();
    assert_eq!(report["pages"], 1);
    assert_eq!(report["open_calls"][0]["task_id"], "task-synth");
}
