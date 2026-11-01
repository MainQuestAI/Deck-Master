use deck::{model::Patch, ops, store::Store};
use serde_json::{Value, json};
use std::{
    collections::HashMap,
    io::{BufRead, BufReader, Read, Write},
    net::{SocketAddr, TcpStream},
    path::Path,
    process::{Child, Command, Stdio},
    time::Duration,
};

struct Service {
    child: Child,
    address: SocketAddr,
}

impl Drop for Service {
    fn drop(&mut self) {
        let _ = self.child.kill();
        self.child.wait().unwrap();
    }
}

struct Reply {
    status: u16,
    headers: HashMap<String, String>,
    body: Vec<u8>,
}

impl Reply {
    fn json(&self) -> Value {
        serde_json::from_slice(&self.body).unwrap()
    }

    fn artifact_status(&self) -> Value {
        serde_json::from_str(&self.headers["x-deck-status"]).unwrap()
    }
}

impl Service {
    fn start(project: &Path) -> Self {
        let mut child = Command::new(env!("CARGO_BIN_EXE_deck"))
            .arg("serve")
            .arg(project)
            .current_dir(project)
            .stdout(Stdio::piped())
            .spawn()
            .unwrap();
        let mut address = String::new();
        BufReader::new(child.stdout.take().unwrap())
            .read_line(&mut address)
            .unwrap();
        let address = address
            .trim()
            .strip_prefix("http://")
            .unwrap()
            .parse()
            .unwrap();
        Self { child, address }
    }

    fn request(&self, method: &str, path: &str, headers: &[(&str, &str)], body: &str) -> Reply {
        let mut stream = TcpStream::connect(self.address).unwrap();
        stream
            .set_read_timeout(Some(Duration::from_secs(30)))
            .unwrap();
        write!(
            stream,
            "{method} {path} HTTP/1.1\r\nConnection: close\r\nContent-Length: {}\r\n",
            body.len()
        )
        .unwrap();
        if !headers
            .iter()
            .any(|(name, _)| name.eq_ignore_ascii_case("host"))
        {
            write!(stream, "Host: {}\r\n", self.address).unwrap();
        }
        for (name, value) in headers {
            write!(stream, "{name}: {value}\r\n").unwrap();
        }
        write!(stream, "\r\n{body}").unwrap();
        let mut bytes = Vec::new();
        stream.read_to_end(&mut bytes).unwrap();
        let end = bytes.windows(4).position(|s| s == b"\r\n\r\n").unwrap();
        let head = std::str::from_utf8(&bytes[..end]).unwrap();
        let status = head
            .lines()
            .next()
            .unwrap()
            .split_whitespace()
            .nth(1)
            .unwrap()
            .parse()
            .unwrap();
        let headers = head
            .lines()
            .skip(1)
            .map(|line| {
                let (key, value) = line.split_once(':').unwrap();
                (key.to_ascii_lowercase(), value.trim().to_owned())
            })
            .collect();
        Reply {
            status,
            headers,
            body: bytes[end + 4..].to_vec(),
        }
    }
}

fn edit(project: &Path, base: i64, value: Value) -> i64 {
    let patch: Patch = serde_json::from_value(value).unwrap();
    ops::put(project, base, patch).unwrap().version
}

#[test]
fn http_edits_conflicts_polling_history_restore_and_incomplete_markdown() {
    let temp = tempfile::tempdir().unwrap();
    ops::new(temp.path(), "合成方案".into()).unwrap();
    let service = Service::start(temp.path());
    assert_eq!(service.address.ip().to_string(), "127.0.0.1");
    let first = service.request("GET", "/api/deck", &[], "");
    assert_eq!(first.status, 200);
    assert_eq!(first.json()["history"][0]["id"], 1);
    assert_eq!(first.json()["runs"], json!([]));
    let submitted =
        json!({"brief":{"title":"已保存"},"order":["p1"],"pages":[{"id":"p1","notes":"作者讲稿"}]});
    let saved = service.request("PUT", "/api/deck?base=1", &[], &submitted.to_string());
    assert_eq!(saved.status, 200);
    let base = saved.json()["version"].as_i64().unwrap();
    let cli_version = edit(
        temp.path(),
        base,
        json!({"pages":[{"id":"p1","notes":"CLI 更新"}]}),
    );
    let conflict_input =
        json!({"pages":[{"id":"p1","notes":"浏览器尚未保存"}],"brief":{"title":"不能部分写入"}});
    let conflict = service.request(
        "PUT",
        &format!("/api/deck?base={base}"),
        &[],
        &conflict_input.to_string(),
    );
    assert_eq!(conflict.status, 409);
    assert_eq!(conflict.json()["exit_code"], 5);
    assert_eq!(conflict.json()["submitted"], conflict_input);
    assert_eq!(
        conflict.json()["conflicts"][0]["current"]["notes"],
        "CLI 更新"
    );
    let polled = service.request("GET", "/api/deck", &[], "").json();
    assert_eq!(polled["version"], cli_version);
    assert_eq!(polled["deck"]["brief"]["title"], "已保存");
    let markdown = service.request("GET", "/api/export/md", &[], "");
    assert_eq!(markdown.status, 200);
    assert!(
        String::from_utf8(markdown.body.clone())
            .unwrap()
            .contains("CLI 更新")
    );
    assert_eq!(markdown.artifact_status()["missing_pages"], json!(["p1"]));
    let restored = service.request("POST", "/api/restore/1", &[], "");
    assert_eq!(restored.status, 200);
    assert!(restored.json()["version"].as_i64().unwrap() > cli_version);
    assert_eq!(restored.json()["deck"]["pages"], json!([]));
    assert_eq!(
        service.request("GET", "/api/deck", &[], "").json()["history"]
            .as_array()
            .unwrap()
            .len(),
        4
    );
}

