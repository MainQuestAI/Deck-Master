use crate::error::{Error, Result};
use crate::model::{Artifact, Canvas, Deck};
use crate::ops::basis::{basis, current_basis_for, image_is_stale, is_complete_render_basis};
use crate::ops::native::{NativePack, native_plan_path, plan_refs, with_shared_layout};
use crate::ops::review::content_review_status;
use crate::ops::run::{file_url, page_job};
use crate::store::{self, Store};
use serde::Serialize;
use serde_json::{Value, json};
use std::collections::BTreeMap;
use std::path::Path;

#[derive(Serialize)]
struct NativeBuildPage<'a> {
    id: &'a str,
    native: Option<&'a Artifact>,
    current_basis: String,
    notes: &'a str,
}

#[derive(Serialize)]
struct SvgBuildPage<'a> {
    id: &'a str,
    svg_file: Option<&'a str>,
    notes: &'a str,
}

#[derive(Serialize)]
struct BuildDigestInput<'a, P: Serialize> {
    mode: &'a str,
    pages: Vec<P>,
    canvas: &'a Canvas,
    fonts: &'a [String],
    assets: BTreeMap<&'a str, &'a str>,
}

fn build_digest(deck: &Deck) -> Result<String> {
    use sha2::{Digest, Sha256};
    let native = deck.pages.iter().any(|p| p.native.is_some());
    let assets: BTreeMap<&str, &str> = deck
        .style
        .assets
        .iter()
        .map(|asset| (asset.id.as_str(), asset.file.as_str()))
        .collect();
    let encoded = if native {
        let pages: Vec<_> = deck
            .pages
            .iter()
            .map(|p| {
                Ok(NativeBuildPage {
                    id: &p.id,
                    native: p.native.as_ref(),
                    current_basis: basis("native", deck, p)?,
                    notes: &p.notes,
                })
            })
            .collect::<Result<_>>()?;
        serde_json::to_vec(&BuildDigestInput {
            mode: "native",
            pages,
            canvas: &deck.style.canvas,
            fonts: &deck.style.fonts,
            assets,
        })?
    } else {
        let pages: Vec<_> = deck
            .pages
            .iter()
            .map(|p| SvgBuildPage {
                id: &p.id,
                svg_file: p.svg.as_ref().map(|s| s.file.as_str()),
                notes: &p.notes,
            })
            .collect();
        serde_json::to_vec(&BuildDigestInput {
            mode: "svg",
            pages,
            canvas: &deck.style.canvas,
            fonts: &deck.style.fonts,
            assets,
        })?
    };
    Ok(format!("{:x}", Sha256::digest(encoded)))
}

pub fn artifact_status(deck: &Deck) -> Result<Value> {
    artifact_status_for(deck, deck.pages.iter().any(|p| p.native.is_some()))
}

pub(super) fn stale_image_warnings(stale_images: &Value) -> Value {
    json!(
        stale_images
            .as_array()
            .into_iter()
            .flatten()
            .filter_map(|page_id| page_id.as_str())
            .map(|page_id| json!({"level":"warning","code":"stale_image","page_id":page_id}))
            .collect::<Vec<_>>()
    )
}

fn artifact_status_for(deck: &Deck, native: bool) -> Result<Value> {
    let missing: Vec<_> = deck
        .pages
        .iter()
        .filter(|p| {
            if native {
                p.native.is_none()
            } else {
                p.svg.is_none()
            }
        })
        .map(|p| &p.id)
        .collect();
    let mut stale = Vec::new();
    let mut stale_images = Vec::new();
    let mut incomplete_basis_pages = Vec::new();
    for page in &deck.pages {
        let artifact = if native { &page.native } else { &page.svg };
        if artifact
            .as_ref()
            .is_some_and(|svg| !is_complete_render_basis(&svg.basis))
        {
            incomplete_basis_pages.push(&page.id);
        }
        let image_stale = image_is_stale(deck, page)?;
        if image_stale {
            stale_images.push(&page.id);
        }
        if let Some(svg) = artifact {
            let stale_render = match current_basis_for("svg", &svg.basis, deck, page) {
                Ok(current) => svg.basis != current,
                Err(_) => true,
            };
            if stale_render {
                stale.push(&page.id);
            }
        }
    }
    Ok(
        json!({"missing_pages":missing,"stale_pages":stale,"stale_images":stale_images,"incomplete_basis_pages":incomplete_basis_pages}),
    )
}

