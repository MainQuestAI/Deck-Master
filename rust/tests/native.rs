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

fn seed_native_candidate(path: &Path, run_id: i64, page: &str, title: [i64; 4], shape: [i64; 4]) {
    let store = Store::open(path).unwrap();
    let png = store.add_file(b"synthetic-preview", "png").unwrap();
    let plan = json!({
        "schema":"deck.native_plan.v1",
        "page": page,
        "canvas_px": {"w": 800, "h": 450},
        "ops": [
            {"op":"text","atom_id":format!("atom:{page}:title"),"text":"t","bbox":title},
            {"op":"shape","type":"rect","bbox":shape},
            {"op":"text","atom_id":format!("atom:{page}:body"),"text":page,"bbox":[12, 120, 80, 24]}
        ]
    });
    let pack = json!({"plan":plan,"assets":[],"render_png":png,"note":""});
    let file = store
        .add_file(pack.to_string().as_bytes(), "native.json")
        .unwrap();
    store
        .connection
        .execute(
            "UPDATE run_pages SET result_file=?1, status='unadopted' WHERE run_id=?2 AND page_id=?3",
            (&file, run_id, page),
        )
        .unwrap();
}

fn warning_codes(value: &Value) -> Vec<&str> {
    value
        .as_array()
        .unwrap()
        .iter()
        .map(|item| item["code"].as_str().unwrap())
        .collect()
}

#[test]
fn native_task_states_original_pixel_size_and_omits_it_when_unreadable() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    cli(path, &["new", path.to_str().unwrap()]);
    edit(
        path,
        json!({"order":["p1"],"pages":[{"id":"p1","content":{"title":"Alpha"}}]}),
    );
    python(&[
        "-c",
        "from PIL import Image; import sys; Image.new('RGB',(1672,941),'white').save(sys.argv[1]); print('{}')",
        path.join("source.png").to_str().unwrap(),
    ]);
    let image = cli(path, &["run", "start", "image", "--pages", "p1"])["runs"][0]["id"].to_string();
    cli(
        path,
        &[
            "run",
            "result",
            &image,
            "p1",
            path.join("source.png").to_str().unwrap(),
        ],
    );
    let run = cli(path, &["run", "start", "native", "--pages", "p1"]);
    assert_eq!(run["runs"][0]["status"], "open");
    let work = Path::new(run["runs"][0]["pages"][0]["work"].as_str().unwrap());
    let task = std::fs::read_to_string(work.join("task.md")).unwrap();
    let attachments: Value =
        serde_json::from_slice(&std::fs::read(work.join("attachments.json")).unwrap()).unwrap();
    let file = attachments
        .as_array()
        .unwrap()
        .iter()
        .find(|item| item["role"] == "original")
        .unwrap()["file"]
        .as_str()
        .unwrap();
    assert!(task.contains(&format!(
        "本页原图 {file} 为 1672×941 px，plan.canvas_px 用这个尺寸。"
    )));
    let store = Store::open(path).unwrap();
    let image_file = store.current().unwrap().deck.pages[0]
        .image
        .as_ref()
        .unwrap()
        .file
        .clone();
    std::fs::write(store.file(&image_file).unwrap(), b"not an image").unwrap();
    drop(store);
    let id = run["runs"][0]["id"].to_string();
    cli(path, &["run", "cancel", &id]);
    let again = cli(path, &["run", "start", "native", "--pages", "p1"]);
    assert_eq!(again["runs"][0]["status"], "open");
    let work = Path::new(again["runs"][0]["pages"][0]["work"].as_str().unwrap());
    let task = std::fs::read_to_string(work.join("task.md")).unwrap();
    assert!(!task.contains("plan.canvas_px 用这个尺寸"));
}

#[test]
fn boilerplate_note_warns_without_blocking_adopt_and_blank_note_still_exits_2() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    cli(path, &["new", path.to_str().unwrap()]);
    edit(
        path,
        json!({"order":["p1"],"pages":[{"id":"p1","content":{"title":"Alpha"}}]}),
    );
    let run = cli(path, &["run", "start", "native", "--pages", "p1"]);
    let run_id = run["runs"][0]["id"].as_i64().unwrap();
    let run_text = run_id.to_string();
    seed_native_candidate(path, run_id, "p1", [40, 30, 500, 48], [24, 24, 10, 36]);
    for note in ["", " \n "] {
        let failed = command(path, &["run", "adopt", &run_text, "p1", "--note", note]);
        assert_eq!(failed.status.code(), Some(2));
        assert!(String::from_utf8_lossy(&failed.stderr).contains("--note"));
    }
    let adopted = cli(path, &["run", "adopt", &run_text, "p1", "--note", "已核对"]);
    assert_eq!(warning_codes(&adopted["warnings"]), ["note_unspecific"]);
    assert_eq!(adopted["warnings"][0]["level"], "warning");
    let store = Store::open(path).unwrap();
    let file = store.current().unwrap().deck.pages[0]
        .native
        .as_ref()
        .unwrap()
        .file
        .clone();
    let pack: Value =
        serde_json::from_slice(&std::fs::read(store.file(&file).unwrap()).unwrap()).unwrap();
    assert_eq!(pack["note"], "已核对");
    assert!(pack.get("warnings").is_none());
    drop(store);
    let specific = "已查看并排图，四来源汇入数据的方向明确，四行来源及获取方式和用途完整，底部保留数据责任、更新与适用条件。";
    let adopted = cli(path, &["run", "adopt", &run_text, "p1", "--note", specific]);
    assert!(adopted.get("warnings").is_none());
    let adopted = cli(
        path,
        &["run", "adopt", &run_text, "p1", "--note", "已查看并排图。"],
    );
    assert_eq!(warning_codes(&adopted["warnings"]), ["note_unspecific"]);
}