#[test]
fn rejects_rebinding_origins_duplicate_headers_and_path_traversal() {
    let temp = tempfile::tempdir().unwrap();
    ops::new(temp.path(), String::new()).unwrap();
    let service = Service::start(temp.path());
    for host in [
        "evil.example",
        "127.0.0.1.evil.example",
        "localhost.evil.example",
        "127.0.0.1:1",
        "user@127.0.0.1",
    ] {
        assert_eq!(
            service
                .request(
                    "PUT",
                    "/api/deck?base=1",
                    &[("Host", host)],
                    r#"{"brief":{"title":"attack"}}"#
                )
                .status,
            403
        );
    }
    for origin in [
        "https://evil.example",
        "null",
        "http://localhost.evil.example",
        "http://127.0.0.1:1",
        "http://user@127.0.0.1",
    ] {
        assert_eq!(
            service
                .request("POST", "/api/restore/1", &[("Origin", origin)], "")
                .status,
            403
        );
    }
    let host = service.address.to_string();
    assert_eq!(
        service
            .request(
                "GET",
                "/api/deck",
                &[("Host", &host), ("Host", "evil.example")],
                ""
            )
            .status,
        403
    );
    let origin = format!("http://localhost:{}", service.address.port());
    assert_eq!(
        service
            .request(
                "GET",
                "/api/deck",
                &[("Origin", &origin), ("Origin", &origin)],
                ""
            )
            .status,
        403
    );
    assert_eq!(
        service
            .request("GET", "/api/deck", &[("Origin", &origin)], "")
            .status,
        200
    );
    let local_host = format!("localhost:{}", service.address.port());
    assert_eq!(
        service
            .request("GET", "/api/deck", &[("Host", &local_host)], "")
            .status,
        200
    );
    for sha in [
        "../deck.db",
        "%2e%2e%2fdeck.db",
        "bad",
        &"a".repeat(63),
        &"g".repeat(64),
        &format!("{}/other", "a".repeat(64)),
    ] {
        assert_eq!(
            service
                .request("GET", &format!("/api/files/{sha}"), &[], "")
                .status,
            400
        );
    }
    for path in [
        "/api/runs/cancel",
        "/api/runs//cancel",
        "/api/restore/invalid",
    ] {
        assert_eq!(service.request("POST", path, &[], "").status, 400);
    }
    assert_eq!(ops::get(temp.path(), None).unwrap()["version"], 1);
    assert_eq!(service.request("POST", "/api/reviews", &[], "").status, 404);
}

#[test]
fn files_are_project_scoped_and_symlinks_cannot_escape() {
    let first = tempfile::tempdir().unwrap();
    let second = tempfile::tempdir().unwrap();
    ops::new(first.path(), String::new()).unwrap();
    ops::new(second.path(), String::new()).unwrap();
    let local = Store::open(first.path())
        .unwrap()
        .add_file(b"local", "png")
        .unwrap();
    let foreign = Store::open(second.path())
        .unwrap()
        .add_file(b"foreign", "png")
        .unwrap();
    let service = Service::start(first.path());
    let downloaded = service.request("GET", &format!("/api/files/{}", &local[..64]), &[], "");
    assert_eq!(downloaded.status, 200);
    assert_eq!(downloaded.body, b"local");
    assert!(downloaded.headers["content-security-policy"].contains("sandbox"));
    assert_eq!(
        service
            .request("GET", &format!("/api/files/{}", &foreign[..64]), &[], "")
            .status,
        404
    );
    #[cfg(unix)]
    {
        let outside = second.path().join(".deck/files").join(&foreign);
        std::os::unix::fs::symlink(outside, first.path().join(".deck/files").join(&foreign))
            .unwrap();
        assert_eq!(
            service
                .request("GET", &format!("/api/files/{}", &foreign[..64]), &[], "")
                .status,
            400
        );
    }
}

