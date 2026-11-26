use crate::error::{Error, Result};
use crate::store::{self, Store};
use serde_json::{Value, json};
use std::path::Path;

pub fn material_add(project: &Path, source: &Path) -> Result<Value> {
    let mut store = Store::open(project)?;
    let name = source
        .file_name()
        .and_then(|name| name.to_str())
        .ok_or_else(|| Error::Input("材料需要有效文件名".into()))?;
    let data = std::fs::read(source)?;
    let extension = source
        .extension()
        .and_then(|ext| ext.to_str())
        .unwrap_or("bin")
        .to_lowercase();
    let file = store.add_file(&data, &extension)?;
    // Parse the immutable copy, not a source the author may still be editing.
    let extraction = crate::tools::read_source(&store.file(&file)?)?;
    let text_file = store.add_file(extraction.text.as_bytes(), "txt")?;
    let tx = store.transaction()?;
    let current = store::current(&tx)?;
    let mut deck = current.deck;
    let existing = deck.materials.iter().position(|m| m.file == file);
    let mut material = if let Some(index) = existing {
        deck.materials[index].clone()
    } else {
        let mut number = 1;
        while deck.materials.iter().any(|m| m.id == format!("m{number}")) {
            number += 1;
        }
        crate::model::Material {
            id: format!("m{number}"),
            name: name.into(),
            file,
            text_file: String::new(),
            status: String::new(),
        }
    };
    if extraction.status == "needs_tool" && material.status == "read" {
        return Err(Error::NeedsTool(format!(
            "材料 {} 本次未能重新解析：{}；已保留已有成功解析结果，可继续使用 material text；如需重新解析，请安装对应工具后重试 material add",
            material.id, extraction.detail
        )));
    }
    material.text_file = text_file;
    material.status = if extraction.status == "needs_tool" {
        "needs_tool"
    } else {
        "read"
    }
    .into();
    let changed = if let Some(index) = existing {
        let changed = deck.materials[index] != material;
        deck.materials[index] = material.clone();
        changed
    } else {
        deck.materials.push(material.clone());
        true
    };
    let version = if changed {
        store::append(&tx, &mut deck, "添加材料")?
    } else {
        current.version
    };
    tx.commit()?;
    if extraction.status == "needs_tool" {
        return Err(Error::NeedsTool(format!(
            "原件已保存为 {}，解析未完成：{}；请安装对应工具后重试 material add",
            material.id, extraction.detail
        )));
    }
    Ok(json!({ "version": version, "material": material, "extraction": extraction }))
}

pub fn material_text(project: &Path, id: &str) -> Result<Value> {
    let store = Store::open(project)?;
    let snapshot = store.current()?;
    let material = snapshot
        .deck
        .materials
        .iter()
        .find(|m| m.id == id)
        .ok_or_else(|| Error::Input(format!("材料 {id} 不存在；请用 deck show 查看材料")))?;
    let original = if material.file.is_empty() {
        None
    } else {
        match store.file(&material.file) {
            Ok(path) => Some(path),
            Err(Error::Missing(_)) => None,
            Err(error) => return Err(error),
        }
    };
    if material.status == "needs_tool" {
        return Err(Error::NeedsTool(format!(
            "材料尚未完成解析；原件：{}；请安装对应工具，再次运行 material add",
            original
                .as_ref()
                .map(|path| path.display().to_string())
                .unwrap_or_else(|| "不可用".into())
        )));
    }
    Ok(
        json!({ "id": id, "status": material.status, "path": store.file(&material.text_file)?, "original_path": original }),
    )
}
