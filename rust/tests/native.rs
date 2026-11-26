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
    // Fill generation-required page fields for non-gate native fixtures.
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

fn cli(path: &Path, args: &[&str]) -> Value {
    if args.first() == Some(&"run") && args.get(1) == Some(&"start") {
        allow_runs(path);
    }
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
#[ignore = "needs soffice; runs in the render job"]
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
    let store = Store::open(path).unwrap();
    let current = store.current().unwrap();
    let adopted = current.deck.pages[0].native.as_ref().unwrap();
    assert_ne!(adopted.file, candidate);
    assert!(adopted.basis.starts_with("svg-v3:"));
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
    // Before p2 adopts either native or svg, partial build reports p2 as missing.
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

#[test]
#[ignore = "needs soffice; runs in the render job"]
fn corrupt_sibling_pack_still_lets_the_other_page_result_and_adopt() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    cli(path, &["new", path.to_str().unwrap()]);
    edit(
        path,
        json!({"order":["p1","p2"],"pages":[
            {"id":"p1","content":{"title":"Alpha"}},
            {"id":"p2","content":{"title":"Beta"}}
        ]}),
    );
    python(&[
        "-c",
        "from PIL import Image; import sys; from pathlib import Path; p=Path(sys.argv[1]); Image.new('RGB',(800,450),'white').save(p/'source.png'); Image.new('RGB',(40,40),'teal').save(p/'asset.png'); print('{}')",
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
    let run_id = cli(path, &["run", "start", "native", "--pages", "p1,p2"])["runs"][0]["id"]
        .as_i64()
        .unwrap();
    seed_native_candidate(path, run_id, "p1", [40, 30, 500, 48], [24, 24, 10, 36]);
    let store = Store::open(path).unwrap();
    let corrupt: String = store
        .connection
        .query_row(
            "SELECT result_file FROM run_pages WHERE run_id=?1 AND page_id=?2",
            (run_id, "p1"),
            |row| row.get(0),
        )
        .unwrap();
    std::fs::write(store.file(&corrupt).unwrap(), b"not a pack").unwrap();
    drop(store);
    let plan = shared_plan(path, "p2", "Beta", 180);
    let run_text = run_id.to_string();
    let result = cli(
        path,
        &["run", "result", &run_text, "p2", plan.to_str().unwrap()],
    );
    assert_eq!(result["adopted"], false);
    let adopted = cli(
        path,
        &[
            "run",
            "adopt",
            &run_text,
            "p2",
            "--note",
            "标题框在原图标题带内，中部椭圆比前一页更低",
        ],
    );
    assert_eq!(adopted["runs"][0]["pages"][1]["status"], "done");
    let failed = command(
        path,
        &[
            "run",
            "adopt",
            &run_text,
            "p1",
            "--note",
            "标题框在原图标题带内，这一页的包已损坏",
        ],
    );
    assert_ne!(failed.status.code(), Some(0));
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
#[ignore = "needs soffice; runs in the render job"]
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

#[test]
fn native_result_rejects_escaped_and_non_png_jpeg_image_assets_without_storing_files() {
    let temp = tempfile::tempdir().unwrap();
    let project = temp.path().join("project");
    let outside = temp.path().join("secret.png");
    // Minimal valid 1x1 PNG so image run result accepts it cleanly.
    let png: &[u8] = &[
        0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a, 0x00, 0x00, 0x00, 0x0d, 0x49, 0x48, 0x44,
        0x52, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01, 0x08, 0x02, 0x00, 0x00, 0x00, 0x90,
        0x77, 0x53, 0xde, 0x00, 0x00, 0x00, 0x0c, 0x49, 0x44, 0x41, 0x54, 0x08, 0xd7, 0x63, 0xf8,
        0xcf, 0xc0, 0x00, 0x00, 0x03, 0x01, 0x01, 0x00, 0x18, 0xdd, 0x8d, 0xb0, 0x00, 0x00, 0x00,
        0x00, 0x49, 0x45, 0x4e, 0x44, 0xae, 0x42, 0x60, 0x82,
    ];
    std::fs::write(&outside, png).unwrap();

    cli(
        &project,
        &["new", project.to_str().unwrap(), "--title", "原生路径测试"],
    );
    edit(
        &project,
        json!({"order":["p1"],"pages":[{"id":"p1","purpose":"说明","layout":"左图右文","content":{"title":"合成标题"}}]}),
    );
    let image_run =
        cli(&project, &["run", "start", "image", "--pages", "p1"])["runs"][0]["id"].to_string();
    cli(
        &project,
        &["run", "result", &image_run, "p1", outside.to_str().unwrap()],
    );
    let run_id =
        cli(&project, &["run", "start", "native", "--pages", "p1"])["runs"][0]["id"].to_string();

    let work_dir = temp.path().join("plan-work");
    std::fs::create_dir_all(&work_dir).unwrap();
    let gif_path = work_dir.join("anim.gif");
    std::fs::write(&gif_path, b"GIF89a\x01\x00\x01\x00").unwrap();
    #[cfg(unix)]
    std::os::unix::fs::symlink(&outside, work_dir.join("link.png")).unwrap();

    let files_dir = project.join(".deck/files");
    let before_count = std::fs::read_dir(&files_dir).unwrap().count();

    let mut bad_files = vec![
        outside.to_str().unwrap().to_string(),
        "../secret.png".to_string(),
        "anim.gif".to_string(),
        "missing.png".to_string(),
    ];
    #[cfg(unix)]
    bad_files.push("link.png".to_string());

    for bad in bad_files {
        let plan_path = work_dir.join("plan.json");
        let plan = json!({
            "schema": "deck.native_plan.v1",
            "page": "p1",
            "canvas_px": {"w": 800, "h": 450},
            "background": "FFFFFF",
            "ops": [
                {"op": "text", "atom_id": "p1:title", "text": "合成标题", "bbox": [20, 20, 300, 40]},
                {"op": "image", "file": bad, "bbox": [500, 100, 100, 100]}
            ]
        });
        std::fs::write(&plan_path, serde_json::to_vec(&plan).unwrap()).unwrap();
        let output = command(
            &project,
            &["run", "result", &run_id, "p1", plan_path.to_str().unwrap()],
        );
        assert_eq!(
            output.status.code(),
            Some(2),
            "expected exit 2 for {bad}, stderr={}",
            String::from_utf8_lossy(&output.stderr)
        );
        assert_eq!(
            std::fs::read_dir(&files_dir).unwrap().count(),
            before_count,
            "rejected asset {bad} must not write into .deck/files"
        );
    }
}

#[test]
fn native_cli_icon_search_crop_and_validate_end_to_end() {
    let temp = tempfile::tempdir().unwrap();
    let project = temp.path().join("project");

    // 1. deck icon search works for both Chinese commercial terms and English tags without needing a project.
    let zh = cli(&project, &["icon", "search", "供应链", "--limit", "5"]);
    assert_eq!(zh["query"], "供应链");
    let zh_ids: Vec<&str> = zh["icons"]
        .as_array()
        .unwrap()
        .iter()
        .map(|item| item["icon_id"].as_str().unwrap())
        .collect();
    assert!(!zh_ids.is_empty());
    assert!(
        zh_ids.iter().all(|id| id.starts_with("tabler-outline/")),
        "unexpected icon ids: {zh_ids:?}"
    );
    assert!(
        zh_ids
            .iter()
            .any(|id| id.contains("truck") || id.contains("package")),
        "expected supply-chain icon in {zh_ids:?}"
    );

    let en = cli(&project, &["icon", "search", "shield", "--limit", "5"]);
    let en_ids: Vec<&str> = en["icons"]
        .as_array()
        .unwrap()
        .iter()
        .map(|item| item["icon_id"].as_str().unwrap())
        .collect();
    assert_eq!(en_ids.first().copied(), Some("tabler-outline/shield"));

    // 2. Prepare project with a 400x200 source PNG and start a native run.
    cli(
        &project,
        &["new", project.to_str().unwrap(), "--title", "C16 原生命令"],
    );
    edit(
        &project,
        json!({
            "order": ["p1"],
            "pages": [{
                "id": "p1",
                "purpose": "演示原生工具链",
                "layout": "左图右文",
                "content": {"title": "供应链安全方案", "subtitle": "核心举措"}
            }]
        }),
    );
    let source_img = temp.path().join("source.png");
    let py = std::env::var_os("DECK_TOOLS_PYTHON").expect("install this worktree's deck-tools");
    let made = Command::new(py)
        .args([
            "-c",
            "from PIL import Image; import sys; Image.new('RGB', (400, 200), (240, 245, 250)).save(sys.argv[1])",
            source_img.to_str().unwrap(),
        ])
        .output()
        .unwrap();
    assert!(made.status.success());

    let image_run =
        cli(&project, &["run", "start", "image", "--pages", "p1"])["runs"][0]["id"].to_string();
    cli(
        &project,
        &[
            "run",
            "result",
            &image_run,
            "p1",
            source_img.to_str().unwrap(),
        ],
    );
    let started = cli(&project, &["run", "start", "native", "--pages", "p1"]);
    let run_id = started["runs"][0]["id"].to_string();
    let work_dir =
        Path::new(started["runs"][0]["pages"][0]["work"].as_str().unwrap()).to_path_buf();
    let task_md = std::fs::read_to_string(work_dir.join("task.md")).unwrap();
    assert!(task_md.contains("deck icon search"));
    assert!(task_md.contains("deck run crop"));
    assert!(task_md.contains("deck run validate"));

    // 3. deck run crop writes only into work/<run>/<ordinal>/assets/<name>.png and rejects path traversal.
    let cropped = cli(
        &project,
        &[
            "run",
            "crop",
            &run_id,
            "p1",
            "--bbox",
            "20,10,120,80",
            "--name",
            "hero_card",
        ],
    );
    assert_eq!(cropped["relative_path"], "assets/hero_card.png");
    assert_eq!(cropped["width"], 120);
    assert_eq!(cropped["height"], 80);
    assert_eq!(cropped["format"], "PNG");
    let expected_crop = work_dir.join("assets").join("hero_card.png");
    assert!(expected_crop.is_file());
    assert_eq!(
        Path::new(cropped["path"].as_str().unwrap())
            .canonicalize()
            .unwrap(),
        expected_crop.canonicalize().unwrap()
    );

    let bad_crop = command(
        &project,
        &[
            "run",
            "crop",
            &run_id,
            "p1",
            "--bbox",
            "0,0,50,50",
            "--name",
            "../escape",
        ],
    );
    assert_eq!(bad_crop.status.code(), Some(2));

    // 4. deck run validate checks valid plans and catches bad colors / escaped paths without changing DB.
    let before_version = Store::open(&project).unwrap().current().unwrap().version;
    let plan_path = work_dir.join("plan.json");
    let valid_plan = json!({
        "schema": "deck.native_plan.v1",
        "page": "p1",
        "canvas_px": {"w": 400, "h": 200},
        "background": "#FFFFFF",
        "ops": [
            {"op": "text", "atom_id": "atom:p1:title", "text": "供应链安全方案", "bbox": [20, 20, 200, 36]},
            {"op": "text", "atom_id": "atom:p1:subtitle", "text": "核心举措", "bbox": [20, 56, 200, 20]},
            {"op": "icon", "icon_id": en_ids[0], "bbox": [240, 20, 32, 32], "color": "#225588"},
            {"op": "image", "file": "assets/hero_card.png", "bbox": [20, 80, 120, 80]}
        ]
    });
    std::fs::write(&plan_path, serde_json::to_vec_pretty(&valid_plan).unwrap()).unwrap();
    let validated = cli(
        &project,
        &[
            "run",
            "validate",
            &run_id,
            "p1",
            plan_path.to_str().unwrap(),
        ],
    );
    assert_eq!(validated["valid"], true);
    assert_eq!(validated["atoms"], 2);

    // Ensure run validate did not submit result or modify version.
    assert_eq!(
        Store::open(&project).unwrap().current().unwrap().version,
        before_version
    );
    let shown = cli(&project, &["run", "show", &run_id]);
    assert_eq!(shown["runs"][0]["pages"][0]["status"], "pending");

    // Invalid hex color -> exit 2
    let bad_color_path = work_dir.join("bad-color.json");
    let bad_color = json!({
        "schema": "deck.native_plan.v1",
        "page": "p1",
        "canvas_px": {"w": 400, "h": 200},
        "background": "not-a-color",
        "ops": [
            {"op": "text", "atom_id": "atom:p1:title", "text": "供应链安全方案", "bbox": [20, 20, 200, 36]}
        ]
    });
    std::fs::write(&bad_color_path, serde_json::to_vec(&bad_color).unwrap()).unwrap();
    let color_out = command(
        &project,
        &[
            "run",
            "validate",
            &run_id,
            "p1",
            bad_color_path.to_str().unwrap(),
        ],
    );
    assert_eq!(color_out.status.code(), Some(2));

    // Escaped image path -> exit 2
    let bad_path_plan = work_dir.join("bad-path.json");
    let bad_path = json!({
        "schema": "deck.native_plan.v1",
        "page": "p1",
        "canvas_px": {"w": 400, "h": 200},
        "background": "#FFFFFF",
        "ops": [
            {"op": "text", "atom_id": "atom:p1:title", "text": "供应链安全方案", "bbox": [20, 20, 200, 36]},
            {"op": "image", "file": "../outside.png", "bbox": [20, 80, 120, 80]}
        ]
    });
    std::fs::write(&bad_path_plan, serde_json::to_vec(&bad_path).unwrap()).unwrap();
    let path_out = command(
        &project,
        &[
            "run",
            "validate",
            &run_id,
            "p1",
            bad_path_plan.to_str().unwrap(),
        ],
    );
    assert_eq!(path_out.status.code(), Some(2));
}

#[test]
fn mixed_svg_and_native_deck_builds_all_three_slides_and_passes_readback() {
    let temp = tempfile::tempdir().unwrap();
    let project = temp.path().join("mixed-project");

    // Pick a system font guaranteed to be installed in both macOS and Ubuntu CI.
    let font_out = Command::new("fc-match")
        .args(["-f", "%{family}", "sans-serif"])
        .output()
        .unwrap();
    let family = String::from_utf8_lossy(&font_out.stdout)
        .split(',')
        .next()
        .unwrap_or("DejaVu Sans")
        .trim()
        .to_string();

    cli(
        &project,
        &["new", project.to_str().unwrap(), "--title", "混合构建测试"],
    );
    edit(
        &project,
        json!({
            "style": {"fonts": [&family]},
            "order": ["p1", "p2", "p3"],
            "pages": [
                {"id": "p1", "purpose": "概述", "layout": "单栏", "notes": "第一页讲稿", "content": {"title": "SVG 第一页"}},
                {"id": "p2", "purpose": "细节", "layout": "双栏", "notes": "第二页讲稿", "content": {"title": "SVG 第二页"}},
                {"id": "p3", "purpose": "结论", "layout": "卡片", "notes": "第三页讲稿", "content": {"title": "Native 第三页"}}
            ]
        }),
    );

    let store = Store::open(&project).unwrap();
    let mut deck = store.current().unwrap().deck;

    let svg1 = format!(
        r##"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720"><rect x="0" y="0" width="1280" height="720" fill="#FFFFFF"/><text x="60" y="90" font-family="{family}" font-size="32" fill="#111111" data-atom-id="atom:p1:title">SVG 第一页</text></svg>"##
    );
    let svg2 = format!(
        r##"<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720"><rect x="0" y="0" width="1280" height="720" fill="#F8FAFC"/><text x="60" y="90" font-family="{family}" font-size="32" fill="#111111" data-atom-id="atom:p2:title">SVG 第二页</text></svg>"##
    );
    let f1 = store.add_file(svg1.as_bytes(), "svg").unwrap();
    let f2 = store.add_file(svg2.as_bytes(), "svg").unwrap();
    let pack3 = json!({
        "plan": {
            "schema": "deck.native_plan.v1",
            "page": "p3",
            "canvas_px": {"w": 1280, "h": 720},
            "background": "#FFFFFF",
            "ops": [
                {"op": "text", "atom_id": "atom:p3:title", "text": "Native 第三页", "bbox": [60, 50, 600, 60], "font": &family, "size": 32, "color": "#1D4ED8"}
            ]
        },
        "assets": [],
        "render_png": "",
        "note": "标题框与文字一致"
    });
    let f3 = store
        .add_file(&serde_json::to_vec(&pack3).unwrap(), "native.json")
        .unwrap();

    deck.pages[0].svg = Some(Artifact {
        file: f1,
        basis: ops::basis("svg", &deck, &deck.pages[0]).unwrap(),
    });
    deck.pages[1].svg = Some(Artifact {
        file: f2,
        basis: ops::basis("svg", &deck, &deck.pages[1]).unwrap(),
    });
    deck.pages[2].native = Some(Artifact {
        file: f3,
        basis: ops::basis("native", &deck, &deck.pages[2]).unwrap(),
    });

    let mut store = Store::open(&project).unwrap();
    let tx = store.transaction().unwrap();
    store::append(&tx, &mut deck, "Adopt mixed SVG and native pages").unwrap();
    tx.commit().unwrap();

    let status = ops::artifact_status(&deck).unwrap();
    assert_eq!(status["build_mode"], "mixed");
    assert_eq!(status["missing_pages"], json!([]));

    let built = cli(&project, &["build"]);
    assert_eq!(built["build_mode"], "mixed");
    assert_eq!(built["missing_pages"], json!([]));
    assert_eq!(built["findings"]["status"], "pass");
    assert_eq!(built["findings"]["findings"], json!([]));

    let detail = ops::build_detail(&project, built["id"].as_i64().unwrap()).unwrap();
    assert_eq!(detail["pages"].as_array().unwrap().len(), 3);
    assert_eq!(detail["readback_matches_current"], true);
}
