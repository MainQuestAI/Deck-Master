use serde::Serialize;
use serde_json::Value;

pub type Result<T> = std::result::Result<T, Error>;

#[derive(Debug, Serialize)]
pub struct Conflict {
    pub unit: String,
    pub current: Value,
}

#[derive(Debug, thiserror::Error)]
pub enum Error {
    #[error("输入有误：{0}")]
    Input(String),
    #[error("{0} 不存在；请检查编号或文件引用")]
    Missing(String),
    #[error("缺少依赖：{0}")]
    NeedsTool(String),
    #[error("工具执行失败：{0}")]
    Tool(String),
    #[error("保存冲突；请读取当前内容后重新提交：{0}")]
    Conflict(String),
    #[error("文件操作失败：{0}；请检查路径和访问权限后重试")]
    Io(#[from] std::io::Error),
    #[error("JSON 读写失败：{0}；请检查输入文件格式")]
    Json(#[from] serde_json::Error),
    #[error("数据库操作失败：{0}；请检查项目目录是否可写后重试")]
    Sql(#[from] rusqlite::Error),
}

impl Error {
    pub fn exit_code(&self) -> i32 {
        match self {
            Self::NeedsTool(_) => 3,
            Self::Tool(_) => 4,
            Self::Conflict(_) => 5,
            _ => 2,
        }
    }
}
