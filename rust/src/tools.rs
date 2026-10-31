use crate::error::{Error, Result};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::io::Write;
use std::path::Path;
use std::process::Command;

#[derive(Debug, Serialize, Deserialize)]
pub struct Extraction {
    pub text: String,
    pub status: String,
    pub locators: Vec<Value>,
    pub tables: Vec<Value>,
    pub image_pages: Vec<Value>,
    pub detail: String,
}

pub fn read_source(path: &Path) -> Result<Extraction> {
    let python = std::env::var_os("DECK_TOOLS_PYTHON").ok_or_else(|| {
        Error::NeedsTool(
            "请把 deck-tools 安装到独立 venv，并设置 DECK_TOOLS_PYTHON 为该环境的 Python 路径"
                .into(),
        )
    })?;
    let mut job = tempfile::NamedTempFile::new()?;
    serde_json::to_writer(&mut job, &serde_json::json!({"path": path.canonicalize()?}))?;
    job.flush()?;
    let output = Command::new(python)
        .args(["-m", "deck_tools", "read-source"])
        .arg(job.path())
        .output()
        .map_err(|e| {
            Error::NeedsTool(format!(
                "无法启动 DECK_TOOLS_PYTHON：{e}；请检查解释器路径并安装 deck-tools"
            ))
        })?;
    if !output.status.success() {
        let detail = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(match output.status.code() {
            Some(2) => Error::Input(detail),
            Some(3) => Error::NeedsTool(detail),
            _ if detail.contains("No module named deck_tools") => Error::NeedsTool(
                "当前解释器没有 deck-tools；请在 DECK_TOOLS_PYTHON 对应环境安装 deck-tools".into(),
            ),
            _ => Error::Tool(format!("read-source：{detail}；请修复工具后重试")),
        });
    }
    let extraction: Extraction = serde_json::from_slice(&output.stdout).map_err(|e| {
        Error::Tool(format!(
            "read-source 返回无效 JSON：{e}；请检查 deck-tools 安装"
        ))
    })?;
    if !["read", "pending_visual", "needs_tool"].contains(&extraction.status.as_str()) {
        return Err(Error::Tool(
            "read-source 返回未知读取状态；请检查 deck-tools 安装".into(),
        ));
    }
    Ok(extraction)
}
