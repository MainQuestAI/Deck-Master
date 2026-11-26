use crate::error::{Error, Result};
use crate::model::Page;
use crate::store::{self, Store};
use serde_json::{Value, json};
use std::collections::HashMap;
use std::path::Path;

#[derive(serde::Serialize, serde::Deserialize)]
pub(super) struct NativeAsset {
    pub(super) id: String,
    pub(super) file: String,
    pub(super) sha256: String,
}

#[derive(serde::Serialize, serde::Deserialize)]
pub(super) struct NativePack {
    pub(super) plan: Value,
    pub(super) assets: Vec<NativeAsset>,
    pub(super) render_png: String,
    pub(super) note: String,
}

fn resolve_native_asset(base_dir: &Path, name: &str) -> Result<(Vec<u8>, &'static str)> {
    use std::path::Component;
    if name.trim().is_empty() {
        return Err(Error::Input("image 缺少素材文件".into()));
    }
    let rel = Path::new(name);
    if rel.is_absolute()
        || rel.components().any(|c| {
            matches!(
                c,
                Component::ParentDir | Component::RootDir | Component::Prefix(_)
            )
        })
    {
        return Err(Error::Input(format!(
            "image 素材必须是当前任务目录内的相对路径：{name}"
        )));
    }
    let base = base_dir.canonicalize()?;
    let resolved = base
        .join(rel)
        .canonicalize()
        .map_err(|_| Error::Input(format!("image 素材文件不存在：{name}")))?;
    if !resolved.starts_with(&base) || !resolved.is_file() {
        return Err(Error::Input(format!(
            "image 素材路径越出当前任务目录：{name}"
        )));
    }
    let bytes = std::fs::read(&resolved)?;
    let ext = if bytes.starts_with(b"\x89PNG\r\n\x1a\n") {
        "png"
    } else if bytes.starts_with(b"\xff\xd8\xff") {
        "jpg"
    } else {
        return Err(Error::Input(format!(
            "image 素材只支持 PNG 或 JPEG：{name}"
        )));
    };
    Ok((bytes, ext))
}

pub(super) fn native_plan_path(store: &Store, pack: &NativePack, path: &Path) -> Result<()> {
    let mut plan = pack.plan.clone();
    let assets_dir = path.parent().unwrap_or(Path::new(".")).join("assets");
    for op in plan["ops"].as_array_mut().into_iter().flatten() {
        if op["op"] == "image" {
            let file = op["file"]
                .as_str()
                .ok_or_else(|| Error::Input("image 缺少素材文件".into()))?;
            let stored = store.file(file)?;
            std::fs::create_dir_all(&assets_dir)?;
            let staged = assets_dir.join(file);
            if !staged.exists() && std::fs::hard_link(&stored, &staged).is_err() {
                std::fs::copy(&stored, &staged)?;
            }
            op["file"] = json!(format!("assets/{file}"));
        }
    }
    std::fs::write(path, serde_json::to_vec(&plan)?)?;
    Ok(())
}

