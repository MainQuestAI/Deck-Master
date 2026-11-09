use deck::{
    model::Patch,
    ops,
    store::{self, Store},
};
use serde_json::{Value, json};
use std::path::Path;
use std::process::Command;

fn setup(path: &Path) {
    ops::new(path, "合成技术方案".into()).unwrap();
    let patch: Patch = serde_json::from_value(json!({"order":["p1","p2"],"pages":[{"id":"p1","content":{"title":"Decision"}},{"id":"p2","content":{"title":"Next"}}]})).unwrap();
    ops::put(path, 1, patch).unwrap();
}
fn edit(path: &Path, value: Value) {
    let base = Store::open(path).unwrap().current().unwrap().version;
    ops::put(path, base, serde_json::from_value(value).unwrap()).unwrap();
}
fn png(path: &Path) {
    let python = std::env::var_os("DECK_TOOLS_PYTHON").expect("install this worktree's deck-tools");
    assert!(Command::new(python).args(["-c", "from PIL import Image; import sys; Image.new('RGB',(16,16),'teal').save(sys.argv[1])"]).arg(path).status().unwrap().success());
}
fn start(path: &Path, max: i64) -> i64 {
    ops::run_start(path, "image", &["p1".into()], Some(max)).unwrap()["runs"][0]["id"]
        .as_i64()
        .unwrap()
}

fn available_font() -> String {
    let font = Command::new("fc-match")
        .args(["-f", "%{family}", "sans-serif"])
        .output()
        .unwrap();
    assert!(font.status.success());
    let families = String::from_utf8(font.stdout).unwrap();
    families.split(',').next().unwrap().trim().to_string()
}

fn put_available_build_font(path: &Path) {
    let snapshot = Store::open(path).unwrap().current().unwrap();
    let mut style = serde_json::to_value(&snapshot.deck.style).unwrap();
    style["fonts"] = json!([available_font()]);
    ops::put(
        path,
        snapshot.version,
        serde_json::from_value(json!({"style": style})).unwrap(),
    )
    .unwrap();
}
#[test]
fn cancelled_late_result_is_saved_and_manual_adoption_keeps_author_edits() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let image = path.join("result.png");
    png(&image);
    let id = start(path, 2);
    ops::run_call(path, id, "p1", false).unwrap();
    ops::run_cancel(path, id).unwrap();
    assert!(ops::run_call(path, id, "p1", true).is_err());
    edit(path, json!({"pages":[{"id":"p1","notes":"作者新讲稿"}]}));
    let result = ops::run_result(path, id, "p1", &image).unwrap();
    assert_eq!(result["adopted"], false);
    let store = Store::open(path).unwrap();
    assert!(
        store
            .file(result["file"].as_str().unwrap())
            .unwrap()
            .is_file()
    );
    assert!(store.current().unwrap().deck.pages[0].image.is_none());
    assert_eq!(result["run"]["runs"][0]["pages"][0]["status"], "unadopted");
    ops::run_adopt(path, id, "p1").unwrap();
    let page = &Store::open(path).unwrap().current().unwrap().deck.pages[0];
    assert!(page.image.is_some());
    assert_eq!(page.notes, "作者新讲稿");
}
#[test]
fn changed_basis_is_not_adopted_but_notes_alone_do_not_stale_images() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let image = path.join("result.png");
    png(&image);
    let id = start(path, 2);
    ops::run_call(path, id, "p1", false).unwrap();
    edit(path, json!({"pages":[{"id":"p1","layout":"新布局"}]}));
    assert_eq!(
        ops::run_result(path, id, "p1", &image).unwrap()["adopted"],
        false
    );
    assert!(
        Store::open(path).unwrap().current().unwrap().deck.pages[0]
            .image
            .is_none()
    );
    ops::run_cancel(path, id).unwrap();
    let id = start(path, 2);
    ops::run_call(path, id, "p1", false).unwrap();
    edit(path, json!({"pages":[{"id":"p1","notes":"只改讲稿"}]}));
    assert_eq!(
        ops::run_result(path, id, "p1", &image).unwrap()["adopted"],
        true
    );
    let version = Store::open(path).unwrap().current().unwrap().version;
    ops::run_result(path, id, "p1", &image).unwrap();
    assert_eq!(
        Store::open(path).unwrap().current().unwrap().version,
        version
    );
    assert_eq!(
        ops::run_show(path, Some(id)).unwrap()["runs"][0]["status"],
        "done"
    );
}
#[test]
fn open_multi_page_run_keeps_replacements_and_delayed_results_as_candidates() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let a = path.join("a.png");
    let b = path.join("b.png");
    png(&a);
    let python = std::env::var_os("DECK_TOOLS_PYTHON").unwrap();
    assert!(
        Command::new(python)
            .args([
                "-c",
                "from PIL import Image; import sys; Image.new('RGB',(8,8),'navy').save(sys.argv[1])"
            ])
            .arg(&b)
            .status()
            .unwrap()
            .success()
    );
    let id = ops::run_start(path, "image", &["p1".into(), "p2".into()], Some(4)).unwrap()["runs"]
        [0]["id"]
        .as_i64()
        .unwrap();
    ops::run_call(path, id, "p1", false).unwrap();
    let first = ops::run_result(path, id, "p1", &a).unwrap();
    assert_eq!(first["adopted"], true);
    assert_eq!(first["run"]["runs"][0]["status"], "open");
    let original = ops::get(path, None).unwrap();
    ops::run_result(path, id, "p1", &a).unwrap();
    assert_eq!(ops::get(path, None).unwrap(), original);
    // A fresh call can set started, but cannot make a replacement the first result.
    ops::run_call(path, id, "p1", false).unwrap();
    let candidate = ops::run_result(path, id, "p1", &b).unwrap();
    assert_eq!(candidate["adopted"], false);
    assert_eq!(
        candidate["run"]["runs"][0]["pages"][0]["status"],
        "unadopted"
    );
    assert_eq!(ops::get(path, None).unwrap(), original);
    ops::run_adopt(path, id, "p1").unwrap();
    let chosen = ops::get(path, None).unwrap();
    assert_eq!(
        chosen["deck"]["pages"][0]["image"]["file"],
        candidate["file"]
    );
    let delayed = ops::run_result(path, id, "p1", &a).unwrap();
    assert_eq!(delayed["adopted"], false);
    assert_eq!(delayed["run"]["runs"][0]["pages"][0]["status"], "unadopted");
    assert_eq!(ops::get(path, None).unwrap(), chosen);
    ops::run_result(path, id, "p1", &a).unwrap();
    assert_eq!(ops::get(path, None).unwrap(), chosen);
    ops::run_call(path, id, "p1", false).unwrap();
    let returned = ops::run_result(path, id, "p1", &a).unwrap();
    assert_eq!(
        returned["run"]["runs"][0]["pages"][0]["status"],
        "unadopted"
    );
    assert_eq!(ops::get(path, None).unwrap(), chosen);
}

