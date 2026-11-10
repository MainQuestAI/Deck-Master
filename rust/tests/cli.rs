use serde_json::{Value, json};
use std::path::Path;
use std::process::{Command, Output};

fn command(path: &Path, args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_deck"))
        .arg("--project")
        .arg(path)
        .args(args)
        .output()
        .unwrap()
}

fn output_json(output: Output) -> Value {
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    serde_json::from_slice(&output.stdout).unwrap()
}

#[test]
fn serve_rejects_project_option_before_or_after_subcommand() {
    let without_option = Command::new(env!("CARGO_BIN_EXE_deck"))
        .args(["serve", "synthetic"])
        .output()
        .unwrap();
    for args in [
        ["serve", "synthetic", "--project", "other"],
        ["--project", "other", "serve", "synthetic"],
    ] {
        let output = Command::new(env!("CARGO_BIN_EXE_deck"))
            .args(args)
            .output()
            .unwrap();
        assert_eq!(output.status.code(), Some(2));
        assert!(output.stdout.is_empty());
        assert!(!output.stderr.is_empty());
        assert_ne!(output.stderr, without_option.stderr);
    }
}

#[test]
fn cli_partial_edit_conflict_and_markdown_export() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    output_json(command(
        path,
        &["new", path.to_str().unwrap(), "--title", "合成演示"],
    ));
    let input = path.join("input.json");
    std::fs::write(
        &input,
        json!({"order":["p1"],"pages":[{"id":"p1","notes":"第一稿"}]}).to_string(),
    )
    .unwrap();
    output_json(command(
        path,
        &["put", "--base", "1", input.to_str().unwrap()],
    ));
    let mut partial = output_json(command(path, &["get", "--pages", "p1"]));
    partial["deck"]["pages"][0]["notes"] = json!("新讲稿");
    std::fs::write(&input, partial.to_string()).unwrap();
    let saved = output_json(command(
        path,
        &["put", "--base", "2", input.to_str().unwrap()],
    ));
    assert_eq!(saved["version"], 3);
    let retry = output_json(command(
        path,
        &["put", "--base", "2", input.to_str().unwrap()],
    ));
    assert_eq!(retry["version"], 3);
    partial["deck"]["pages"][0]["notes"] = json!("冲突稿");
    std::fs::write(&input, partial.to_string()).unwrap();
    assert_eq!(
        command(path, &["put", "--base", "2", input.to_str().unwrap()])
            .status
            .code(),
        Some(5)
    );
    let exported = command(path, &["export", "md"]);
    assert!(exported.status.success());
    assert!(
        String::from_utf8(exported.stdout)
            .unwrap()
            .contains("新讲稿")
    );
    assert_eq!(output_json(command(path, &["restore", "2"]))["version"], 4);
    assert_eq!(
        output_json(command(path, &["show"]))["history"]
            .as_array()
            .unwrap()
            .len(),
        4
    );
}

#[test]
fn new_deck_defaults_reach_image_task_without_putting_style() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    output_json(command(path, &["new", path.to_str().unwrap()]));
    let created = output_json(command(path, &["get"]));
    assert_eq!(
        created["deck"]["style"]["palette"],
        json!(["#164267", "#F5F7FA", "#D97706"])
    );
    assert_eq!(
        created["deck"]["style"]["fonts"],
        json!(["Noto Sans CJK SC"])
    );
    let input = path.join("page.json");
    std::fs::write(
        &input,
        json!({"order":["p1"],"pages":[{
            "id":"p1",
            "purpose":"看清校验与执行的先后。",
            "layout":"主图从左向右连接校验与执行；校验通过后进入执行。",
            "content":{
                "title":"校验通过后才进入执行",
                "body_blocks":[{"type":"paragraph","text":"校验通过后进入执行。"}]
            }
        }]})
        .to_string(),
    )
    .unwrap();
    output_json(command(
        path,
        &["put", "--base", "1", input.to_str().unwrap()],
    ));
    let run = output_json(command(path, &["run", "start", "image", "--pages", "p1"]));
    let work = Path::new(run["runs"][0]["pages"][0]["work"].as_str().unwrap());
    let task = std::fs::read_to_string(work.join("task.md")).unwrap();
    for text in ["#164267", "#F5F7FA", "#D97706", "Noto Sans CJK SC"] {
        assert!(task.contains(text), "image task omits default style {text}");
    }
}

