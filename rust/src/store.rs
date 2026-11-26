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

pub const FORMAT_VERSION: i64 = 7;

const FRESH_V7: &str = "
CREATE TABLE versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    summary TEXT NOT NULL,
    deck_json TEXT NOT NULL
);
CREATE TABLE runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL, status TEXT NOT NULL,
    max_calls INTEGER, calls_used INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE run_pages (
    run_id INTEGER NOT NULL, page_id TEXT NOT NULL, basis TEXT NOT NULL,
    status TEXT NOT NULL, result_file TEXT, preview_file TEXT,
    PRIMARY KEY (run_id, page_id)
);
CREATE TABLE builds (
    id INTEGER PRIMARY KEY AUTOINCREMENT, version_id INTEGER NOT NULL,
    input_digest TEXT NOT NULL, pptx_file TEXT NOT NULL,
    findings_json TEXT NOT NULL, missing_pages TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    version_id INTEGER NOT NULL, page_id TEXT,
    reviewer TEXT NOT NULL,
    method TEXT NOT NULL CHECK (method IN ('self_check','other_model','human')),
    text TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    resolved_at TEXT,
    record_kind TEXT NOT NULL DEFAULT 'comment' CHECK (record_kind IN ('comment','content_review')),
    snapshot_json TEXT,
    checks_json TEXT
);
PRAGMA user_version = 7;";

pub fn unsupported_format_message(version: i64, supported: i64) -> String {
    format!("项目格式为 {version}，当前程序只支持 {supported}；请升级 deck")
}

pub struct Store {
    #[doc(hidden)]
    pub connection: Connection,
    pub root: PathBuf,
}

#[derive(Debug, Serialize)]
pub struct Version {
    pub id: i64,
    pub created_at: String,
    pub summary: String,
}

fn enable_wal_mode(connection: &Connection) -> Result<()> {
    let mode: String = connection.pragma_query_value(None, "journal_mode", |row| row.get(0))?;
    if !mode.eq_ignore_ascii_case("wal") {
        let _: String = connection.query_row("PRAGMA journal_mode = WAL", [], |row| row.get(0))?;
    }
    connection.pragma_update(None, "synchronous", "NORMAL")?;
    Ok(())
}