#[test]
fn changed_basis_manual_adoption_replaces_existing_image_and_keeps_stale_hint() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let image = path.join("result.png");
    png(&image);
    let first = start(path, 1);
    ops::run_call(path, first, "p1", false).unwrap();
    let first_result = ops::run_result(path, first, "p1", &image).unwrap();
    let id = start(path, 1);
    ops::run_call(path, id, "p1", false).unwrap();
    edit(path, json!({"pages":[{"id":"p1","layout":"新布局"}]}));
    let python = std::env::var_os("DECK_TOOLS_PYTHON").unwrap();
    assert!(
        Command::new(python)
            .args([
                "-c",
                "from PIL import Image; import sys; Image.new('RGB',(8,8),'navy').save(sys.argv[1])"
            ])
            .arg(&image)
            .status()
            .unwrap()
            .success()
    );
    let result = ops::run_result(path, id, "p1", &image).unwrap();
    assert_eq!(result["adopted"], false);
    assert_ne!(result["file"], first_result["file"]);
    let before = Store::open(path).unwrap().current().unwrap();
    assert_eq!(
        before.deck.pages[0].image.as_ref().unwrap().file,
        first_result["file"]
    );
    let candidate = &ops::workspace(path).unwrap()["runs"][0]["pages"][0];
    assert_ne!(candidate["result_url"], candidate["current_image_url"]);
    let store = Store::open(path).unwrap();
    assert_ne!(
        std::fs::read(store.file(result["file"].as_str().unwrap()).unwrap()).unwrap(),
        std::fs::read(store.file(first_result["file"].as_str().unwrap()).unwrap()).unwrap()
    );
    ops::run_adopt(path, id, "p1").unwrap();
    let after = Store::open(path).unwrap().current().unwrap();
    let mut expected = before.deck;
    expected.pages[0].image.as_mut().unwrap().file = result["file"].as_str().unwrap().into();
    assert_eq!(after.deck, expected);
    assert_eq!(after.version, before.version + 1);
    assert_eq!(
        ops::artifact_status(&after.deck).unwrap()["stale_images"],
        json!(["p1"])
    );
}