pub(super) fn native_result(
    store: &Store,
    id: i64,
    page: &Page,
    source: &Path,
    data: &[u8],
    temporary: &Path,
) -> Result<(Vec<u8>, String, Value, Value)> {
    use sha2::{Digest, Sha256};
    let mut plan: Value = serde_json::from_slice(data)?;
    let path = temporary.join("plan.json");
    let mut input = serde_json::to_value(page)?;
    input["plan"] = json!(path);
    let base_dir = source.parent().unwrap_or(Path::new("."));
    let mut staged_assets = Vec::new();
    for (index, op) in plan["ops"].as_array().into_iter().flatten().enumerate() {
        if op["op"] == "image" {
            let name = op["file"]
                .as_str()
                .ok_or_else(|| Error::Input("image 缺少素材文件".into()))?;
            let (raw_bytes, default_ext) = resolve_native_asset(base_dir, name)?;
            let raw_path = temporary.join(format!("asset-raw-{index}.{default_ext}"));
            let normalized = temporary.join(format!("asset-norm-{index}"));
            std::fs::write(&raw_path, &raw_bytes)?;
            let info = crate::tools::invoke(
                "normalize-image",
                &json!({"path": raw_path, "output": normalized, "svg": false}),
            )?;
            let (bytes, ext) = if info["normalized"].as_bool() == Some(true) {
                let out_ext = match info["format"].as_str() {
                    Some("PNG") => "png",
                    Some("JPEG") => "jpg",
                    _ => {
                        return Err(Error::Tool(
                            "normalize-image 未返回 PNG 或 JPEG 格式".into(),
                        ));
                    }
                };
                (std::fs::read(&normalized)?, out_ext)
            } else {
                (raw_bytes, default_ext)
            };
            staged_assets.push((name.to_string(), bytes, ext));
        }
    }
    let mut assets = Vec::new();
    let mut asset_iter = staged_assets.into_iter();
    for op in plan["ops"].as_array_mut().into_iter().flatten() {
        if op["op"] == "image"
            && let Some((name, bytes, ext)) = asset_iter.next()
        {
            let file = store.add_file(&bytes, ext)?;
            assets.push(NativeAsset {
                id: name,
                file: file.clone(),
                sha256: format!("{:x}", Sha256::digest(&bytes)),
            });
            op["file"] = json!(file);
        }
    }
    let mut pack = NativePack {
        plan,
        assets,
        render_png: String::new(),
        note: String::new(),
    };
    native_plan_path(store, &pack, &path)?;
    let image = page
        .image
        .as_ref()
        .ok_or_else(|| Error::Input("本页没有已采用的原图；请先交回并采用原图".into()))?;
    input["source_image"] = json!(store.file(&image.file)?.canonicalize()?);
    let work = store.root.canonicalize()?.join("work").join(id.to_string());
    std::fs::create_dir_all(&work)?;
    // Each check keeps its own comparison, including concurrent or repeated results.
    let directory = tempfile::Builder::new()
        .prefix("native-")
        .tempdir_in(work)?
        .keep();
    let output = crate::tools::invoke(
        "render",
        &json!({
            "page": input,
            "output": directory,
        }),
    )?;
    let preview = output["render_png"]
        .as_str()
        .ok_or_else(|| Error::Tool("render 缺少预览路径".into()))?;
    pack.render_png = store.add_file(&std::fs::read(preview)?, "png")?;
    Ok((
        serde_json::to_vec(&pack)?,
        pack.render_png,
        output["findings"].clone(),
        output["side_by_side"].clone(),
    ))
}

#[derive(Clone, PartialEq, Eq, Hash)]
struct HeaderKey {
    title: [i64; 4],
    shape: Option<(String, [i64; 4])>,
}

fn round_px(value: &Value) -> Option<i64> {
    let number = value.as_f64()?;
    if !number.is_finite() {
        return None;
    }
    let rounded = number.round();
    if !(-1e12..=1e12).contains(&rounded) {
        return None;
    }
    Some(rounded as i64)
}

fn bbox4(value: &Value) -> Option<[i64; 4]> {
    let array = value.as_array()?;
    if array.len() != 4 {
        return None;
    }
    Some([
        round_px(&array[0])?,
        round_px(&array[1])?,
        round_px(&array[2])?,
        round_px(&array[3])?,
    ])
}

fn atom_tail(atom_id: &str) -> &str {
    atom_id
        .rsplit_once(':')
        .map(|(_, tail)| tail)
        .unwrap_or(atom_id)
}

fn header_key(plan: &Value) -> Option<HeaderKey> {
    let ops = plan.get("ops")?.as_array()?;
    let mut title = None;
    let mut saw_title = false;
    let mut first_shape = None;
    for op in ops {
        let Some(kind) = op.get("op").and_then(Value::as_str) else {
            continue;
        };
        if !saw_title && kind == "text" {
            let Some(atom) = op.get("atom_id").and_then(Value::as_str) else {
                continue;
            };
            if atom_tail(atom) == "title" {
                saw_title = true;
                title = op.get("bbox").and_then(bbox4);
            }
        }
        if first_shape.is_none() && kind == "shape" {
            first_shape = Some(op);
        }
    }
    let title = title?;
    let shape = match first_shape {
        None => None,
        Some(op) => {
            let kind = op
                .get("type")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            let bbox = bbox4(op.get("bbox")?)?;
            Some((kind, bbox))
        }
    };
    Some(HeaderKey { title, shape })
}

fn shared_layout_message(count: usize) -> String {
    format!(
        "本 run 已有 {count} 页共用同一题头（标题框与第一条 shape 相同）。请按这张原图逐页测量，不要套同一题头。此提示不阻止交回或采用。"
    )
}