#[test]
fn lookup_page_table_survives_readable_export() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    output_json(command(path, &["new", path.to_str().unwrap()]));
    let input = path.join("input.json");
    std::fs::write(&input, include_str!("fixtures/lookup-page.json")).unwrap();
    output_json(command(
        path,
        &["put", "--base", "1", input.to_str().unwrap()],
    ));
    let exported = command(path, &["export", "md"]);
    assert!(
        exported.status.success(),
        "{}",
        String::from_utf8_lossy(&exported.stderr)
    );
    let markdown = String::from_utf8(exported.stdout).unwrap();
    let table = "| 要求 | 响应要点 | 展开位置 |\n\
| --- | --- | --- |\n\
| 异常记录 | 拟记录失败原因 | 异常处理章节 |\n\
| 结果导出 | 拟支持按任务导出 | 导出说明章节 |\n\n\
拟议响应不表示已经交付。\n";
    assert!(
        markdown.contains(table),
        "readable export loses lookup rows"
    );
}

#[test]
fn planned_page_survives_image_task_and_readable_export() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    output_json(command(
        path,
        &["new", path.to_str().unwrap(), "--title", "合成任务方案"],
    ));
    let fixture = include_str!("fixtures/page-planning.json");
    let input = path.join("input.json");
    std::fs::write(&input, fixture).unwrap();
    output_json(command(
        path,
        &["put", "--base", "1", input.to_str().unwrap()],
    ));
    let expected: Value = serde_json::from_str(fixture).unwrap();
    let page = &expected["pages"][0];
    let run = output_json(command(
        path,
        &["run", "start", "image", "--pages", "p1", "--max-calls", "1"],
    ));
    let work = Path::new(run["runs"][0]["pages"][0]["work"].as_str().unwrap());
    let task = std::fs::read_to_string(work.join("task.md")).unwrap();
    let exported = command(path, &["export", "md"]);
    assert!(
        exported.status.success(),
        "{}",
        String::from_utf8_lossy(&exported.stderr)
    );
    let markdown = String::from_utf8(exported.stdout).unwrap();
    for text in [
        page["content"]["title"].as_str().unwrap(),
        page["purpose"].as_str().unwrap(),
        page["layout"].as_str().unwrap(),
    ] {
        assert!(task.contains(text), "image task omits {text}");
        assert!(markdown.contains(text), "readable export omits {text}");
    }
    for field in ["palette", "fonts"] {
        for value in expected["style"][field].as_array().unwrap() {
            let text = value.as_str().unwrap();
            assert!(task.contains(text), "image task omits style {text}");
        }
    }
    assert!(markdown.contains(&format!(
        "**本页目的**：{}",
        page["purpose"].as_str().unwrap()
    )));
    assert!(markdown.contains(&format!("**布局**：{}", page["layout"].as_str().unwrap())));
    // Verify body hierarchy separately so facts mentioned in layout cannot hide lost body blocks.
    let body = "**状态与分支**\n\n\
- 校验通过后，有执行空位的任务进入执行，无空位的任务进入排队。\n\
- 空位释放后，排队任务进入执行。\n\
- 执行后分为互斥的两种结果：\n  - 成功：记录输出。\n  - 失败：记录原因。\n\n\
**容量条件**\n\n- 50指执行中并发目标，不是排队人数。\n\n\
**验收证据**\n\n- 分别记录排队数、执行数和成功或失败的结果。\n";
    assert!(task.contains(body), "image task loses content organization");
    assert!(
        markdown.contains(body),
        "readable export loses content organization"
    );
    for label in page["content"]["labels"].as_array().unwrap() {
        let text = label["text"].as_str().unwrap();
        assert!(task.contains(&format!("- {text}\n")));
        assert!(markdown.contains(&format!("- {text}\n")));
    }
}

#[test]
fn material_add_uses_real_python_tool_preserves_original_and_deduplicates() {
    assert!(
        std::env::var_os("DECK_TOOLS_PYTHON").is_some(),
        "install deck-tools and set DECK_TOOLS_PYTHON before cargo test"
    );
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    output_json(command(path, &["new", path.to_str().unwrap()]));
    let source = path.join("合成材料.md");
    let data = "# 合成材料\n数字 0\n末尾仍保留\n";
    std::fs::write(&source, data).unwrap();
    let added = output_json(command(
        path,
        &["material", "add", source.to_str().unwrap()],
    ));
    assert_eq!(added["material"]["id"], "m1");
    assert_eq!(added["extraction"]["text"], data);
    assert_eq!(std::fs::read_to_string(&source).unwrap(), data);
    let retry = output_json(command(
        path,
        &["material", "add", source.to_str().unwrap()],
    ));
    assert_eq!(retry["version"], added["version"]);
    let file = path
        .join(".deck/files")
        .join(added["material"]["file"].as_str().unwrap());
    assert_eq!(std::fs::read_to_string(file).unwrap(), data);
    std::fs::remove_file(&source).unwrap();
    let text = output_json(command(path, &["material", "text", "m1"]));
    assert!(std::path::Path::new(text["original_path"].as_str().unwrap()).is_file());
    assert_eq!(
        std::fs::read_to_string(text["path"].as_str().unwrap()).unwrap(),
        data
    );
    assert_eq!(
        output_json(command(path, &["get"]))["deck"]["materials"]
            .as_array()
            .unwrap()
            .len(),
        1
    );
    std::fs::remove_file(text["path"].as_str().unwrap()).unwrap();
    assert_eq!(
        command(path, &["material", "text", "m1"]).status.code(),
        Some(2)
    );
}