#[test]
fn unknown_call_requires_explicit_retry_and_cannot_exceed_limit() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let id = start(path, 2);
    assert!(ops::run_start(path, "image", &["p2".into()], None).is_err());
    ops::run_call(path, id, "p1", false).unwrap();
    assert!(ops::run_call(path, id, "p1", false).is_err());
    assert_eq!(
        ops::run_show(path, Some(id)).unwrap()["runs"][0]["calls_used"],
        1
    );
    ops::run_call(path, id, "p1", true).unwrap();
    assert!(ops::run_call(path, id, "p1", true).is_err());
    assert_eq!(
        ops::run_show(path, Some(id)).unwrap()["runs"][0]["calls_used"],
        2
    );
}
#[test]
fn image_run_inlines_readable_page_inputs_and_keeps_svg_inputs_separate() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    edit(
        path,
        json!({
            "style":{"palette":["#164267"],"fonts":["Noto Sans CJK SC"]},
            "pages":[{
                "id":"p1",
                "purpose":"看清处理边界",
                "layout":"预检→执行→完成或退回",
                "notes":"讲稿不入图",
                "todo":["内部待核项"],
                "refs":["材料定位"],
                "content":{
                    "title":"请求处理",
                    "subtitle":"处理容量与状态",
                    "body_blocks":[
                        {"type":"paragraph","text":"完成与退回是互斥结果"},
                        {"type":"bullets","heading":"处理条件","items":[
                            {"text":"满足校验要求","children":[{"text":"校验失败单独记录"}]}
                        ]},
                        {"type":"table","title":"容量上限",
                         "columns":[{"id":"kind","label":"项目"},{"id":"cap","label":"限额"}],
                         "rows":[{"cells":[
                            {"column_id":"cap","display_text":"1,200","unit":"次/日","value":1200},
                            {"column_id":"kind","display_text":"提交"}
                         ]}]}
                    ],
                    "labels":[{"text":"退回"}],
                    "callouts":[{"text":"容量限制按日计算"}],
                    "footnotes":[{"text":"仅适用于正常工作时段"}]
                }
            }]
        }),
    );
    let id = start(path, 1);
    let task = ops::run_show(path, Some(id)).unwrap();
    let work = Path::new(task["runs"][0]["pages"][0]["work"].as_str().unwrap());
    let image = std::fs::read_to_string(work.join("task.md")).unwrap();
    for text in [
        "1280×720",
        "看清处理边界",
        "预检→执行→完成或退回",
        "#164267",
        "Noto Sans CJK SC",
        "请求处理",
        "处理容量与状态",
        "完成与退回是互斥结果",
        "处理条件",
        "- 满足校验要求\n  - 校验失败单独记录",
        "容量上限",
        "| 项目 | 限额 |",
        "| 提交 | 1,200 |",
        "次/日",
        "退回",
        "容量限制按日计算",
        "仅适用于正常工作时段",
        "让主要文字、连线和业务对象可以分开重建",
        "不要为了方便转 SVG 先画成扁平色块",
        "不要把整页当成最后必须压成零张图",
        "pictures=0 不是目标，也不是失败",
    ] {
        assert!(image.contains(text), "image task omits {text}");
    }
    for text in [
        "讲稿不入图",
        "内部待核项",
        "材料定位",
        "content.json",
        "style.json",
    ] {
        assert!(!image.contains(text), "image task contains {text}");
    }
    let attachments: Value =
        serde_json::from_slice(&std::fs::read(work.join("attachments.json")).unwrap()).unwrap();
    assert_eq!(attachments, json!([]));

    let svg = ops::run_start(path, "svg", &["p1".into()], None).unwrap();
    let work = Path::new(svg["runs"][0]["pages"][0]["work"].as_str().unwrap());
    let svg = std::fs::read_to_string(work.join("task.md")).unwrap();
    for requirement in [
        "正文取 content.json",
        "绑定 atoms.json 的 data-atom-id",
        "对应 content.labels（含 children）中标签的节点必须写 data-node-ref，值为该标签 id",
        "有向连线必须写 data-edge-ref",
        "先读 svg-subset.md",
        "reconstruction.md",
        "主要文字、节点、连线、分区、表格和标签必须成为可编辑对象",
        "插画、质感、人物、复杂曲线可保留为有边界的图",
        "图片不能承载唯一正文",
        "禁止把整页原图或蓝图当背景",
        "禁止为了方便转 SVG 先压成扁平色块",
        "禁止为了零张图（pictures=0）把流线或空间关系改成普通矩形或默认流程图",
        "pictures=0 不是目标，也不是失败",
        "对象计数、图片数不能代表质量",
        "流程图、架构图、路径图只用于还原阶段的空间锚点和标签避让",
        "不是规划菜单，也不替代构图句",
        "错漏文字、局部排版和依据明确的连线可沿用原图",
        "业务关系有歧义先问内容",
        "主结构需要重排时先更新蓝图再重建",
    ] {
        assert!(svg.contains(requirement), "SVG task omits {requirement}");
    }
    for text in [
        "完成与退回是互斥结果",
        "校验失败单独记录",
        "1,200",
        "容量限制按日计算",
        "仅适用于正常工作时段",
        "讲稿不入图",
        "内部待核项",
        "材料定位",
    ] {
        assert!(!svg.contains(text), "SVG task inlines {text}");
    }
    assert!(work.join("atoms.json").is_file());
    assert!(work.join("reconstruction.md").is_file());
}

