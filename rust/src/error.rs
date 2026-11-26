use rusqlite::ErrorCode;
use serde::Serialize;
use serde_json::{Value, json};
use std::fmt;

pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug, Clone, Serialize)]
pub struct Conflict {
    pub unit: String,
    pub current: Value,
}

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("输入有误：{0}")]
    Input(String),
    #[error("SVG 超出支持子集（{step}）：{message}")]
    SvgSubset {
        step: String,
        message: String,
        details: Value,
    },
    #[error("{0}")]
    Missing(String),
    #[error("缺少依赖：{0}")]
    NeedsTool(String),
    #[error("工具执行失败：{0}")]
    Tool(String),
    #[error("{}", format_conflict(.message, .items))]
    Conflict {
        message: String,
        items: Vec<Conflict>,
    },
    #[error("数据库正忙：{0}；请稍后重试")]
    Busy(String),
    #[error("项目数据已损坏：{0}；请恢复历史版本或核对 .deck/files")]
    DataCorrupt(String),
    #[error("文件操作失败：{0}；请检查路径和访问权限后重试")]
    Io(#[from] std::io::Error),
    #[error("JSON 读写失败：{0}；请检查输入文件格式")]
    Json(#[from] serde_json::Error),
    #[error("数据库操作失败：{0}；请检查项目目录是否可写后重试")]
    Sql(rusqlite::Error),
}

fn format_conflict(message: &str, items: &[Conflict]) -> String {
    if items.is_empty() {
        message.to_string()
    } else {
        let serialized = serde_json::to_string(items).unwrap_or_else(|_| "[]".into());
        format!("{message}：{serialized}")
    }
}

impl From<rusqlite::Error> for Error {
    fn from(error: rusqlite::Error) -> Self {
        match error.sqlite_error_code() {
            Some(ErrorCode::DatabaseBusy | ErrorCode::DatabaseLocked) => {
                Self::Busy(error.to_string())
            }
            Some(ErrorCode::DatabaseCorrupt | ErrorCode::NotADatabase) => {
                Self::DataCorrupt(error.to_string())
            }
            _ => Self::Sql(error),
        }
    }
}

impl Error {
    pub fn conflict(message: impl Into<String>) -> Self {
        Self::Conflict {
            message: message.into(),
            items: Vec::new(),
        }
    }

    pub fn conflict_items(items: Vec<Conflict>) -> Self {
        Self::Conflict {
            message: "保存冲突；请读取当前内容后重新提交".into(),
            items,
        }
    }

    pub fn code(&self) -> &'static str {
        match self {
            Self::Input(_) | Self::Json(_) => "input",
            Self::SvgSubset { .. } => "svg_subset",
            Self::Missing(_) => "missing",
            Self::NeedsTool(_) => "needs_tool",
            Self::Tool(_) => "tool",
            Self::Conflict { .. } => "conflict",
            Self::Busy(_) => "busy",
            Self::DataCorrupt(_) => "data_corrupt",
            Self::Io(_) => "io",
            Self::Sql(_) => "sql",
        }
    }

    pub fn exit_code(&self) -> i32 {
        match self {
            Self::Input(_) | Self::SvgSubset { .. } | Self::Missing(_) | Self::Json(_) => 2,
            Self::NeedsTool(_) => 3,
            Self::Tool(_) => 4,
            Self::Conflict { .. } => 5,
            Self::Busy(_) => 6,
            Self::DataCorrupt(_) => 7,
            Self::Io(_) | Self::Sql(_) => 2,
        }
    }

    pub fn http_status(&self) -> u16 {
        match self {
            Self::Input(_) | Self::SvgSubset { .. } | Self::Json(_) => 400,
            Self::Missing(_) => 404,
            Self::Conflict { .. } => 409,
            Self::NeedsTool(_) | Self::Busy(_) => 503,
            Self::Tool(_) | Self::DataCorrupt(_) | Self::Io(_) | Self::Sql(_) => 500,
        }
    }

    pub fn next_hint(&self, for_http: bool) -> &'static str {
        match self {
            Self::Input(_) | Self::Json(_) => "请按提示修正输入内容或参数后重试",
            Self::SvgSubset { .. } => "请移除或替换不受支持的 SVG 元素/属性后重新提交",
            Self::Missing(_) => "请核对目标 ID 或文件是否存在后重试",
            Self::NeedsTool(_) => {
                if for_http {
                    "请在运行环境安装缺失的工具或字体后重试"
                } else {
                    "请按提示安装缺失的工具或字体并运行 deck doctor 核验"
                }
            }
            Self::Tool(_) => "请查看工具错误详情并修正环境或输入后重试",
            Self::Conflict { .. } => "请读取当前最新内容、解决冲突后重新提交",
            Self::Busy(_) => "数据库正被其他操作占用，请稍后重试",
            Self::DataCorrupt(_) => "项目数据已损坏，请恢复历史版本或核对项目文件",
            Self::Io(_) => "请检查文件路径与访问权限后重试",
            Self::Sql(_) => "请检查项目目录状态后重试",
        }
    }

    pub fn message_for_client(&self, for_http: bool) -> String {
        let raw = match self {
            Self::SvgSubset { message, .. } => message.clone(),
            Self::Conflict { message, .. } => message.clone(),
            _ => self.to_string(),
        };
        if !for_http {
            return raw;
        }
        // Keep HTTP-facing messages free of CLI command syntax.
        raw.replace("请先运行 deck build", "请先在界面执行构建")
            .replace("必须用 --note 填写", "必须填写")
            .replace("用 deck show 查看", "刷新工作区查看")
            .replace("运行 deck doctor", "检查运行环境")
    }

    pub fn to_json(&self, step: Option<&str>, for_http: bool) -> Value {
        let effective_step = match self {
            Self::SvgSubset { step: svg_step, .. } => svg_step.as_str(),
            _ => step.unwrap_or("deck"),
        };
        let message = self.message_for_client(for_http);
        let mut payload = json!({
            "code": self.code(),
            "exit_code": self.exit_code(),
            "step": effective_step,
            "message": message,
            "next": self.next_hint(for_http),
            "error": message,
        });
        match self {
            Self::SvgSubset { details, .. } if !details.is_null() => {
                payload["details"] = details.clone();
            }
            Self::Conflict { items, .. } if !items.is_empty() => {
                payload["details"] = json!({"conflicts": items});
            }
            _ => {}
        }
        payload
    }
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ErrorFormat {
    Text,
    Json,
}

impl fmt::Display for ErrorFormat {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Text => write!(f, "text"),
            Self::Json => write!(f, "json"),
        }
    }
}
