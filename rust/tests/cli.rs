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