fn svg_reconstruction_task() -> String {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成重建任务".into()).unwrap();
    edit(
        path,
        json!({"order":["p1"],"pages":[{
            "id":"p1",
            "purpose":"看清服务入口与处理步骤",
            "layout":"左侧界面原型，右侧沿原图方向展开处理步骤",
            "content":{"title":"服务示意","body_blocks":[
                {"type":"paragraph","text":"顶区：示例用户｜基础会员｜会员规则"}
            ]}
        }]}),
    );
    let run = ops::run_start(path, "svg", &["p1".into()], None).unwrap();
    let work = Path::new(run["runs"][0]["pages"][0]["work"].as_str().unwrap());
    std::fs::read_to_string(work.join("task.md")).unwrap()
}

#[test]
fn svg_task_requires_original_objects_instead_of_body_block_templates() {
    let task = svg_reconstruction_task();
    let policy = task
        .lines()
        .find(|line| line.starts_with("- 按原图"))
        .unwrap();
    for requirement in [
        "原图对象",
        "布局",
        "层级",
        "关系重建",
        "不按 content.json",
        "默认卡片",
        "默认表",
        "默认清单",
        "不能代替控件或节点",
    ] {
        assert!(policy.contains(requirement), "SVG task omits {requirement}");
    }
}

#[test]
fn svg_task_keeps_ui_controls_separate_from_annotation_atoms_and_crops() {
    let task = svg_reconstruction_task();
    let ui = task
        .lines()
        .find(|line| line.starts_with("- 界面："))
        .unwrap();
    for requirement in [
        "按原图分区",
        "不留空白线框",
        "关键字不足",
        "外侧标注",
        "绑定原 atom",
        "内部控件与文字分别可编辑",
        "不要求拆改 atom",
        "句子保持完整",
        "分别可见",
    ] {
        assert!(ui.contains(requirement), "UI task omits {requirement}");
    }
    let crops = task
        .lines()
        .find(|line| line.starts_with("- 局部素材："))
        .unwrap();
    for requirement in [
        "头像",
        "SVG 子集",
        "有边界的局部 PNG/JPEG",
        "先 deck asset add",
        "image 引用素材 ID",
        "重新准备 SVG",
        "新附件",
        "关键文字须可编辑",
        "示意属性",
        "不能冒充真实产品截图",
    ] {
        assert!(crops.contains(requirement), "crop task omits {requirement}");
    }
    assert!(task.contains("禁止把整页原图或蓝图当背景"));
}

#[test]
fn svg_task_keeps_journey_scenes_and_directional_steps_with_lookup_exception() {
    let task = svg_reconstruction_task();
    let journey = task
        .lines()
        .find(|line| line.starts_with("- 顾客旅程："))
        .unwrap();
    let (scenes, path) = journey.split_once("有方向的步骤").unwrap();
    for requirement in [
        "步骤空间顺序",
        "人物、动作、场景层",
        "不能只剩",
        "模块卡片",
        "除非原图",
    ] {
        assert!(
            scenes.contains(requirement),
            "journey task omits {requirement}"
        );
    }
    for requirement in [
        "节点边界",
        "连线端点",
        "方向",
        "分支",
        "回流",
        "不收成箭头句",
        "两列清单",
        "原图本就是",
        "逐行核对",
        "查阅清单时例外",
    ] {
        assert!(path.contains(requirement), "path task omits {requirement}");
    }
}

#[test]
fn svg_task_requires_opened_original_comparison_beyond_text_and_findings() {
    let task = svg_reconstruction_task();
    let acceptance = task.split("验收要点：").nth(1).unwrap();
    for object in [
        "实际打开",
        "预览 PNG",
        "原图",
        "对照功能时使用",
        "身份／资产",
        "分入口",
        "内容区可视物",
        "服务或操作入口",
        "旅程步骤空间顺序",
        "动作／场景层",
        "路径节点",
        "端点",
        "方向",
        "分支",
        "回流",
        "层级",
        "侧栏",
        "阅读顺序",
        "对象缺失",
        "说明文字",
        "默认卡片",
        "清单",
    ] {
        assert!(acceptance.contains(object), "comparison omits {object}");
    }
    for check in [
        "文字回读",
        "字符串齐全",
        "对象计数",
        "图片数",
        "机械 findings",
        "不能代替对照原图",
        "未比对对象与关系",
        "重建未完成",
        "visual_review",
        "desktop_editing",
        "not_evaluated",
        "不改成自动通过",
    ] {
        assert!(acceptance.contains(check), "comparison omits {check}");
    }
}

