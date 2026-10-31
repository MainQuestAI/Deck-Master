use crate::error::{Error, Result};
use crate::model::{Deck, Snapshot};
use rusqlite::{
    Connection, OpenFlags, OptionalExtension, Transaction, TransactionBehavior, params,
};
use serde::Serialize;
use sha2::{Digest, Sha256};
use std::fs::{self, File};
use std::io::Write;
use std::path::{Path, PathBuf};
use std::time::Duration;

pub const FORMAT_VERSION: i64 = 1;

pub struct Store {
    pub connection: Connection,
    pub root: PathBuf,
}

#[derive(Debug, Serialize)]
pub struct Version {
    pub id: i64,
    pub created_at: String,
    pub summary: String,
}

impl Store {
    pub fn create(project: &Path, deck: &Deck) -> Result<Self> {
        if project.join(".deckmaster").exists() {
            return Err(Error::Input(
                "目标包含旧项目；请选择新目录，旧项目不会原地改写".into(),
            ));
        }
        fs::create_dir_all(project)?;
        let root = project.join(".deck");
        fs::create_dir(&root)
            .map_err(|e| Error::Input(format!("无法新建项目（可能已存在）：{e}；请选择新目录")))?;
        fs::create_dir(root.join("files"))?;
        let connection = Connection::open(root.join("deck.db"))?;
        let mut store = Self { connection, root };
        store.configure()?;
        let tx = store.transaction()?;
        append(&tx, deck, "新建作品")?;
        tx.commit()?;
        Ok(store)
    }

    pub fn open(project: &Path) -> Result<Self> {
        let root = project.join(".deck");
        if !root.join("deck.db").is_file() {
            return Err(Error::Input(
                "此目录没有 .deck/deck.db；请用 --project 指定作品目录，或先执行 deck new".into(),
            ));
        }
        let connection =
            Connection::open_with_flags(root.join("deck.db"), OpenFlags::SQLITE_OPEN_READ_WRITE)?;
        let mut store = Self { connection, root };
        store.configure()?;
        Ok(store)
    }

    fn configure(&mut self) -> Result<()> {
        self.connection.busy_timeout(Duration::from_secs(5))?;
        let version: i64 = self
            .connection
            .pragma_query_value(None, "user_version", |row| row.get(0))?;
        if version > FORMAT_VERSION {
            return Err(Error::Input(format!(
                "项目格式为 {version}，当前程序只支持 {FORMAT_VERSION}；请升级 deck"
            )));
        }
        if version == 0 {
            let tx = self.transaction()?;
            tx.execute_batch(
                "CREATE TABLE IF NOT EXISTS versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                summary TEXT NOT NULL,
                deck_json TEXT NOT NULL
            ); PRAGMA user_version = 1;",
            )?;
            tx.commit()?;
        }
        Ok(())
    }

    pub fn transaction(&mut self) -> Result<Transaction<'_>> {
        Ok(self
            .connection
            .transaction_with_behavior(TransactionBehavior::Immediate)?)
    }

    pub fn current(&self) -> Result<Snapshot> {
        current(&self.connection)
    }

    pub fn history(&self) -> Result<Vec<Version>> {
        let mut query = self
            .connection
            .prepare("SELECT id, created_at, summary FROM versions ORDER BY id DESC")?;
        Ok(query
            .query_map([], |row| {
                Ok(Version {
                    id: row.get(0)?,
                    created_at: row.get(1)?,
                    summary: row.get(2)?,
                })
            })?
            .collect::<std::result::Result<_, _>>()?)
    }

    pub fn add_file(&self, data: &[u8], extension: &str) -> Result<String> {
        let extension: String = extension
            .chars()
            .filter(char::is_ascii_alphanumeric)
            .take(16)
            .collect();
        let extension = if extension.is_empty() {
            "bin"
        } else {
            &extension
        };
        let name = format!("{:x}.{extension}", Sha256::digest(data));
        let files = self.root.join("files");
        let mut temp = tempfile::NamedTempFile::new_in(&files)?;
        temp.write_all(data)?;
        temp.as_file().sync_all()?;
        match temp.persist_noclobber(files.join(&name)) {
            Ok(_) => {}
            Err(e) if e.error.kind() == std::io::ErrorKind::AlreadyExists => {}
            Err(e) => return Err(Error::Io(e.error)),
        }
        File::open(files)?.sync_all()?;
        Ok(name)
    }

    pub fn file(&self, name: &str) -> Result<PathBuf> {
        file_path(&self.root, name)
    }
}

pub fn file_path(root: &Path, name: &str) -> Result<PathBuf> {
    // File references enter through style patches and tool output, never as paths.
    let valid = name.split_once('.').is_some_and(|(hash, ext)| {
        hash.len() == 64
            && hash.bytes().all(|c| c.is_ascii_hexdigit())
            && !ext.is_empty()
            && ext.bytes().all(|c| c.is_ascii_alphanumeric())
    });
    if !valid {
        return Err(Error::Input(
            "附件引用必须是 files/ 中的 sha256.扩展名；请先添加附件".into(),
        ));
    }
    let path = root.join("files").join(name);
    if !path.is_file() {
        return Err(Error::Input(format!("附件 {name} 不存在；请先添加附件")));
    }
    Ok(path)
}

pub fn current(connection: &Connection) -> Result<Snapshot> {
    let row: Option<(i64, String)> = connection
        .query_row(
            "SELECT id, deck_json FROM versions ORDER BY id DESC LIMIT 1",
            [],
            |row| Ok((row.get(0)?, row.get(1)?)),
        )
        .optional()?;
    let (version, json) =
        row.ok_or_else(|| Error::Input("项目没有作品版本；请检查所选项目".into()))?;
    Ok(Snapshot {
        version,
        deck: serde_json::from_str(&json)?,
    })
}

pub fn load(connection: &Connection, version: i64) -> Result<Deck> {
    let json: Option<String> = connection
        .query_row(
            "SELECT deck_json FROM versions WHERE id = ?",
            [version],
            |row| row.get(0),
        )
        .optional()?;
    Ok(serde_json::from_str(&json.ok_or_else(|| {
        Error::Input(format!("版本 {version} 不存在；请用 deck show 查看历史"))
    })?)?)
}

pub fn append(connection: &Connection, deck: &Deck, summary: &str) -> Result<i64> {
    connection.execute(
        "INSERT INTO versions (summary, deck_json) VALUES (?, ?)",
        params![summary, serde_json::to_string(deck)?],
    )?;
    Ok(connection.last_insert_rowid())
}
