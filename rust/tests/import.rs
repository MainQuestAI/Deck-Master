use deck::ops;
use serde_json::{Value, json};
use std::fs;
use std::path::Path;
use std::process::Command;

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
    write_file(root, "deck.pptx", b"PK\x03\x04synthetic");
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