#[test]
fn asset_bytes_are_attached_to_host_task_without_using_ids_as_paths() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let image = path.join("logo.png");
    png(&image);
    let asset = ops::asset_add(path, "../logo", &image, &[], "", "").unwrap();
    let id = start(path, 2);
    let task = ops::run_show(path, Some(id)).unwrap();
    let directory = Path::new(task["runs"][0]["pages"][0]["work"].as_str().unwrap());
    let attachments: Value =
        serde_json::from_slice(&std::fs::read(directory.join("attachments.json")).unwrap())
            .unwrap();
    assert_eq!(attachments[0]["id"], "../logo");
    assert_eq!(
        std::fs::read(directory.join(attachments[0]["file"].as_str().unwrap())).unwrap(),
        std::fs::read(&image).unwrap()
    );
    assert_eq!(
        asset["asset"]["file"],
        Store::open(path)
            .unwrap()
            .current()
            .unwrap()
            .deck
            .style
            .assets[0]
            .file
    );
}
#[test]
fn failed_svg_and_corrupt_bitmap_publish_no_artifact() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let broken = path.join("broken.svg");
    std::fs::write(&broken, "<svg viewBox='0 0 100 100'><script/></svg>").unwrap();
    let run = ops::run_start(path, "svg", &["p1".into()], None).unwrap();
    let id = run["runs"][0]["id"].as_i64().unwrap();
    assert_eq!(
        ops::run_result(path, id, "p1", &broken)
            .unwrap_err()
            .exit_code(),
        4
    );
    assert!(
        Store::open(path).unwrap().current().unwrap().deck.pages[0]
            .svg
            .is_none()
    );
    let bad = path.join("broken.png");
    std::fs::write(&bad, b"not a bitmap").unwrap();
    let id = start(path, 1);
    ops::run_call(path, id, "p1", false).unwrap();
    assert!(ops::run_result(path, id, "p1", &bad).is_err());
    assert!(
        Store::open(path).unwrap().current().unwrap().deck.pages[0]
            .image
            .is_none()
    );
}
#[test]
fn build_retains_notes_reports_missing_and_export_compares_inputs_after_restore() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    put_available_build_font(path);
    let mut store = Store::open(path).unwrap();
    let mut snapshot = store.current().unwrap();
    let family = available_font();
    let svg_text = format!(
        "<svg viewBox='0 0 1280 720'><text x='64' y='80' font-size='36' font-family=\"{family}\" data-atom-id='atom:p1:title'>Decision</text></svg>"
    );
    let svg = store.add_file(svg_text.as_bytes(), "svg").unwrap();
    let basis = ops::basis("svg", &snapshot.deck, &snapshot.deck.pages[0]).unwrap();
    snapshot.deck.pages[0].svg = Some(deck::model::Artifact { file: svg, basis });
    snapshot.deck.pages[0].notes = "Speaker notes\n\nLast line\n".into();
    let tx = store.transaction().unwrap();
    let baseline = store::append(&tx, &snapshot.deck, "synthetic compiler fixture").unwrap();
    tx.commit().unwrap();
    let build = ops::build(path).unwrap();
    assert_eq!(build["missing_pages"], json!(["p2"]));
    assert!(Path::new(build["path"].as_str().unwrap()).is_file());
    assert_eq!(ops::export_pptx(path).unwrap()["input_changed"], false);
    edit(
        path,
        json!({"pages":[{"id":"p1","content":{"title":"Changed"}}]}),
    );
    let exported = ops::export_pptx(path).unwrap();
    assert_eq!(exported["input_changed"], false);
    assert_eq!(exported["stale_pages"], json!(["p1"]));
    edit(path, json!({"pages":[{"id":"p1","notes":"Changed notes"}]}));
    assert_eq!(ops::export_pptx(path).unwrap()["input_changed"], true);
    ops::restore(path, baseline).unwrap();
    assert_eq!(ops::export_pptx(path).unwrap()["input_changed"], false);
    for patch in [
        json!({"style":{"canvas":{"width_px":1440,"height_px":900,"slide_width_in":12.0,"slide_height_in":7.5}}}),
        json!({"style":{"fonts":["Changed Font"]}}),
    ] {
        edit(path, patch);
        assert_eq!(ops::export_pptx(path).unwrap()["input_changed"], true);
        ops::restore(path, baseline).unwrap();
        assert_eq!(ops::export_pptx(path).unwrap()["input_changed"], false);
    }
    let asset = path.join("logo.png");
    png(&asset);
    ops::asset_add(path, "logo", &asset, &[], "", "").unwrap();
    assert_eq!(ops::export_pptx(path).unwrap()["input_changed"], true);
    ops::restore(path, baseline).unwrap();
    assert_eq!(ops::export_pptx(path).unwrap()["input_changed"], false);
}
#[test]
fn version_one_database_keeps_versions_files_and_gains_delivery_tables() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    let store = Store::open(path).unwrap();
    let file = store.add_file(b"retained", "txt").unwrap();
    let before = store.current().unwrap();
    store
        .connection
        .execute_batch(
            "DROP TABLE reviews; DROP TABLE run_pages; DROP TABLE runs; DROP TABLE builds; PRAGMA user_version=1;",
        )
        .unwrap();
    drop(store);
    let store = Store::open(path).unwrap();
    assert_eq!(store.current().unwrap().version, before.version);
    assert_eq!(store.current().unwrap().deck, before.deck);
    assert_eq!(
        std::fs::read(store.file(&file).unwrap()).unwrap(),
        b"retained"
    );
    assert_eq!(
        store
            .connection
            .pragma_query_value(None, "user_version", |r| r.get::<_, i64>(0))
            .unwrap(),
        store::FORMAT_VERSION
    );
    start(path, 1);
}