#[test]
fn http_cancel_uses_ops_and_late_result_stays_unadopted() {
    let temp = tempfile::tempdir().unwrap();
    ops::new(temp.path(), String::new()).unwrap();
    edit(
        temp.path(),
        1,
        json!({"order":["p1"],"pages":[{"id":"p1"}]}),
    );
    let run = ops::run_start(temp.path(), "image", &["p1".into()], None).unwrap();
    let id = run["runs"][0]["id"].as_i64().unwrap();
    ops::run_call(temp.path(), id, "p1", false).unwrap();
    let service = Service::start(temp.path());
    let stopped = service.request("POST", &format!("/api/runs/{id}/cancel"), &[], "");
    assert_eq!(stopped.status, 200);
    assert_eq!(stopped.json()["runs"][0]["status"], "cancelled");
    assert!(stopped.json()["runs"][0]["pages"][0].get("work").is_none());
    let bitmap = temp.path().join("late.png");
    let python = std::env::var_os("DECK_TOOLS_PYTHON").expect("install this worktree's deck-tools");
    assert!(
        Command::new(python)
            .args([
                "-c",
                "from PIL import Image; import sys; Image.new('RGB',(8,8)).save(sys.argv[1])"
            ])
            .arg(&bitmap)
            .status()
            .unwrap()
            .success()
    );
    assert_eq!(
        ops::run_result(temp.path(), id, "p1", &bitmap).unwrap()["adopted"],
        false
    );
    let polled = service.request("GET", "/api/deck", &[], "").json();
    assert_eq!(polled["runs"][0]["pages"][0]["status"], "unadopted");
    assert_eq!(polled["deck"]["pages"][0]["image"], Value::Null);
}

#[test]
fn polling_can_read_beside_a_cli_writer_and_releases_its_read_transaction() {
    let temp = tempfile::tempdir().unwrap();
    ops::new(temp.path(), String::new()).unwrap();
    let service = Service::start(temp.path());
    let mut writer = Store::open(temp.path()).unwrap();
    let tx = writer.transaction().unwrap();
    assert_eq!(service.request("GET", "/api/deck", &[], "").status, 200);
    tx.commit().unwrap();
    assert_eq!(
        edit(temp.path(), 1, json!({"brief":{"title":"CLI commit"}})),
        2
    );
    assert_eq!(
        service.request("GET", "/api/deck", &[], "").json()["version"],
        2
    );
    assert_eq!(service.request("GET", "/", &[], "").status, 200);
    assert_eq!(service.request("GET", "/missing.js", &[], "").status, 404);
}

#[test]
fn build_downloads_report_missing_stale_and_changed_inputs_without_gating() {
    let temp = tempfile::tempdir().unwrap();
    ops::new(temp.path(), String::new()).unwrap();
    edit(
        temp.path(),
        1,
        json!({"order":["p1","待补😀"],"pages":[{"id":"p1","content":{"title":"Decision"}},{"id":"待补😀"}]}),
    );
    let svg = temp.path().join("page.svg");
    let font = Command::new("fc-match")
        .args(["-f", "%{family}", "sans-serif"])
        .output()
        .unwrap();
    assert!(font.status.success());
    let families = String::from_utf8(font.stdout).unwrap();
    let family = families.split(',').next().unwrap().trim();
    std::fs::write(&svg, format!(r#"<svg viewBox="0 0 1280 720"><text x="64" y="80" font-size="36" font-family="{family}" data-atom-id="atom:p1:title">Decision</text></svg>"#)).unwrap();
    let run = ops::run_start(temp.path(), "svg", &["p1".into()], None).unwrap();
    ops::run_result(
        temp.path(),
        run["runs"][0]["id"].as_i64().unwrap(),
        "p1",
        &svg,
    )
    .unwrap();
    let base = ops::get(temp.path(), None).unwrap()["version"]
        .as_i64()
        .unwrap();
    edit(
        temp.path(),
        base,
        json!({"pages":[{"id":"p1","content":{"title":"Changed"}}]}),
    );
    let service = Service::start(temp.path());
    let build = service.request("POST", "/api/build", &[], "");
    assert_eq!(
        build.status,
        200,
        "{}",
        String::from_utf8_lossy(&build.body)
    );
    assert_eq!(build.json()["missing_pages"], json!(["待补😀"]));
    assert_eq!(build.json()["stale_pages"], json!(["p1"]));
    assert!(build.json().get("path").is_none());
    let downloaded = service.request("GET", build.json()["url"].as_str().unwrap(), &[], "");
    assert_eq!(downloaded.status, 200);
    assert!(downloaded.body.starts_with(b"PK"));
    assert_eq!(downloaded.artifact_status()["stale_pages"], json!(["p1"]));
    let base = ops::get(temp.path(), None).unwrap()["version"]
        .as_i64()
        .unwrap();
    edit(
        temp.path(),
        base,
        json!({"pages":[{"id":"p1","notes":"Changed notes"}]}),
    );
    let exported = service.request("GET", "/api/export/pptx", &[], "");
    assert_eq!(exported.status, 200);
    assert_eq!(exported.body, downloaded.body);
    assert_eq!(exported.artifact_status()["input_changed"], true);
    assert_eq!(
        exported.artifact_status()["missing_pages"],
        json!(["待补😀"])
    );
    assert_eq!(exported.artifact_status()["stale_pages"], json!(["p1"]));
    let markdown = service.request("GET", "/api/export/md", &[], "");
    assert_eq!(markdown.status, 200);
    assert_eq!(
        markdown.artifact_status()["missing_pages"],
        json!(["待补😀"])
    );
}