#[test]
fn material_errors_have_real_exit_codes_and_no_dangling_version_references() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    output_json(command(path, &["new", path.to_str().unwrap()]));
    let source = path.join("bad.json");
    std::fs::write(&source, "{broken").unwrap();
    assert_eq!(
        command(path, &["material", "add", source.to_str().unwrap()])
            .status
            .code(),
        Some(2)
    );
    assert_eq!(output_json(command(path, &["show"]))["version"], 1);
    let source = path.join("source.xyz");
    std::fs::write(&source, "synthetic input").unwrap();
    assert_eq!(
        command(path, &["material", "add", source.to_str().unwrap()])
            .status
            .code(),
        Some(3)
    );
    assert_eq!(
        output_json(command(path, &["show"]))["materials"][0]["status"],
        "needs_tool"
    );
    assert_eq!(
        command(path, &["material", "text", "m1"]).status.code(),
        Some(3)
    );
    let no_python = Command::new(env!("CARGO_BIN_EXE_deck"))
        .env_remove("DECK_TOOLS_PYTHON")
        .arg("--project")
        .arg(path)
        .args(["material", "add"])
        .arg(&source)
        .output()
        .unwrap();
    assert_eq!(no_python.status.code(), Some(3));
    assert_eq!(output_json(command(path, &["show"]))["version"], 2);
}

fn synthetic_pdf() -> Vec<u8> {
    let stream = "BT /F1 14 Tf 72 720 Td (Synthetic material zero 0) Tj ET\n";
    let objects = [
        "<< /Type /Catalog /Pages 2 0 R >>".to_string(),
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>".to_string(),
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>".to_string(),
        format!("<< /Length {} >>\nstream\n{stream}endstream", stream.len()),
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>".to_string(),
    ];
    let mut pdf = "%PDF-1.4\n".to_string();
    let mut offsets = Vec::new();
    for (index, object) in objects.iter().enumerate() {
        offsets.push(pdf.len());
        pdf.push_str(&format!("{} 0 obj\n{object}\nendobj\n", index + 1));
    }
    let xref = pdf.len();
    pdf.push_str("xref\n0 6\n0000000000 65535 f \n");
    for offset in offsets {
        pdf.push_str(&format!("{offset:010} 00000 n \n"));
    }
    pdf.push_str(&format!(
        "trailer << /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n"
    ));
    pdf.into_bytes()
}

#[test]
fn duplicate_pdf_add_without_tool_preserves_successful_extraction() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    output_json(command(path, &["new", path.to_str().unwrap()]));
    let source = path.join("synthetic.pdf");
    let original = synthetic_pdf();
    std::fs::write(&source, &original).unwrap();
    let empty_path = path.join("without-tools");
    std::fs::create_dir(&empty_path).unwrap();
    let without_pdf_tool = || {
        Command::new(env!("CARGO_BIN_EXE_deck"))
            .env("PATH", &empty_path)
            .arg("--project")
            .arg(path)
            .args(["material", "add"])
            .arg(&source)
            .output()
            .unwrap()
    };

    assert_eq!(without_pdf_tool().status.code(), Some(3));
    assert_eq!(
        output_json(command(path, &["show"]))["materials"][0]["status"],
        "needs_tool"
    );
    let added = output_json(command(
        path,
        &["material", "add", source.to_str().unwrap()],
    ));
    assert_eq!(added["material"]["status"], "read");
    assert!(
        added["extraction"]["text"]
            .as_str()
            .unwrap()
            .contains("Synthetic material zero 0")
    );
    let before = output_json(command(path, &["get"]));
    let history_before = output_json(command(path, &["show"]))["history"].clone();
    let text_before = output_json(command(path, &["material", "text", "m1"]));
    let saved_text = std::fs::read(text_before["path"].as_str().unwrap()).unwrap();

    assert_eq!(without_pdf_tool().status.code(), Some(3));
    assert_eq!(output_json(command(path, &["get"])), before);
    assert_eq!(
        output_json(command(path, &["show"]))["history"],
        history_before
    );
    let text_after = output_json(command(path, &["material", "text", "m1"]));
    assert_eq!(text_after, text_before);
    assert_eq!(
        std::fs::read(text_after["path"].as_str().unwrap()).unwrap(),
        saved_text
    );
    assert_eq!(std::fs::read(&source).unwrap(), original);
    assert_eq!(
        output_json(command(
            path,
            &["material", "add", source.to_str().unwrap()]
        ))["version"],
        added["version"]
    );
}