#[test]
fn concurrent_open_migrates_the_old_database_only_once() {
    let temp = tempfile::tempdir().unwrap();
    setup(temp.path());
    let store = Store::open(temp.path()).unwrap();
    store
        .connection
        .execute_batch(
            "DROP TABLE reviews; DROP TABLE run_pages; DROP TABLE runs; DROP TABLE builds; PRAGMA user_version=1;",
        )
        .unwrap();
    drop(store);
    let barrier = std::sync::Arc::new(std::sync::Barrier::new(2));
    let threads: Vec<_> = (0..2)
        .map(|_| {
            let path = temp.path().to_path_buf();
            let barrier = barrier.clone();
            std::thread::spawn(move || {
                barrier.wait();
                Store::open(&path)
                    .unwrap()
                    .current()
                    .unwrap()
                    .deck
                    .pages
                    .len()
            })
        })
        .collect();
    for thread in threads {
        assert_eq!(thread.join().unwrap(), 2);
    }
}

#[test]
fn page_three_redo_and_notes_only_edits_preserve_other_pages_and_existing_build() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, "合成三页方案".into()).unwrap();
    ops::put(
        path,
        1,
        serde_json::from_value(json!({
            "order":["p1","p2","p3"], "pages":[
                {"id":"p1","content":{"title":"Decision"}},
                {"id":"p2","content":{"title":"Decision"}},
                {"id":"p3","content":{"title":"Decision"}}
            ]
        }))
        .unwrap(),
    )
    .unwrap();
    put_available_build_font(path);
    let image = path.join("new.png");
    png(&image);
    let mut store = Store::open(path).unwrap();
    let mut snapshot = store.current().unwrap();
    let old_image = store
        .add_file(&std::fs::read(&image).unwrap(), "png")
        .unwrap();
    let preview = store
        .add_file(&std::fs::read(&image).unwrap(), "png")
        .unwrap();
    let family = available_font();
    for index in 0..3 {
        let basis = ops::basis("image", &snapshot.deck, &snapshot.deck.pages[index]).unwrap();
        snapshot.deck.pages[index].image = Some(deck::model::Artifact {
            file: old_image.clone(),
            basis,
        });
        let page = &snapshot.deck.pages[index];
        let svg = format!(
            "<svg viewBox='0 0 1280 720'><text x='64' y='80' font-size='36' font-family=\"{family}\" data-atom-id='atom:{}:title'>Decision</text></svg>",
            page.id
        );
        let file = store.add_file(svg.as_bytes(), "svg").unwrap();
        let basis = ops::basis("svg", &snapshot.deck, page).unwrap();
        snapshot.deck.pages[index].svg = Some(deck::model::Artifact { file, basis });
        snapshot.deck.pages[index].preview = Some(preview.clone());
    }
    let tx = store.transaction().unwrap();
    let baseline = store::append(&tx, &snapshot.deck, "synthetic three-page fixture").unwrap();
    tx.commit().unwrap();
    let build = ops::build(path).unwrap();
    let build_bytes = std::fs::read(build["path"].as_str().unwrap()).unwrap();
    let build_rows = || {
        let store = Store::open(path).unwrap();
        let mut query = store.connection.prepare("SELECT id,version_id,input_digest,pptx_file,findings_json,missing_pages,created_at FROM builds ORDER BY id").unwrap();
        query
            .query_map([], |row| {
                Ok((
                    row.get::<_, i64>(0)?,
                    row.get::<_, i64>(1)?,
                    (2..7)
                        .map(|i| row.get::<_, String>(i).unwrap())
                        .collect::<Vec<_>>(),
                ))
            })
            .unwrap()
            .collect::<std::result::Result<Vec<_>, _>>()
            .unwrap()
    };
    let original_builds = build_rows();
    let original_files: Vec<_> = std::fs::read_dir(path.join(".deck/files"))
        .unwrap()
        .map(|entry| {
            let file = entry.unwrap().path();
            let bytes = std::fs::read(&file).unwrap();
            (file, bytes)
        })
        .collect();
    let python = std::env::var_os("DECK_TOOLS_PYTHON").unwrap();
    assert!(Command::new(python).args(["-c", "from PIL import Image; import sys; Image.new('RGB',(16,16),'navy').save(sys.argv[1])"]).arg(&image).status().unwrap().success());
    let run = ops::run_start(path, "image", &["p3".into()], None).unwrap();
    let id = run["runs"][0]["id"].as_i64().unwrap();
    assert_eq!(run["runs"][0]["pages"].as_array().unwrap().len(), 1);
    assert_eq!(
        Store::open(path).unwrap().current().unwrap().version,
        baseline
    );
    ops::run_call(path, id, "p3", false).unwrap();
    let result = ops::run_result(path, id, "p3", &image).unwrap();
    assert_eq!(result["adopted"], true);
    let after = Store::open(path).unwrap().current().unwrap();
    let mut expected = snapshot.deck.clone();
    expected.pages[2].image.as_mut().unwrap().file = result["file"].as_str().unwrap().into();
    assert_eq!(after.deck, expected);
    assert_eq!(after.version, baseline + 1);
    let exported = ops::export_pptx(path).unwrap();
    assert_eq!(exported["input_changed"], false);
    assert_eq!(exported["missing_pages"], json!([]));
    assert_eq!(exported["stale_pages"], json!(["p3"]));
    assert_eq!(build_rows(), original_builds);
    assert_eq!(
        std::fs::read(exported["path"].as_str().unwrap()).unwrap(),
        build_bytes
    );

    // Isolate a notes-only edit from the intentional stale SVG after image redo.
    let restored = ops::restore(path, baseline).unwrap();
    assert_eq!(ops::export_pptx(path).unwrap()["input_changed"], false);
    let edited = ops::put(
        path,
        restored.version,
        serde_json::from_value(json!({"pages":[{"id":"p3","notes":"只改第三页讲稿"}]})).unwrap(),
    )
    .unwrap();
    let mut expected = snapshot.deck;
    expected.pages[2].notes = "只改第三页讲稿".into();
    assert_eq!(edited.deck, expected);
    let status = ops::export_pptx(path).unwrap();
    assert_eq!(status["input_changed"], true);
    assert_eq!(status["missing_pages"], json!([]));
    assert_eq!(status["stale_pages"], json!([]));
    assert_eq!(
        ops::artifact_status(&edited.deck).unwrap()["stale_images"],
        json!([])
    );
    assert_eq!(build_rows(), original_builds);
    assert_eq!(
        std::fs::read(status["path"].as_str().unwrap()).unwrap(),
        build_bytes
    );
    for (file, bytes) in original_files {
        assert_eq!(std::fs::read(file).unwrap(), bytes);
    }
}