pub(super) fn shared_layout_warnings(pages: &[(&str, &Value)]) -> Vec<Value> {
    let mut keyed = Vec::new();
    for (page_id, plan) in pages {
        if let Some(key) = header_key(plan) {
            keyed.push((*page_id, key));
        }
    }
    let mut counts: HashMap<HeaderKey, usize> = HashMap::new();
    for (_, key) in &keyed {
        *counts.entry(key.clone()).or_insert(0) += 1;
    }
    let mut warnings = Vec::new();
    for (page_id, key) in &keyed {
        let count = counts[key];
        if count >= 3 {
            warnings.push(json!({
                "level": "warning",
                "code": "shared_layout",
                "page_id": page_id,
                "message": shared_layout_message(count),
            }));
        }
    }
    warnings
}

pub(super) fn plan_refs(plans: &[(String, Value)]) -> Vec<(&str, &Value)> {
    plans
        .iter()
        .map(|(page_id, plan)| (page_id.as_str(), plan))
        .collect()
}

pub(super) fn with_shared_layout(mut warnings: Value, pages: &[(&str, &Value)]) -> Value {
    if let Some(list) = warnings.as_array_mut() {
        list.extend(shared_layout_warnings(pages));
    }
    warnings
}

pub(super) fn append_findings_warnings(findings: &mut Value, warnings: Vec<Value>) {
    if warnings.is_empty() {
        return;
    }
    let Some(object) = findings.as_object_mut() else {
        return;
    };
    let entry = object.entry("warnings").or_insert_with(|| json!([]));
    if let Some(list) = entry.as_array_mut() {
        list.extend(warnings);
    }
}

fn is_punctuation(c: char) -> bool {
    if c.is_ascii_punctuation() {
        return true;
    }
    matches!(
        c,
        '\u{00A1}'
            | '\u{00A7}'
            | '\u{00AB}'
            | '\u{00B6}'
            | '\u{00B7}'
            | '\u{00BB}'
            | '\u{00BF}'
            | '\u{2010}'..='\u{2027}'
            | '\u{2030}'..='\u{205E}'
            | '\u{3001}'..='\u{3003}'
            | '\u{3008}'..='\u{3011}'
            | '\u{3014}'..='\u{301F}'
            | '\u{3030}'
            | '\u{303D}'
            | '\u{30A0}'
            | '\u{30FB}'
            | '\u{FF01}'..='\u{FF0F}'
            | '\u{FF1A}'..='\u{FF20}'
            | '\u{FF3B}'..='\u{FF40}'
            | '\u{FF5B}'..='\u{FF65}'
            | '\u{FE10}'..='\u{FE19}'
            | '\u{FE30}'..='\u{FE52}'
            | '\u{FE54}'..='\u{FE61}'
            | '\u{FE63}'
            | '\u{FE68}'
            | '\u{FE6A}'
            | '\u{FE6B}'
    )
}

fn take_prefix<'a>(text: &'a str, options: &[&str]) -> Option<&'a str> {
    options
        .iter()
        .filter(|option| text.starts_with(*option))
        .max_by_key(|option| option.len())
        .map(|option| &text[option.len()..])
}

pub(super) fn is_confirmation_only(note: &str) -> bool {
    let stripped: String = note
        .chars()
        .filter(|c| !c.is_whitespace() && !is_punctuation(*c))
        .collect();
    if stripped.is_empty() {
        return false;
    }
    let mut rest = stripped.as_str();
    if let Some(next) = take_prefix(rest, &["本页", "此页", "该页"]) {
        rest = next;
    }
    let Some(next) = take_prefix(
        rest,
        &[
            "已核对",
            "已对照",
            "已查看",
            "已复查",
            "已复看",
            "已确认",
            "已检查",
            "已核验",
        ],
    ) else {
        return false;
    };
    rest = next;
    if let Some(next) = take_prefix(rest, &["了", "过"]) {
        rest = next;
    }
    if let Some(next) = take_prefix(
        rest,
        &[
            "这一页",
            "此页面",
            "本页面",
            "并排图",
            "对照图",
            "原图",
            "本页",
            "此页",
            "该页",
            "页面",
            "生产稿",
            "原稿",
        ],
    ) {
        rest = next;
    }
    if let Some(next) = take_prefix(rest, &["后"]) {
        rest = next;
    }
    if let Some(next) = take_prefix(
        rest,
        &[
            "没有问题",
            "没问题",
            "一致",
            "无误",
            "完成",
            "通过",
            "正确",
            "ok",
            "OK",
        ],
    ) {
        rest = next;
    }
    rest.is_empty()
}