pub fn build(project: &Path) -> Result<Value> {
    use rusqlite::params;
    let mut store = Store::open(project)?;
    let snapshot = store.current()?;
    let native = snapshot.deck.pages.iter().any(|p| p.native.is_some());
    let status = artifact_status_for(&snapshot.deck, native)?;
    let temporary = tempfile::tempdir()?;
    let mut pages = Vec::new();
    let mut native_plans = Vec::new();
    let mut job = Value::Null;
    for (index, page) in snapshot.deck.pages.iter().enumerate() {
        if native {
            if let Some(artifact) = &page.native {
                let pack: NativePack =
                    serde_json::from_slice(&std::fs::read(store.file(&artifact.file)?)?)?;
                let plan = temporary.path().join(format!("{index}.json"));
                native_plan_path(&store, &pack, &plan)?;
                native_plans.push((page.id.clone(), pack.plan));
                pages.push(
                    json!({"id":page.id,"content":page.content,"notes":page.notes,"plan":plan}),
                );
            }
        } else if let Some(svg) = &page.svg {
            let input = page_job(&store, &snapshot.deck, page, &store.file(&svg.file)?)?;
            pages.push(input["pages"][0].clone());
            job = input;
        }
    }
    if pages.is_empty() {
        let missing = snapshot
            .deck
            .pages
            .iter()
            .map(|page| page.id.as_str())
            .collect::<Vec<_>>()
            .join(",");
        return Err(Error::Input(format!("没有已采用的页面；缺页：{missing}")));
    }
    let content_review =
        content_review_status(&store.connection, snapshot.version, &snapshot.deck)?;
    let output = if native {
        crate::tools::invoke("assemble", &json!({"work":temporary.path(),"pages":pages}))?
    } else {
        job["pages"] = json!(pages);
        job["output"] = json!(temporary.path().join("build"));
        crate::tools::invoke("build", &job)?
    };
    let path = output["pptx"]
        .as_str()
        .ok_or_else(|| Error::Tool("build 缺少 PPTX 路径".into()))?;
    let file = store.add_file(&std::fs::read(path)?, "pptx")?;
    let tx = store.transaction()?;
    tx.execute("INSERT INTO builds(version_id,input_digest,pptx_file,findings_json,missing_pages) VALUES (?,?,?,?,?)",params![snapshot.version,build_digest(&snapshot.deck)?,file,serde_json::to_string(&output["findings"])?,serde_json::to_string(&status["missing_pages"])?])?;
    let id = tx.last_insert_rowid();
    tx.commit()?;
    Ok(
        json!({"id":id,"version_id":snapshot.version,"path":store.file(&file)?,"findings":output["findings"],"missing_pages":status["missing_pages"],"stale_pages":status["stale_pages"],"stale_images":status["stale_images"],"warnings":with_shared_layout(stale_image_warnings(&status["stale_images"]), &plan_refs(&native_plans)),"content_review":content_review}),
    )
}