impl Store {
    pub fn create(project: &Path, deck: &Deck) -> Result<Self> {
        if project.join(".deckmaster").exists() {
            return Err(Error::Input(
                "目标包含旧项目；请选择新目录，旧项目不会原地改写".into(),
            ));
        }
        let root = project.join(".deck");
        if root.exists() {
            return Err(Error::Input(
                "无法新建项目（可能已存在）：目标目录已包含 .deck；请选择新目录".into(),
            ));
        }
        fs::create_dir_all(project)?;
        // Stage creation in a sibling temp directory so any failure leaves no half-initialized .deck/.
        let staging = tempfile::Builder::new()
            .prefix(".deck-init-")
            .tempdir_in(project)?;
        fs::create_dir(staging.path().join("files"))?;
        {
            let mut connection = Connection::open(staging.path().join("deck.db"))?;
            connection.busy_timeout(Duration::from_secs(5))?;
            enable_wal_mode(&connection)?;
            let tx = connection.transaction_with_behavior(TransactionBehavior::Immediate)?;
            tx.execute_batch(FRESH_V7)?;
            let mut deck = deck.clone();
            append(&tx, &mut deck, "新建作品")?;
            tx.commit()?;
        }
        let kept = staging.keep();
        if let Err(error) = fs::rename(&kept, &root) {
            let _ = fs::remove_dir_all(&kept);
            return Err(Error::Input(format!(
                "无法新建项目（可能已存在）：{error}；请选择新目录"
            )));
        }
        let connection =
            Connection::open_with_flags(root.join("deck.db"), OpenFlags::SQLITE_OPEN_READ_WRITE)?;
        connection.busy_timeout(Duration::from_secs(5))?;
        connection.pragma_update(None, "synchronous", "NORMAL")?;
        Ok(Self { connection, root })
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
            return Err(Error::Input(unsupported_format_message(
                version,
                FORMAT_VERSION,
            )));
        }
        // v6 stays readable. v7 columns are added in the same transaction as the
        // first versions insert, not when a command only opens the database.
        if version == 6 || version == FORMAT_VERSION {
            return Ok(());
        }
        // Read the format after acquiring the write transaction: two clients may
        // open the same old project while another client is migrating it.
        let tx = self.transaction()?;
        let version: i64 = tx.pragma_query_value(None, "user_version", |row| row.get(0))?;
        if version > FORMAT_VERSION {
            return Err(Error::Input(unsupported_format_message(
                version,
                FORMAT_VERSION,
            )));
        }
        if version == 6 || version == FORMAT_VERSION {
            return Ok(());
        }
        if version == 0 {
            tx.execute_batch(
                "CREATE TABLE IF NOT EXISTS versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                summary TEXT NOT NULL,
                deck_json TEXT NOT NULL
            );",
            )?;
        }
        if version < 2 {
            tx.execute_batch(
                "CREATE TABLE runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL, status TEXT NOT NULL,
                max_calls INTEGER, calls_used INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            );
            CREATE TABLE run_pages (
                run_id INTEGER NOT NULL, page_id TEXT NOT NULL, basis TEXT NOT NULL,
                status TEXT NOT NULL, result_file TEXT,
                PRIMARY KEY (run_id, page_id)
            );
            CREATE TABLE builds (
                id INTEGER PRIMARY KEY AUTOINCREMENT, version_id INTEGER NOT NULL,
                input_digest TEXT NOT NULL, pptx_file TEXT NOT NULL,
                findings_json TEXT NOT NULL, missing_pages TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
            );
            PRAGMA user_version = 2;",
            )?;
        }
        if version < 3 {
            tx.execute_batch(
                "CREATE TABLE reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id INTEGER NOT NULL, page_id TEXT,
                reviewer TEXT NOT NULL,
                method TEXT NOT NULL CHECK (method IN ('self_check','other_model','human')),
                text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved')),
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
                resolved_at TEXT
            );
            PRAGMA user_version = 3;",
            )?;
        }
        if version < 4 {
            // Candidate previews are recorded at check-page time. Reads only return the name.
            tx.execute_batch(
                "ALTER TABLE run_pages ADD COLUMN preview_file TEXT;
            PRAGMA user_version = 4;",
            )?;
        }
        if version < 5 {
            tx.pragma_update(None, "user_version", 5)?;
        }
        if version < 6 {
            tx.pragma_update(None, "user_version", 6)?;
        }
        tx.commit()?;
        Ok(())
    }

    pub fn transaction(&mut self) -> Result<Transaction<'_>> {
        enable_wal_mode(&self.connection)?;
        Ok(self
            .connection
            .transaction_with_behavior(TransactionBehavior::Immediate)?)
    }

    pub fn read_transaction(&mut self) -> Result<Transaction<'_>> {
        Ok(self.connection.transaction()?)
    }

    pub fn current(&self) -> Result<Snapshot> {
        current(&self.connection)
    }

    pub fn history(&self) -> Result<Vec<Version>> {
        history(&self.connection)
    }

    pub fn add_file(&self, data: &[u8], extension: &str) -> Result<String> {
        add_file(&self.root, data, extension)
    }

    pub fn file(&self, name: &str) -> Result<PathBuf> {
        file_path(&self.root, name)
    }
}