pub(super) fn readable_native_plan(root: &Path, file: &str) -> Option<Value> {
    let path = store::file_path(root, file).ok()?;
    let bytes = std::fs::read(path).ok()?;
    serde_json::from_slice::<NativePack>(&bytes)
        .ok()
        .map(|pack| pack.plan)
}

pub(super) fn note_unspecific_warning(page_id: &str) -> Value {
    json!({
        "level": "warning",
        "code": "note_unspecific",
        "page_id": page_id,
        "message": "--note 去掉空白和标点后只剩确认用语，没有写出本页对照了什么。此提示不阻止采用。",
    })
}

pub(super) fn result_plans(
    store: &Store,
    run_id: i64,
    current_page: &str,
    current_plan: Option<&Value>,
) -> Result<Vec<(String, Value)>> {
    let mut statement = store.connection.prepare(
        "SELECT page_id, result_file FROM run_pages WHERE run_id=? AND result_file IS NOT NULL ORDER BY rowid",
    )?;
    let rows = statement
        .query_map([run_id], |row| {
            Ok((row.get::<_, String>(0)?, row.get::<_, String>(1)?))
        })?
        .collect::<std::result::Result<Vec<_>, _>>()?;
    let mut plans = Vec::new();
    let mut replaced = false;
    for (page_id, file) in rows {
        if page_id == current_page
            && let Some(plan) = current_plan
        {
            plans.push((page_id, plan.clone()));
            replaced = true;
            continue;
        }
        // Another page's pack only adds a shared_layout hint. Skip it when it cannot be read.
        let Some(plan) = readable_native_plan(&store.root, &file) else {
            continue;
        };
        plans.push((page_id, plan));
    }
    if let Some(plan) = current_plan
        && !replaced
    {
        plans.push((current_page.to_string(), plan.clone()));
    }
    Ok(plans)
}

#[cfg(test)]
mod layout_warning_tests {
    use super::*;

    fn text_op(page: &str, tail: &str, bbox: Value) -> Value {
        json!({"op":"text","atom_id":format!("atom:{page}:{tail}"),"text":"t","bbox":bbox})
    }

    fn shape_op(kind: &str, bbox: Value) -> Value {
        json!({"op":"shape","type":kind,"bbox":bbox})
    }

    fn plan(ops: Vec<Value>) -> Value {
        json!({"ops": ops})
    }