// Selection and its metadata share the caller's read transaction.
pub(super) fn default_build(
    connection: &rusqlite::Connection,
    deck: &Deck,
) -> Result<Option<Value>> {
    use rusqlite::OptionalExtension;
    let digest = build_digest(deck)?;
    let row = connection.query_row(
        "SELECT id,version_id,input_digest,pptx_file,missing_pages,created_at FROM builds ORDER BY (input_digest=?1) DESC,id DESC LIMIT 1",
        [&digest],
        |r| Ok((r.get::<_,i64>(0)?,r.get::<_,i64>(1)?,r.get::<_,String>(2)?,r.get::<_,String>(3)?,r.get::<_,String>(4)?,r.get::<_,String>(5)?)),
    ).optional()?;
    row.map(|(id,version_id,input,file,missing,created)| {
        let changed = input != digest;
        Ok(json!({"id":id,"version_id":version_id,"file":file,"created_at":created,
            "input_changed":changed,
            "warning":if changed {"当前构建输入没有匹配的成品；下载的是最近可用历史成品，请按需重新构建"} else {""},
            "build_missing_pages":serde_json::from_str::<Value>(&missing)
                .map_err(|e| Error::DataCorrupt(format!("构建缺页记录损坏：{e}")))?}))
    }).transpose()
}

pub fn build_detail(project: &Path, id: i64) -> Result<Value> {
    use rusqlite::OptionalExtension;
    let mut store = Store::open(project)?;
    let tx = store.read_transaction()?;
    let current = store::current(&tx)?;
    let row = tx.query_row(
        "SELECT version_id,input_digest,pptx_file,findings_json,missing_pages,created_at FROM builds WHERE id=?",
        [id], |r| Ok((r.get::<_,i64>(0)?,r.get::<_,String>(1)?,r.get::<_,String>(2)?,r.get::<_,String>(3)?,r.get::<_,String>(4)?,r.get::<_,String>(5)?)),
    ).optional()?.ok_or_else(|| Error::Missing(format!("构建 {id} 不存在")))?;
    let (version_id, digest, file, findings, missing, created_at) = row;
    let findings: Value = serde_json::from_str(&findings)
        .map_err(|e| Error::DataCorrupt(format!("构建回读 JSON 损坏：{e}")))?;
    let source = store::load(&tx, version_id)?;
    let imported = digest == "imported";
    if !imported
        && (!findings.is_object()
            || !findings["findings"].is_array()
            || !matches!(findings["status"].as_str(), Some("pass" | "fail")))
    {
        return Err(Error::Tool(
            "构建回读结果不可读取；请保留原始产物并按需重新构建".into(),
        ));
    }
    let mut pages = Vec::new();
    let mut content_matches = true;
    let native = source.pages.iter().any(|p| p.native.is_some());
    for (index, page) in source.pages.iter().enumerate() {
        if if native {
            page.native.is_none()
        } else {
            page.svg.is_none()
        } {
            continue;
        }
        content_matches &= current
            .deck
            .pages
            .iter()
            .any(|now| now.id == page.id && now.content == page.content);
        pages.push(json!({"page_id":page.id,"title":page.content.title,"source_order":index+1,"pptx_slide":pages.len()+1}));
    }
    let input_changed = digest != build_digest(&current.deck)?;
    Ok(
        json!({"id":id,"version_id":version_id,"created_at":created_at,"pptx_url":file_url(&file),
        "findings":findings,"pages":pages,"build_missing_pages":serde_json::from_str::<Value>(&missing)?,
        "current_version":current.version,"input_changed":input_changed,"readback_available":!imported,
        "readback_matches_current":if imported {Value::Null} else {json!(!input_changed && content_matches)}}),
    )
}

#[cfg(test)]
mod build_selection_tests {
    use super::*;
    use crate::model::Page;
    use crate::ops::basis::calculate_legacy_basis;
    use crate::ops::{export_pptx, workspace};

