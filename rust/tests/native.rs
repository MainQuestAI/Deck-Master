use deck::{
    model::Artifact,
    ops,
    store::{self, Store},
};
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

fn cli(path: &Path, args: &[&str]) -> Value {
    let output = command(path, args);
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    serde_json::from_slice(&output.stdout).unwrap()
}

fn edit(path: &Path, patch: Value) {
    let version = Store::open(path).unwrap().current().unwrap().version;
    ops::put(path, version, serde_json::from_value(patch).unwrap()).unwrap();
}

fn python(args: &[&str]) -> Value {
    let output = Command::new(
        std::env::var_os("DECK_TOOLS_PYTHON").expect("install this worktree's deck-tools"),
    )
    .args(args)
    .output()
    .unwrap();
    assert!(
        output.status.success(),
        "{}",
        String::from_utf8_lossy(&output.stderr)
    );
    serde_json::from_slice(&output.stdout).unwrap()
}

fn plan(path: &Path, page: &str, title: &str) -> std::path::PathBuf {
    let plan = json!({"schema":"deck.native_plan.v1", "page":page,
    "canvas_px":{"w":800,"h":450},"background":"FFFFFF","ops":[
        {"op":"text","text":title,"atom_id":format!("atom:{page}:title"),
         "bbox":[20,20,700,70],"size":32},
        {"op":"text","text":"","atom_id":format!("atom:{page}:subtitle"),"bbox":[20,95,700,10],"size":12},
            {"op":"image","file":"asset.png","bbox":[20,120,100,100]},
        {"op":"icon","icon_id":"tabler-outline/anchor","bbox":[200,120,50,50]}
    ]});
    let filename = path.join(format!("{page}-plan.json"));
    std::fs::write(&filename, plan.to_string()).unwrap();
    filename
}

fn digest(path: &Path, id: i64) -> String {
    Store::open(path)
        .unwrap()
        .connection
        .query_row("SELECT input_digest FROM builds WHERE id=?", [id], |r| {
            r.get(0)
        })
        .unwrap()
}

#[test]
fn v5_pages_without_native_upgrade_only_user_version_and_future_formats_prompt_upgrade() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成作品".into()).unwrap();
    edit(
        path,
        json!({"order":["p1"],"pages":[{"id":"p1","content":{"title":"Alpha"}}]}),
    );
    let store = Store::open(path).unwrap();
    let old_json: String = store
        .connection
        .query_row(
            "SELECT deck_json FROM versions ORDER BY id DESC LIMIT 1",
            [],
            |row| row.get(0),
        )
        .unwrap();
    let mut old: Value = serde_json::from_str(&old_json).unwrap();
    old["pages"][0].as_object_mut().unwrap().remove("native");
    let old_json = old.to_string();
    store
        .connection
        .execute("UPDATE versions SET deck_json=? WHERE id=2", [&old_json])
        .unwrap();
    store
        .connection
        .pragma_update(None, "user_version", 5)
        .unwrap();
    drop(store);
    let loaded = cli(path, &["get"]);
    assert!(loaded["deck"]["pages"][0]["native"].is_null());
    let store = Store::open(path).unwrap();
    assert_eq!(
        store
            .connection
            .pragma_query_value(None, "user_version", |r| r.get::<_, i64>(0))
            .unwrap(),
        6
    );
    let unchanged: String = store
        .connection
        .query_row("SELECT deck_json FROM versions WHERE id=2", [], |r| {
            r.get(0)
        })
        .unwrap();
    assert_eq!(unchanged, old_json);
    assert_eq!(store.history().unwrap().len(), 2);
    store
        .connection
        .pragma_update(None, "user_version", store::FORMAT_VERSION + 1)
        .unwrap();
    // A future document must be refused before attempting to deserialize it.
    store
        .connection
        .execute(
            "UPDATE versions SET deck_json='{\"unknown_future_field\":true}'",
            [],
        )
        .unwrap();
    drop(store);
    let output = command(path, &["get"]);
    assert_eq!(output.status.code(), Some(2));
    assert!(String::from_utf8_lossy(&output.stderr).contains("请升级 deck"));
}