#[test]
fn adopt_reports_shared_layout_for_three_result_pages_in_this_run() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    cli(path, &["new", path.to_str().unwrap()]);
    edit(
        path,
        json!({"order":["p1","p2","p3"],"pages":[
            {"id":"p1","content":{"title":"Alpha"}},
            {"id":"p2","content":{"title":"Beta"}},
            {"id":"p3","content":{"title":"Gamma"}}
        ]}),
    );
    let run = cli(path, &["run", "start", "native", "--pages", "p1,p2,p3"]);
    let run_id = run["runs"][0]["id"].as_i64().unwrap();
    for page in ["p1", "p2", "p3"] {
        seed_native_candidate(path, run_id, page, [40, 30, 500, 48], [24, 24, 10, 36]);
    }
    let adopted = cli(
        path,
        &[
            "run",
            "adopt",
            &run_id.to_string(),
            "p2",
            "--note",
            "标题框在原图标题带内，三列顺序与原图一致",
        ],
    );
    let ids: Vec<_> = adopted["warnings"]
        .as_array()
        .unwrap()
        .iter()
        .map(|warning| warning["page_id"].as_str().unwrap())
        .collect();
    assert_eq!(ids, ["p1", "p2", "p3"]);
    assert_eq!(
        warning_codes(&adopted["warnings"]),
        ["shared_layout", "shared_layout", "shared_layout"]
    );
}

fn shared_plan(path: &Path, page: &str, title: &str, body_y: i64) -> std::path::PathBuf {
    let plan = json!({"schema":"deck.native_plan.v1", "page":page,
    "canvas_px":{"w":800,"h":450},"background":"FFFFFF","ops":[
        {"op":"text","text":title,"atom_id":format!("atom:{page}:title"),
         "bbox":[40,30,500,48],"size":32},
        {"op":"shape","type":"rect","bbox":[24,24,10,36],"fill":"CCDDEE"},
        {"op":"text","text":"","atom_id":format!("atom:{page}:subtitle"),"bbox":[40,90,500,12],"size":12},
        {"op":"shape","type":"ellipse","bbox":[80,body_y,60,24],"fill":"225588"},
        {"op":"image","file":"asset.png","bbox":[20,200,80,80]},
        {"op":"icon","icon_id":"tabler-outline/anchor","bbox":[200,200,40,40]}
    ]});
    let filename = path.join(format!("{page}-plan.json"));
    std::fs::write(&filename, plan.to_string()).unwrap();
    filename
}

#[test]
#[ignore = "needs node + pptxgenjs + soffice; runs in the render job"]
fn shared_layout_on_build_keeps_readback_pass() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    cli(path, &["new", path.to_str().unwrap()]);
    edit(
        path,
        json!({"order":["p1","p2","p3"],"pages":[
            {"id":"p1","content":{"title":"Alpha"},"notes":"第一页讲稿"},
            {"id":"p2","content":{"title":"Beta"},"notes":"第二页讲稿"},
            {"id":"p3","content":{"title":"Gamma"},"notes":"第三页讲稿"}
        ]}),
    );
    python(&[
        "-c",
        "from PIL import Image; import sys; from pathlib import Path; p=Path(sys.argv[1]); Image.new('RGB',(800,450),'white').save(p/'source.png'); Image.new('RGB',(40,40),'teal').save(p/'asset.png'); print('{}')",
        path.to_str().unwrap(),
    ]);
    let image =
        cli(path, &["run", "start", "image", "--pages", "p1,p2,p3"])["runs"][0]["id"].to_string();
    for id in ["p1", "p2", "p3"] {
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
    let run_id =
        cli(path, &["run", "start", "native", "--pages", "p1,p2,p3"])["runs"][0]["id"].to_string();
    let plans = [
        shared_plan(path, "p1", "Alpha", 140),
        shared_plan(path, "p2", "Beta", 180),
        shared_plan(path, "p3", "Gamma", 220),
    ];
    for (index, plan_path) in plans.iter().enumerate() {
        let page = format!("p{}", index + 1);
        let result = cli(
            path,
            &["run", "result", &run_id, &page, plan_path.to_str().unwrap()],
        );
        assert_eq!(result["adopted"], false);
        let codes = result["findings"]
            .get("warnings")
            .map(warning_codes)
            .unwrap_or_default();
        if index < 2 {
            assert!(!codes.contains(&"shared_layout"), "{codes:?}");
        } else {
            assert_eq!(codes, ["shared_layout"]);
        }
        assert!(!codes.contains(&"canvas_not_original"));
    }
    for (page, note) in [
        ("p1", "标题框在原图标题带内，左侧色条与原图同宽"),
        ("p2", "标题框在原图标题带内，中部椭圆比前一页更低"),
        ("p3", "标题框在原图标题带内，底部图标仍在右侧"),
    ] {
        let adopted = cli(path, &["run", "adopt", &run_id, page, "--note", note]);
        assert_eq!(
            warning_codes(&adopted["warnings"]),
            ["shared_layout", "shared_layout", "shared_layout"]
        );
    }
    let built = cli(path, &["build"]);
    assert_eq!(built["findings"]["status"], "pass");
    assert_eq!(
        warning_codes(&built["warnings"]),
        ["shared_layout", "shared_layout", "shared_layout"]
    );
    let exported = cli(path, &["export", "pptx"]);
    assert_eq!(
        warning_codes(&exported["warnings"]),
        ["shared_layout", "shared_layout", "shared_layout"]
    );
}
