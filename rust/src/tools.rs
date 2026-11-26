use crate::error::{Error, Result};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::ffi::OsString;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

const DEFAULT_TIMEOUT_SECS: u64 = 600;

fn timeout_duration() -> Duration {
    std::env::var("DECK_TOOLS_TIMEOUT_SECS")
        .ok()
        .and_then(|value| value.trim().parse::<u64>().ok())
        .filter(|&secs| secs > 0)
        .map(Duration::from_secs)
        .unwrap_or_else(|| Duration::from_secs(DEFAULT_TIMEOUT_SECS))
}

#[derive(Debug, Serialize, Deserialize)]
pub struct Extraction {
    pub text: String,
    pub status: String,
    pub locators: Vec<Value>,
    pub tables: Vec<Value>,
    pub image_pages: Vec<Value>,
    pub detail: String,
}

fn interpreter() -> Result<OsString> {
    if let Some(value) = std::env::var_os("DECK_TOOLS_PYTHON") {
        return Ok(value);
    }
    if let Ok(exe) = std::env::current_exe()
        && let Some(path) = installed_python(&exe)
    {
        return Ok(path.into());
    }
    Err(Error::NeedsTool(
        "请把 deck-tools 安装到独立 venv，并设置 DECK_TOOLS_PYTHON；或运行 scripts/install.sh"
            .into(),
    ))
}

fn installed_python(exe: &Path) -> Option<PathBuf> {
    let installation = exe.parent()?.parent()?;
    if installation.parent()?.file_name()? != "installations" {
        return None;
    }
    let python = installation.join("share/deck/venv/bin/python");
    python.is_file().then_some(python)
}

pub fn invoke(command: &str, value: &Value) -> Result<Value> {
    let python = interpreter()?;
    // Isolate job file and subprocess cwd away from the project directory so customer
    // materials (e.g. json.py) cannot shadow stdlib or deck_tools imports.
    let job_dir = tempfile::tempdir()?;
    let job_path = job_dir.path().join("job.json");
    std::fs::write(&job_path, serde_json::to_vec(value)?)?;
    let mut child = Command::new(python)
        .args(["-P", "-m", "deck_tools", command])
        .arg(&job_path)
        .env("PYTHONSAFEPATH", "1")
        .current_dir(job_dir.path())
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| {
            Error::NeedsTool(format!(
                "无法启动 deck-tools 解释器：{e}；请检查 DECK_TOOLS_PYTHON 或 scripts/install.sh 安装的环境"
            ))
        })?;
    let mut stdout_pipe = child.stdout.take();
    let mut stderr_pipe = child.stderr.take();
    let stdout_thread = std::thread::spawn(move || {
        let mut buf = Vec::new();
        if let Some(ref mut pipe) = stdout_pipe {
            let _ = pipe.read_to_end(&mut buf);
        }
        buf
    });
    let stderr_thread = std::thread::spawn(move || {
        let mut buf = Vec::new();
        if let Some(ref mut pipe) = stderr_pipe {
            let _ = pipe.read_to_end(&mut buf);
        }
        buf
    });
    let timeout = timeout_duration();
    let started = Instant::now();
    let status = loop {
        if let Some(status) = child.try_wait()? {
            break status;
        }
        if started.elapsed() >= timeout {
            let _ = child.kill();
            let _ = child.wait();
            // Do not join reader threads on timeout: a grandchild (e.g. soffice) may still hold pipes open.
            return Err(Error::Tool(format!(
                "{command} 执行超时（超过 {} 秒）；请检查环境或调整 DECK_TOOLS_TIMEOUT_SECS 后重试",
                timeout.as_secs()
            )));
        }
        std::thread::sleep(Duration::from_millis(20));
    };
    let stdout = stdout_thread.join().unwrap_or_default();
    let stderr = stderr_thread.join().unwrap_or_default();
    if !status.success() {
        let detail = String::from_utf8_lossy(&stderr).trim().to_string();
        return Err(match status.code() {
            Some(2) => {
                if let Ok(parsed) = serde_json::from_str::<Value>(&detail)
                    && (parsed.get("code").and_then(Value::as_str) == Some("svg_subset")
                        || (parsed.get("rule").is_some() && parsed.get("message").is_some()))
                {
                    let message = parsed
                        .get("message")
                        .and_then(Value::as_str)
                        .unwrap_or(&detail)
                        .to_string();
                    Error::SvgSubset {
                        step: command.to_string(),
                        message,
                        details: parsed,
                    }
                } else {
                    Error::Input(detail)
                }
            }
            Some(3) => Error::NeedsTool(detail),
            _ if detail.contains("No module named deck_tools") => Error::NeedsTool(
                "当前解释器没有 deck-tools；请在 DECK_TOOLS_PYTHON 对应环境安装 deck-tools".into(),
            ),
            _ => Error::Tool(format!("{command}：{detail}；请修复工具后重试")),
        });
    }
    serde_json::from_slice(&stdout).map_err(|e| {
        Error::Tool(format!(
            "{command} 返回无效 JSON：{e}；请检查 deck-tools 安装"
        ))
    })
}

pub fn read_source(path: &Path) -> Result<Extraction> {
    let extraction: Extraction = serde_json::from_value(invoke(
        "read-source",
        &serde_json::json!({"path": path.canonicalize()?}),
    )?)?;
    if !["read", "pending_visual", "needs_tool"].contains(&extraction.status.as_str()) {
        return Err(Error::Tool(
            "read-source 返回未知读取状态；请检查 deck-tools 安装".into(),
        ));
    }
    Ok(extraction)
}

#[cfg(test)]
mod tests {
    use super::installed_python;
    use std::fs;

    #[test]
    fn installed_venv_is_pinned_to_the_real_installation_directory() {
        let temp = tempfile::tempdir().unwrap();
        let installation = temp.path().join("share/deck/installations/first");
        let python = installation
            .join("share")
            .join("deck")
            .join("venv")
            .join("bin")
            .join("python");
        fs::create_dir_all(python.parent().unwrap()).unwrap();
        fs::write(&python, "").unwrap();
        let exe = installation.join("bin").join("deck");
        fs::create_dir_all(exe.parent().unwrap()).unwrap();
        fs::write(&exe, "").unwrap();
        assert_eq!(installed_python(&exe).as_deref(), Some(python.as_path()));
        assert!(installed_python(&python).is_none());
        assert!(installed_python(&temp.path().join("bin/deck")).is_none());
    }
}