    #[test]
    fn three_pages_sharing_a_header_warn_and_two_pages_or_different_shapes_do_not() {
        let title = json!([40, 30, 500, 48]);
        let bar = json!([24, 24, 10, 36]);
        let page = |id: &str, body_y: i64| {
            plan(vec![
                text_op(id, "title", title.clone()),
                shape_op("rect", bar.clone()),
                text_op(id, "body", json!([20, body_y, 200, 30])),
                shape_op("ellipse", json!([80, body_y, 40, 20])),
            ])
        };
        let pages = [
            ("p1", page("p1", 120)),
            ("p2", page("p2", 180)),
            ("p3", page("p3", 240)),
        ];
        let warnings = shared_layout_warnings(&[
            ("p1", &pages[0].1),
            ("p2", &pages[1].1),
            ("p3", &pages[2].1),
        ]);
        assert_eq!(
            warnings
                .iter()
                .map(|warning| warning["page_id"].as_str().unwrap())
                .collect::<Vec<_>>(),
            ["p1", "p2", "p3"]
        );
        assert!(warnings.iter().all(|warning| {
            warning["level"] == "warning" && warning["code"] == "shared_layout"
        }));
        let two = [page("p1", 120), page("p2", 180)];
        assert!(shared_layout_warnings(&[("p1", &two[0]), ("p2", &two[1])]).is_empty());
        let varied: Vec<Value> = ["a", "b", "c", "d"]
            .into_iter()
            .enumerate()
            .map(|(index, id)| {
                plan(vec![
                    text_op(id, "title", title.clone()),
                    shape_op("rect", json!([10 + index * 20, 20, 12, 30])),
                    text_op(id, "body", json!([20, 100, 80, 20])),
                ])
            })
            .collect();
        assert!(
            shared_layout_warnings(&[
                ("a", &varied[0]),
                ("b", &varied[1]),
                ("c", &varied[2]),
                ("d", &varied[3]),
            ])
            .is_empty()
        );
        let rounded = [
            plan(vec![
                text_op("r1", "title", json!([20.4, 10, 30, 40])),
                shape_op("rect", bar.clone()),
            ]),
            plan(vec![
                text_op("r2", "title", json!([19.6, 10, 30, 40])),
                shape_op("rect", bar.clone()),
            ]),
            plan(vec![
                text_op("r3", "title", json!([20, 10, 30, 40])),
                shape_op("rect", bar.clone()),
            ]),
        ];
        assert_eq!(
            shared_layout_warnings(&[
                ("r1", &rounded[0]),
                ("r2", &rounded[1]),
                ("r3", &rounded[2]),
            ])
            .len(),
            3
        );
        let untitled = [
            plan(vec![
                text_op("u1", "label", title.clone()),
                shape_op("rect", bar.clone()),
            ]),
            plan(vec![
                text_op("u2", "label", title.clone()),
                shape_op("rect", bar.clone()),
            ]),
            plan(vec![
                text_op("u3", "label", title.clone()),
                shape_op("rect", bar.clone()),
            ]),
        ];
        assert!(
            shared_layout_warnings(&[
                ("u1", &untitled[0]),
                ("u2", &untitled[1]),
                ("u3", &untitled[2]),
            ])
            .is_empty()
        );
    }

    #[test]
    fn confirmation_only_notes_are_boilerplate_and_specific_notes_are_not() {
        assert!(is_confirmation_only("已核对"));
        assert!(is_confirmation_only("已核对，没问题"));
        assert!(is_confirmation_only("已查看并排图。"));
        assert!(!is_confirmation_only(
            "已查看并排图，四来源汇入数据的方向明确，四行来源及获取方式和用途完整，底部保留数据责任、更新与适用条件。"
        ));
        assert!(!is_confirmation_only("已对照文字与对象"));
        assert!(!is_confirmation_only(
            "标题框在原图标题带内，左侧三列与原图同序，底部限定条件保留"
        ));
        assert!(!is_confirmation_only(
            "主表四行与原图对齐，右侧注释的适用范围保留"
        ));
        assert!(!is_confirmation_only("   "));
        assert!(!is_confirmation_only(
            "本页已核对了原图后，标题位置与四行来源一致"
        ));
    }

    #[test]
    fn anonymized_geometry_replay_matches_expected_warned_pages() {
        let path =
            Path::new(env!("CARGO_MANIFEST_DIR")).join("tests/fixtures/issue-337/geometry.json");
        let fixture: Value = serde_json::from_slice(&std::fs::read(path).unwrap()).unwrap();
        let sets = fixture.as_object().unwrap();
        assert!(sets.contains_key("bad_first_result"));
        assert!(sets.contains_key("good_final"));
        for (name, set) in sets {
            let pages = set["pages"].as_array().unwrap();
            let plans: Vec<(String, Value)> = pages
                .iter()
                .enumerate()
                .map(|(index, page)| {
                    let id = page["page"].as_str().unwrap().to_string();
                    let plan = json!({
                        "ops": [
                            {"op":"text","atom_id":format!("atom:{id}:title"),"text":"t","bbox":page["title_bbox"]},
                            {"op":"shape","type":page["first_shape"]["type"],"bbox":page["first_shape"]["bbox"]},
                            {"op":"text","atom_id":format!("atom:{id}:body"),"text":id,"bbox":[20, 220 + index, 140, 28]},
                        ]
                    });
                    (id, plan)
                })
                .collect();
            let warned: Vec<String> = shared_layout_warnings(&plan_refs(&plans))
                .into_iter()
                .map(|warning| warning["page_id"].as_str().unwrap().to_string())
                .collect();
            let expected: Vec<String> = set["expected_warned_pages"]
                .as_array()
                .unwrap()
                .iter()
                .map(|page| page.as_str().unwrap().to_string())
                .collect();
            assert_eq!(warned, expected, "{name}");
        }
    }
}