    #[test]
    fn legacy_basis_survives_format_upgrade_and_does_not_claim_purpose_coverage() {
        let temp = tempfile::tempdir().unwrap();
        let mut store = Store::create(temp.path(), &Deck::default()).unwrap();
        let mut deck = Deck::default();
        deck.pages.push(Page {
            id: "p1".into(),
            ..Page::default()
        });
        let legacy = calculate_legacy_basis("svg", &deck, &deck.pages[0], false).unwrap();
        deck.pages[0].svg = Some(crate::model::Artifact {
            file: "historical.svg".into(),
            basis: legacy.clone(),
        });
        let tx = store.transaction().unwrap();
        store::append(&tx, &mut deck, "Legacy fixture").unwrap();
        tx.commit().unwrap();
        store
            .connection
            .pragma_update(None, "user_version", 4)
            .unwrap();
        drop(store);
        let upgraded = Store::open(temp.path()).unwrap();
        assert_eq!(
            upgraded
                .connection
                .pragma_query_value(None, "user_version", |r| r.get::<_, i64>(0))
                .unwrap(),
            6
        );
        assert_eq!(
            upgraded.current().unwrap().deck.pages[0]
                .svg
                .as_ref()
                .unwrap()
                .basis,
            legacy
        );
        let old_v2 = basis("svg", &deck, &deck.pages[0]).unwrap();
        deck.pages[0].purpose = "Changed purpose".into();
        assert_eq!(
            current_basis_for("svg", &legacy, &deck, &deck.pages[0]).unwrap(),
            legacy
        );
        assert_ne!(basis("svg", &deck, &deck.pages[0]).unwrap(), old_v2);
        let status = artifact_status(&deck).unwrap();
        assert_eq!(status["stale_pages"], json!([]));
        assert_eq!(status["incomplete_basis_pages"], json!(["p1"]));
    }

    #[test]
    fn persisted_readback_compares_content_and_preserves_import_and_corruption_identity() {
        let temp = tempfile::tempdir().unwrap();
        let mut store = Store::create(temp.path(), &Deck::default()).unwrap();
        let file = store.add_file(b"synthetic SVG", "svg").unwrap();
        let mut deck = Deck::default();
        deck.pages.push(Page {
            id: "p1".into(),
            ..Page::default()
        });
        deck.pages[0].svg = Some(crate::model::Artifact {
            file,
            basis: basis("svg", &deck, &deck.pages[0]).unwrap(),
        });
        let tx = store.transaction().unwrap();
        let source = store::append(&tx, &mut deck, "Source").unwrap();
        tx.commit().unwrap();
        let report = json!({"status":"pass","findings":[],"visual_review":"not_evaluated","desktop_editing":"not_evaluated"});
        store.connection.execute("INSERT INTO builds(version_id,input_digest,pptx_file,findings_json,missing_pages) VALUES (?,?, 'synthetic.pptx',?, '[]')",rusqlite::params![source,build_digest(&deck).unwrap(),report.to_string()]).unwrap();
        let detail = build_detail(temp.path(), 1).unwrap();
        assert_eq!(detail["readback_matches_current"], true);
        assert_eq!(detail["pages"][0]["pptx_slide"], 1);
        deck.pages[0].content.title = "Changed text".into();
        let tx = store.transaction().unwrap();
        store::append(&tx, &mut deck, "Content only").unwrap();
        tx.commit().unwrap();
        let detail = build_detail(temp.path(), 1).unwrap();
        assert_eq!(detail["input_changed"], false);
        assert_eq!(detail["readback_matches_current"], false);
        store
            .connection
            .execute("UPDATE builds SET findings_json='broken' WHERE id=1", [])
            .unwrap();
        assert!(build_detail(temp.path(), 1).is_err());
        assert_eq!(workspace(temp.path()).unwrap()["default_build"]["id"], 1);
        store
            .connection
            .execute(
                "UPDATE builds SET input_digest='imported',findings_json='[]' WHERE id=1",
                [],
            )
            .unwrap();
        let detail = build_detail(temp.path(), 1).unwrap();
        assert_eq!(detail["readback_available"], false);
        assert!(detail["readback_matches_current"].is_null());
        assert!(matches!(
            build_detail(temp.path(), 99),
            Err(Error::Missing(_))
        ));
    }