#[test]
fn polled_svg_staleness_inherits_image_staleness_without_changing_basis() {
    use sha2::{Digest, Sha256};
    use std::os::unix::fs::PermissionsExt;
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    setup(path);
    edit(
        path,
        json!({"pages":[{"id":"p1","content":{"title":"增长","body_blocks":[{"type":"paragraph","id":"a1","text":"预期增长 10%"}]}}]}),
    );
    let image = path.join("original.png");
    png(&image);
    let image_run = start(path, 1);
    ops::run_call(path, image_run, "p1", false).unwrap();
    assert_eq!(
        ops::run_result(path, image_run, "p1", &image).unwrap()["adopted"],
        true
    );
    let mut store = Store::open(path).unwrap();
    let mut snapshot = store.current().unwrap();
    let svg_file = store
        .add_file(b"<svg viewBox='0 0 1280 720'/>", "svg")
        .unwrap();
    // Seed the pre-cut persisted formula to detect accidental hash migrations.
    for index in 0..snapshot.deck.pages.len() {
        let page = &snapshot.deck.pages[index];
        let legacy_inputs = json!([
            page.content,
            page.image.as_ref().map(|image| &image.file),
            snapshot.deck.style
        ]);
        snapshot.deck.pages[index].svg = Some(deck::model::Artifact {
            file: svg_file.clone(),
            basis: format!(
                "{:x}",
                Sha256::digest(serde_json::to_vec(&legacy_inputs).unwrap())
            ),
        });
    }
    let tx = store.transaction().unwrap();
    store::append(&tx, &snapshot.deck, "synthetic legacy SVG bases").unwrap();
    tx.commit().unwrap();
    let wrapper = temp.path().join("python-wrapper");
    let script = temp.path().join("tool.py");
    std::fs::write(
        &wrapper,
        "#!/bin/sh\nexec /usr/bin/python3 \"$DECK_TEST_WRAPPER\" \"$@\"\n",
    )
    .unwrap();
    std::fs::set_permissions(&wrapper, std::fs::Permissions::from_mode(0o755)).unwrap();
    std::fs::write(
        &script,
        r#"import sys
if sys.argv[-2] == "atoms":
    print("[]")
else:
    print("unexpected", sys.argv[-2], file=sys.stderr)
    raise SystemExit(1)
"#,
    )
    .unwrap();
    let started = Command::new(env!("CARGO_BIN_EXE_deck"))
        .arg("--project")
        .arg(path)
        .args(["run", "start", "svg", "--pages", "p1,p2"])
        .env("DECK_TOOLS_PYTHON", &wrapper)
        .env("DECK_TEST_WRAPPER", &script)
        .output()
        .unwrap();
    assert!(
        started.status.success(),
        "{}",
        String::from_utf8_lossy(&started.stderr)
    );
    let page = |kind: &str, id: &str| {
        let workspace = ops::workspace(path).unwrap();
        let run = workspace["runs"]
            .as_array()
            .unwrap()
            .iter()
            .find(|run| run["kind"] == kind)
            .unwrap()
            .clone();
        let page = run["pages"]
            .as_array()
            .unwrap()
            .iter()
            .find(|page| page["page_id"] == id)
            .unwrap()
            .clone();
        (workspace["version"].clone(), page)
    };
    let (version, svg) = page("svg", "p1");
    let svg_basis = svg["current_basis"]
        .as_str()
        .expect("current_basis")
        .to_string();
    assert_eq!(svg["basis_changed"], false);
    ops::run_start(path, "image", &["p1".into(), "p2".into()], None).unwrap();
    let (_, image) = page("image", "p1");
    let image_basis = image["current_basis"]
        .as_str()
        .expect("current_basis")
        .to_string();
    let assert_artifacts = |stale: Value| {
        let status = ops::workspace(path).unwrap()["artifact_status"].clone();
        assert_eq!(status["stale_pages"], stale);
        assert_eq!(status["stale_images"], stale);
    };
    assert_artifacts(json!([]));
    edit(path, json!({"pages":[{"id":"p2","notes":"另一页讲稿"}]}));
    let (after_other, svg) = page("svg", "p1");
    assert_ne!(after_other, version);
    assert_eq!(svg["current_basis"], svg_basis);
    assert_eq!(svg["basis_changed"], false);
    assert_eq!(page("image", "p1").1["basis_changed"], false);
    assert_artifacts(json!([]));
    edit(path, json!({"pages":[{"id":"p1","notes":"只改本页讲稿"}]}));
    let (_, svg) = page("svg", "p1");
    assert_eq!(svg["current_basis"], svg_basis);
    assert_eq!(svg["basis_changed"], false);
    let (_, image) = page("image", "p1");
    assert_eq!(image["current_basis"], image_basis);
    assert_eq!(image["basis_changed"], false);
    assert_artifacts(json!([]));

    // Without an original image, layout and purpose remain outside SVG basis.
    let (_, svg) = page("svg", "p2");
    let no_image_basis = svg["current_basis"].clone();
    edit(
        path,
        json!({"pages":[{"id":"p2","layout":"左侧说明，右侧结论","purpose":"查阅下一步"}]}),
    );
    let (_, svg) = page("svg", "p2");
    assert_eq!(svg["current_basis"], no_image_basis);
    assert_eq!(svg["basis_changed"], false);
    assert_artifacts(json!([]));

    edit(path, json!({"pages":[{"id":"p1","layout":"改为两栏"}]}));
    let (_, image) = page("image", "p1");
    let (_, svg) = page("svg", "p1");
    assert_ne!(image["current_basis"], image_basis);
    assert_eq!(image["basis_changed"], true);
    assert_eq!(svg["current_basis"], svg_basis);
    assert_eq!(svg["basis_changed"], true);
    assert_artifacts(json!(["p1"]));

    edit(path, json!({"pages":[{"id":"p1","layout":""}]}));
    assert_eq!(page("svg", "p1").1["basis_changed"], false);
    assert_artifacts(json!([]));
    edit(
        path,
        json!({"pages":[{"id":"p1","purpose":"评估增长预期"}]}),
    );
    let (_, image) = page("image", "p1");
    let (_, svg) = page("svg", "p1");
    assert_ne!(image["current_basis"], image_basis);
    assert_eq!(image["basis_changed"], true);
    assert_eq!(svg["current_basis"], svg_basis);
    assert_eq!(svg["basis_changed"], true);
    assert_artifacts(json!(["p1"]));

    edit(path, json!({"pages":[{"id":"p1","purpose":""}]}));
    assert_artifacts(json!([]));
    edit(
        path,
        json!({"pages":[{"id":"p1","content":{"title":"增长","body_blocks":[{"type":"paragraph","id":"a1","text":"预期增长 5%"}]}}]}),
    );
    let (_, svg) = page("svg", "p1");
    assert_ne!(svg["current_basis"], svg_basis);
    assert_eq!(svg["basis_changed"], true);
    assert_artifacts(json!(["p1"]));
}