pub fn add_file(root: &Path, data: &[u8], extension: &str) -> Result<String> {
    let extension: String = if extension == "native.json" {
        extension.into()
    } else {
        extension
            .chars()
            .filter(char::is_ascii_alphanumeric)
            .take(16)
            .collect()
    };
    let extension = if extension.is_empty() {
        "bin"
    } else {
        &extension
    };
    let name = format!("{:x}.{extension}", Sha256::digest(data));
    let files = root.join("files");
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

pub fn file_path(root: &Path, name: &str) -> Result<PathBuf> {
    // File references enter through style patches and tool output, never as paths.
    let valid = name.split_once('.').is_some_and(|(hash, ext)| {
        hash.len() == 64
            && hash.bytes().all(|c| c.is_ascii_hexdigit())
            && !ext.is_empty()
            && (ext == "native.json" || ext.bytes().all(|c| c.is_ascii_alphanumeric()))
    });
    if !valid {
        return Err(Error::Input(
            "附件引用必须是 files/ 中的 sha256.扩展名；请先添加附件".into(),
        ));
    }
    let path = root.join("files").join(name);
    if !path.is_file() {
        return Err(Error::Missing(format!("附件 {name} 不存在;请先添加附件")));
    }
    Ok(path)
}

pub fn history(connection: &Connection) -> Result<Vec<Version>> {
    let mut query =
        connection.prepare("SELECT id, created_at, summary FROM versions ORDER BY id DESC")?;
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
    load_optional(connection, version)?
        .ok_or_else(|| Error::Input(format!("版本 {version} 不存在；请用 deck show 查看历史")))
}

pub(crate) fn load_optional(connection: &Connection, version: i64) -> Result<Option<Deck>> {
    let json: Option<String> = connection
        .query_row(
            "SELECT deck_json FROM versions WHERE id = ?",
            [version],
            |row| row.get(0),
        )
        .optional()?;
    json.map(|json| serde_json::from_str(&json))
        .transpose()
        .map_err(Error::from)
}

fn has_column(connection: &Connection, table: &str, column: &str) -> Result<bool> {
    let mut statement = connection.prepare(&format!("PRAGMA table_info({table})"))?;
    let mut rows = statement.query([])?;
    while let Some(row) = rows.next()? {
        let name: String = row.get(1)?;
        if name == column {
            return Ok(true);
        }
    }
    Ok(false)
}

pub(crate) fn user_version(connection: &Connection) -> Result<i64> {
    Ok(connection.pragma_query_value(None, "user_version", |row| row.get(0))?)
}

pub(crate) fn reviews_have_record_kind(connection: &Connection) -> Result<bool> {
    has_column(connection, "reviews", "record_kind")
}

fn migrate_v7(connection: &Connection) -> Result<()> {
    let version = user_version(connection)?;
    if version >= FORMAT_VERSION {
        return Ok(());
    }
    if version < 6 {
        return Err(Error::Input(
            "项目格式尚未完成到 6 的迁移；请重新打开项目后再保存".into(),
        ));
    }
    if !has_column(connection, "reviews", "record_kind")? {
        connection.execute(
            "ALTER TABLE reviews ADD COLUMN record_kind TEXT NOT NULL DEFAULT 'comment' CHECK (record_kind IN ('comment','content_review'))",
            [],
        )?;
    }
    if !has_column(connection, "reviews", "snapshot_json")? {
        connection.execute("ALTER TABLE reviews ADD COLUMN snapshot_json TEXT", [])?;
    }
    if !has_column(connection, "reviews", "checks_json")? {
        connection.execute("ALTER TABLE reviews ADD COLUMN checks_json TEXT", [])?;
    }
    connection.pragma_update(None, "user_version", FORMAT_VERSION)?;
    Ok(())
}

pub fn max_material_number(connection: &Connection) -> Result<u64> {
    #[derive(serde::Deserialize)]
    struct MaterialId {
        id: String,
    }
    #[derive(serde::Deserialize)]
    struct MaterialsOnly {
        #[serde(default)]
        materials: Vec<MaterialId>,
    }

    let mut query = connection.prepare("SELECT deck_json FROM versions")?;
    let mut rows = query.query([])?;
    let mut max_number = 0u64;
    while let Some(row) = rows.next()? {
        let json: String = row.get(0)?;
        let parsed: MaterialsOnly = serde_json::from_str(&json)?;
        for material in parsed.materials {
            if let Some(number) = material
                .id
                .strip_prefix('m')
                .and_then(|digits| digits.parse::<u64>().ok())
            {
                max_number = max_number.max(number);
            }
        }
    }
    Ok(max_number)
}

pub fn append(tx: &Transaction<'_>, deck: &mut Deck, summary: &str) -> Result<i64> {
    migrate_v7(tx)?;
    tx.execute(
        "INSERT INTO versions (summary, deck_json) VALUES (?, ?)",
        params![summary, serde_json::to_string(deck)?],
    )?;
    Ok(tx.last_insert_rowid())
}