#[test]
fn review_commands_default_filter_resolve_count_and_reject_invalid_input() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    output_json(command(path, &["new", path.to_str().unwrap()]));
    deck::ops::put(
        path,
        1,
        serde_json::from_value(json!({"order":["p3"],"pages":[{"id":"p3"}]})).unwrap(),
    )
    .unwrap();
    let human = output_json(command(path, &["review", "add", "整稿意见"]));
    assert_eq!(human["method"], "human");
    assert_eq!(human["reviewer"], "author");
    let checked = output_json(command(
        path,
        &[
            "review",
            "add",
            "自检 100 元",
            "--page",
            "p3",
            "--method",
            "self_check",
            "--reviewer",
            "Host",
        ],
    ));
    assert_eq!(checked["method"], "self_check");
    assert_eq!(checked["reviewer"], "Host");
    let remaining = output_json(command(
        path,
        &["review", "add", "另一条页上意见", "--page", "p3"],
    ));
    let show = output_json(command(path, &["show"]));
    assert_eq!(show["open_reviews_total"], 3);
    assert_eq!(show["pages"][0]["open_reviews"], 2);
    let filtered = output_json(command(
        path,
        &["review", "list", "--status", "open", "--page", "p3"],
    ));
    assert_eq!(filtered["reviews"], json!([checked, remaining]));
    let target = checked["id"].to_string();
    let resolved = output_json(command(path, &["review", "resolve", &target]));
    assert_eq!(resolved["id"], checked["id"]);
    assert_eq!(resolved["status"], "resolved");
    assert_eq!(
        output_json(command(path, &["review", "resolve", &target])),
        resolved
    );
    assert_eq!(
        output_json(command(
            path,
            &["review", "list", "--status", "open", "--page", "p3"]
        ))["reviews"],
        json!([remaining])
    );
    assert_eq!(
        output_json(command(path, &["review", "list", "--status", "resolved"]))["reviews"],
        json!([resolved])
    );
    for args in [
        vec!["review", "add", ""],
        vec!["review", "add", "意见", "--method", "pass"],
        vec!["review", "add", "意见", "--page", "p9"],
        vec!["review", "list", "--status", "pass"],
        vec!["review", "resolve", "999"],
    ] {
        assert_eq!(command(path, &args).status.code(), Some(2));
    }
    assert_eq!(output_json(command(path, &["show"]))["version"], 2);
}

#[test]
fn material_original_is_immutable_optional_and_invalid_references_are_errors() {
    use deck::{
        ops,
        store::{self, Store},
    };
    let temp = tempfile::tempdir().unwrap();
    let project = temp.path();
    ops::new(project, "Synthetic material".into()).unwrap();
    let source = project.join("source.md");
    std::fs::write(&source, "Original text").unwrap();
    ops::material_add(project, &source).unwrap();
    let read = ops::material_text(project, "m1").unwrap();
    let original = read["original_path"].as_str().unwrap();
    std::fs::write(&source, "Changed external source").unwrap();
    assert_eq!(std::fs::read_to_string(original).unwrap(), "Original text");
    let version = ops::get(project, None).unwrap()["version"].clone();
    std::fs::remove_file(original).unwrap();
    let read = ops::material_text(project, "m1").unwrap();
    assert!(read["original_path"].is_null());
    assert_eq!(
        std::fs::read_to_string(read["path"].as_str().unwrap()).unwrap(),
        "Original text"
    );
    assert_eq!(ops::get(project, None).unwrap()["version"], version);
    let mut store = Store::open(project).unwrap();
    let mut snapshot = store.current().unwrap();
    snapshot.deck.materials[0].file = "../invalid.md".into();
    let tx = store.transaction().unwrap();
    store::append(&tx, &snapshot.deck, "Synthetic invalid reference").unwrap();
    tx.commit().unwrap();
    assert!(matches!(
        ops::material_text(project, "m1"),
        Err(deck::error::Error::Input(_))
    ));
}