#[test]
#[ignore = "needs node + pptxgenjs + soffice; runs in the render job"]
fn native_candidates_require_a_conclusion_then_build_export_use_adopted_packs_and_current_notes() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    cli(path, &["new", path.to_str().unwrap()]);
    edit(
        path,
        json!({"order":["p1","p2"],"pages":[
            {"id":"p1","content":{"title":"Alpha"},"notes":"原讲稿"},
            {"id":"p2","content":{"title":"Beta"},"notes":"第二页讲稿"}
        ]}),
    );
    python(&[
        "-c",
        "from PIL import Image; import sys,json; from pathlib import Path; p=Path(sys.argv[1]); Image.new('RGB',(800,450),'white').save(p/'source.png'); Image.new('RGB',(40,40),'teal').save(p/'asset.png'); print('{}')",
        path.to_str().unwrap(),
    ]);
    let image =
        cli(path, &["run", "start", "image", "--pages", "p1,p2"])["runs"][0]["id"].to_string();
    for id in ["p1", "p2"] {
        cli(
            path,
            &[
                "run",
                "result",
                &image,
                id,
                path.join("source.png").to_str().unwrap(),
            ],
        );
    }
    let run = cli(path, &["run", "start", "native", "--pages", "p1,p2"]);
    assert_eq!(run["runs"][0]["kind"], "native");
    let run_id = run["runs"][0]["id"].to_string();
    let work = Path::new(run["runs"][0]["pages"][0]["work"].as_str().unwrap());
    assert!(work.join("atoms.json").is_file());
    assert!(work.join("native-reconstruction.md").is_file());
    let p1 = plan(path, "p1", "Alpha");
    let result = cli(
        path,
        &["run", "result", &run_id, "p1", p1.to_str().unwrap()],
    );
    assert_eq!(result["adopted"], false);
    assert_eq!(result["run"]["runs"][0]["pages"][0]["status"], "unadopted");
    assert_eq!(result["findings"], json!({"page":"p1", "atoms":2}));
    assert!(Path::new(result["side_by_side"].as_str().unwrap()).is_file());
    let store = Store::open(path).unwrap();
    let candidate = result["file"].as_str().unwrap();
    assert!(candidate.ends_with(".native.json"));
    let candidate_bytes = std::fs::read(store.file(candidate).unwrap()).unwrap();
    let pack: Value = serde_json::from_slice(&candidate_bytes).unwrap();
    assert_eq!(pack["note"], "");
    assert_eq!(pack["assets"].as_array().unwrap().len(), 1);
    for field in ["file", "sha256"] {
        assert!(pack["assets"][0][field].is_string());
    }
    assert!(
        store
            .file(pack["assets"][0]["file"].as_str().unwrap())
            .unwrap()
            .is_file()
    );
    assert!(store.current().unwrap().deck.pages[0].native.is_none());
    drop(store);
    let unadopted = command(path, &["build"]);
    assert_eq!(unadopted.status.code(), Some(2));
    let error = String::from_utf8_lossy(&unadopted.stderr);
    assert!(error.contains("p1") && error.contains("p2"));
    assert_eq!(
        Store::open(path)
            .unwrap()
            .connection
            .query_row("SELECT count(*) FROM builds", [], |row| row
                .get::<_, i64>(0))
            .unwrap(),
        0
    );
    for args in [
        vec!["run", "adopt", &run_id, "p1"],
        vec!["run", "adopt", &run_id, "p1", "--note", ""],
        vec!["run", "adopt", &run_id, "p1", "--note", " \n "],
    ] {
        let failed = command(path, &args);
        assert_eq!(failed.status.code(), Some(2));
        assert!(String::from_utf8_lossy(&failed.stderr).contains("--note"));
    }
    cli(
        path,
        &[
            "run",
            "adopt",
            &run_id,
            "p1",
            "--note",
            " 已对照文字与对象 ",
        ],
    );
    let mut store = Store::open(path).unwrap();
    let mut current = store.current().unwrap();
    let adopted = current.deck.pages[0].native.as_ref().unwrap();
    assert_ne!(adopted.file, candidate);
    assert!(adopted.basis.starts_with("svg-v2:"));
    assert_eq!(
        adopted.basis,
        ops::basis("svg", &current.deck, &current.deck.pages[0]).unwrap()
    );
    let final_pack: Value =
        serde_json::from_slice(&std::fs::read(store.file(&adopted.file).unwrap()).unwrap())
            .unwrap();
    assert_eq!(final_pack["note"], "已对照文字与对象");
    assert_eq!(
        current.deck.pages[0].preview.as_deref(),
        final_pack["render_png"].as_str()
    );
    assert_eq!(
        std::fs::read(store.file(candidate).unwrap()).unwrap(),
        candidate_bytes
    );
    // An old SVG on the missing page must never supply a native slide.
    let svg = store.add_file(b"synthetic unused svg", "svg").unwrap();
    current.deck.pages[1].svg = Some(Artifact {
        file: svg,
        basis: "imported".into(),
    });
    let tx = store.transaction().unwrap();
    store::append(&tx, &current.deck, "Synthetic legacy artifact").unwrap();
    tx.commit().unwrap();
    drop(store);
    let partial = cli(path, &["build"]);
    assert_eq!(partial["missing_pages"], json!(["p2"]));
    assert_eq!(partial["stale_pages"], json!([]));
    assert_eq!(
        ops::artifact_status(&Store::open(path).unwrap().current().unwrap().deck).unwrap()["missing_pages"],
        json!(["p2"])
    );
    let p2 = plan(path, "p2", "Beta");
    cli(
        path,
        &["run", "result", &run_id, "p2", p2.to_str().unwrap()],
    );
    cli(
        path,
        &["run", "adopt", &run_id, "p2", "--note", "已对照第二页"],
    );
    let shown = cli(path, &["run", "show", &run_id]);
    assert_eq!(shown["runs"][0]["status"], "done");
    assert_eq!(shown["runs"][0]["pages"][0]["basis_changed"], false);
    // Adopted packs retain their inputs after source files are removed.
    std::fs::remove_file(path.join("asset.png")).unwrap();
    std::fs::remove_file(&p1).unwrap();
    std::fs::remove_file(&p2).unwrap();
    edit(
        path,
        json!({"pages":[{"id":"p1","notes":"当前讲稿第一行\n当前讲稿第二行"}]}),
    );
    let built = cli(path, &["build"]);
    assert_eq!(built["missing_pages"], json!([]));
    assert_eq!(built["stale_pages"], json!([]));
    let exported = cli(path, &["export", "pptx"]);
    assert_eq!(exported["input_changed"], false);
    assert_eq!(exported["stale_pages"], json!([]));
    assert_eq!(
        std::fs::read(exported["path"].as_str().unwrap()).unwrap(),
        std::fs::read(built["path"].as_str().unwrap()).unwrap()
    );
    let notes = python(&[
        "-c",
        "from deck_tools.compiler.native import notes_records; from pathlib import Path; import sys,json; print(json.dumps(notes_records(Path(sys.argv[1]).read_bytes()),ensure_ascii=False))",
        exported["path"].as_str().unwrap(),
    ]);
    assert_eq!(notes[0]["notes"], "当前讲稿第一行\n当前讲稿第二行");
    assert_eq!(notes[1]["notes"], "第二页讲稿");
    assert_eq!(notes.as_array().unwrap().len(), 2);
    let before = digest(path, built["id"].as_i64().unwrap());
    let detail = ops::build_detail(path, built["id"].as_i64().unwrap()).unwrap();
    assert_eq!(detail["pages"].as_array().unwrap().len(), 2);
    assert_eq!(detail["readback_matches_current"], true);
    edit(
        path,
        json!({"pages":[{"id":"p1","content":{"title":"Changed Alpha"}}]}),
    );
    assert_eq!(
        cli(path, &["get"])["artifact_status"]["stale_pages"],
        json!(["p1"])
    );
    assert_eq!(cli(path, &["export", "pptx"])["input_changed"], true);
    let stale_build = cli(path, &["build"]);
    assert_eq!(stale_build["stale_pages"], json!(["p1"]));
    assert_ne!(digest(path, stale_build["id"].as_i64().unwrap()), before);
    edit(
        path,
        json!({"pages":[{"id":"p1","content":{"title":"Alpha"}}]}),
    );
    assert_eq!(
        cli(path, &["get"])["artifact_status"]["stale_pages"],
        json!([])
    );
    python(&[
        "-c",
        "from PIL import Image; import sys; Image.new('RGB',(800,450),'navy').save(sys.argv[1]); print('{}')",
        path.join("changed.png").to_str().unwrap(),
    ]);
    let image = cli(path, &["run", "start", "image", "--pages", "p1"])["runs"][0]["id"].to_string();
    cli(
        path,
        &[
            "run",
            "result",
            &image,
            "p1",
            path.join("changed.png").to_str().unwrap(),
        ],
    );
    assert_eq!(
        cli(path, &["get"])["artifact_status"]["stale_pages"],
        json!(["p1"])
    );
}