    #[test]
    fn matching_build_wins_over_later_completion_and_restore_can_select_older_id() {
        let temp = tempfile::tempdir().unwrap();
        let mut store = Store::create(temp.path(), &Deck::default()).unwrap();
        let mut older = Deck::default();
        older.pages.push(Page {
            id: "p1".into(),
            notes: "old".into(),
            ..Page::default()
        });
        let mut current = older.clone();
        current.pages[0].notes = "new".into();
        let old_file = store.add_file(b"old build", "pptx").unwrap();
        let current_file = store.add_file(b"current build", "pptx").unwrap();
        for (deck, file) in [
            (&older, &old_file),
            (&current, &current_file),
            (&older, &old_file),
        ] {
            store.connection.execute("INSERT INTO builds(version_id,input_digest,pptx_file,findings_json,missing_pages) VALUES (1,?,?, '{}','[]')", rusqlite::params![build_digest(deck).unwrap(), file]).unwrap();
        }
        assert_eq!(
            default_build(&store.connection, &current).unwrap().unwrap()["id"],
            2
        );
        assert_eq!(
            default_build(&store.connection, &older).unwrap().unwrap()["id"],
            3
        );
        let tx = store.transaction().unwrap();
        store::append(&tx, &mut current, "Current inputs").unwrap();
        tx.commit().unwrap();
        let export = export_pptx(temp.path()).unwrap();
        assert_eq!(export["id"], 2);
        assert_eq!(export["input_changed"], false);
        assert_eq!(
            std::fs::read(export["path"].as_str().unwrap()).unwrap(),
            b"current build"
        );
        current.pages[0].notes = "unbuilt".into();
        let fallback = default_build(&store.connection, &current).unwrap().unwrap();
        assert_eq!(fallback["id"], 3);
        assert_eq!(fallback["input_changed"], true);
        std::fs::remove_file(store.file(&current_file).unwrap()).unwrap();
        assert!(matches!(export_pptx(temp.path()), Err(Error::Missing(_))));
    }

    #[test]
    fn export_returns_the_historical_pptx_when_a_native_pack_cannot_be_read() {
        let temp = tempfile::tempdir().unwrap();
        let mut store = Store::create(temp.path(), &Deck::default()).unwrap();
        let mut deck = Deck::default();
        deck.pages.push(Page {
            id: "p1".into(),
            ..Page::default()
        });
        deck.pages[0].native = Some(crate::model::Artifact {
            file: format!("{}.native.json", "ab".repeat(32)),
            basis: basis("native", &deck, &deck.pages[0]).unwrap(),
        });
        let tx = store.transaction().unwrap();
        store::append(&tx, &mut deck, "Native without a readable pack").unwrap();
        tx.commit().unwrap();
        let pptx = store.add_file(b"historical pptx", "pptx").unwrap();
        store.connection.execute(
            "INSERT INTO builds(version_id,input_digest,pptx_file,findings_json,missing_pages) VALUES (1,?,?,'{}','[]')",
            rusqlite::params![build_digest(&deck).unwrap(), pptx],
        ).unwrap();
        let corrupt = store.add_file(b"not json", "native.json").unwrap();
        deck.pages.push(Page {
            id: "p2".into(),
            ..Page::default()
        });
        deck.pages[1].native = Some(crate::model::Artifact {
            file: corrupt,
            basis: basis("native", &deck, &deck.pages[1]).unwrap(),
        });
        let tx = store.transaction().unwrap();
        store::append(&tx, &mut deck, "Native with a corrupt pack").unwrap();
        tx.commit().unwrap();
        let export = export_pptx(temp.path()).unwrap();
        assert_eq!(
            std::fs::read(export["path"].as_str().unwrap()).unwrap(),
            b"historical pptx"
        );
        assert!(
            export["warnings"]
                .as_array()
                .unwrap()
                .iter()
                .all(|warning| { warning["code"] != "shared_layout" })
        );
    }
}
