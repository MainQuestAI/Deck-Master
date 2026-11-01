use deck::{
    model::{Artifact, Patch},
    ops,
    store::{self, Store},
};
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
    assert_eq!(
        service
            .request("PUT", "/api/deck?base=1", &[], r#"{"deck":{}}"#)
            .status,
        400
    );
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
    assert_eq!(service.request("POST", "/api/reviews", &[], "").status, 400);
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
    std::fs::remove_file(first.path().join(".deck/files").join(&local)).unwrap();
    let missing = service.request("GET", &format!("/api/files/{}", &local[..64]), &[], "");
    assert_eq!(missing.status, 404);
    assert!(missing.json().get("exit_code").is_none());
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
        std::fs::remove_file(second.path().join(".deck/files").join(&foreign)).unwrap();
        assert_eq!(
            service
                .request("GET", &format!("/api/files/{}", &foreign[..64]), &[], "")
                .status,
            404
        );
    }
}

#[test]
fn jpeg_result_named_png_downloads_as_jpeg() {
    let temp = tempfile::tempdir().unwrap();
    ops::new(temp.path(), String::new()).unwrap();
    edit(
        temp.path(),
        1,
        json!({"order":["p1"],"pages":[{"id":"p1"}]}),
    );
    let bitmap = temp.path().join("result.png");
    let python = std::env::var_os("DECK_TOOLS_PYTHON").expect("install this worktree's deck-tools");
    assert!(
        Command::new(python)
            .args([
                "-c",
                "from PIL import Image; import sys; Image.new('RGB',(8,8)).save(sys.argv[1],format='JPEG')"
            ])
            .arg(&bitmap)
            .status()
            .unwrap()
            .success()
    );
    let run = ops::run_start(temp.path(), "image", &["p1".into()], None).unwrap();
    let id = run["runs"][0]["id"].as_i64().unwrap();
    ops::run_call(temp.path(), id, "p1", false).unwrap();
    let result = ops::run_result(temp.path(), id, "p1", &bitmap).unwrap();
    let file = result["file"].as_str().unwrap();
    assert!(file.ends_with(".jpg"));
    let service = Service::start(temp.path());
    let downloaded = service.request("GET", &format!("/api/files/{}", &file[..64]), &[], "");
    assert_eq!(downloaded.status, 200);
    assert_eq!(downloaded.headers["content-type"], "image/jpeg");
    assert_eq!(downloaded.body, std::fs::read(bitmap).unwrap());
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
    let mut store = Store::open(temp.path()).unwrap();
    let mut snapshot = store.current().unwrap();
    let font = Command::new("fc-match")
        .args(["-f", "%{family}", "sans-serif"])
        .output()
        .unwrap();
    assert!(font.status.success());
    let families = String::from_utf8(font.stdout).unwrap();
    let family = families.split(',').next().unwrap().trim();
    let svg = format!(
        r#"<svg viewBox="0 0 1280 720"><text x="64" y="80" font-size="36" font-family="{family}" data-atom-id="atom:p1:title">Decision</text></svg>"#
    );
    let file = store.add_file(svg.as_bytes(), "svg").unwrap();
    let basis = ops::basis("svg", &snapshot.deck, &snapshot.deck.pages[0]).unwrap();
    snapshot.deck.pages[0].svg = Some(Artifact { file, basis });
    let tx = store.transaction().unwrap();
    let base = store::append(&tx, &snapshot.deck, "synthetic compiler fixture").unwrap();
    tx.commit().unwrap();
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

#[test]
fn http_reviews_force_human_filter_resolve_and_poll_without_changing_version() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, String::new()).unwrap();
    edit(
        path,
        1,
        json!({"order":["p3","页 4"],"pages":[{"id":"p3"},{"id":"页 4"}]}),
    );
    let checked = ops::review_add(path, Some("p3"), "自检原文", "Host", "self_check").unwrap();
    let service = Service::start(path);
    let posted = service.request(
        "POST",
        "/api/reviews",
        &[],
        r#"{"page_id":"p3","text":"收入 100 元 , 复核","reviewer":"editor","method":"self_check"}"#,
    );
    assert_eq!(posted.status, 200);
    assert_eq!(posted.headers["cache-control"], "no-store");
    assert_eq!(posted.headers["x-content-type-options"], "nosniff");
    assert_eq!(posted.json()["method"], "human");
    assert_eq!(posted.json()["reviewer"], "editor");
    assert_eq!(posted.json()["text"], "收入 100 元 , 复核");
    let global = service
        .request("POST", "/api/reviews", &[], r#"{"text":"全稿"}"#)
        .json();
    assert_eq!(global["method"], "human");
    assert_eq!(global["reviewer"], "author");
    assert_eq!(global["page_id"], Value::Null);
    let unicode = service
        .request(
            "POST",
            "/api/reviews",
            &[],
            r#"{"page_id":"页 4","text":"另页"}"#,
        )
        .json();
    assert_eq!(
        service
            .request("GET", "/api/reviews?page=%E9%A1%B5+4&status=open", &[], "")
            .json()["reviews"],
        json!([unicode])
    );
    let filtered = service.request("GET", "/api/reviews?status=open&page=p3", &[], "");
    assert_eq!(filtered.status, 200);
    assert_eq!(filtered.json()["reviews"], json!([checked, posted.json()]));
    let workspace = service.request("GET", "/api/deck", &[], "").json();
    assert_eq!(workspace["reviews"].as_array().unwrap().len(), 4);
    assert_eq!(workspace["reviews"][0]["method"], "self_check");
    assert_eq!(workspace["deck"]["pages"][0]["open_reviews"], 2);
    assert_eq!(workspace["deck"]["pages"][1]["open_reviews"], 1);
    assert_eq!(workspace["open_reviews_total"], 4);
    assert_eq!(workspace["version"], 2);
    let url = format!("/api/reviews/{}/resolve", checked.id);
    let resolved = service.request("POST", &url, &[], "");
    assert_eq!(resolved.status, 200);
    assert_eq!(resolved.json()["id"], checked.id);
    assert_eq!(resolved.json()["status"], "resolved");
    assert!(resolved.json()["resolved_at"].is_string());
    assert_eq!(
        service.request("POST", &url, &[], "").json(),
        resolved.json()
    );
    assert_eq!(
        service
            .request("GET", "/api/reviews?status=resolved&page=p3", &[], "")
            .json()["reviews"],
        json!([resolved.json()])
    );
    assert_eq!(
        service.request("GET", "/api/deck", &[], "").json()["deck"]["pages"][0]["open_reviews"],
        1
    );
    assert_eq!(
        service
            .request("GET", "/api/reviews?status=open&page=p3", &[], "")
            .json()["reviews"],
        json!([posted.json()])
    );
    for body in [
        r#"{"text":" "}"#,
        r#"{"text":"意见","page_id":"missing"}"#,
        r#"{}"#,
    ] {
        assert_eq!(
            service.request("POST", "/api/reviews", &[], body).status,
            400
        );
    }
    for url in [
        "/api/reviews?status=pass",
        "/api/reviews?page=%GG",
        "/api/reviews?page=%FF",
    ] {
        assert_eq!(service.request("GET", url, &[], "").status, 400);
    }
    for url in [
        "/api/reviews/resolve",
        "/api/reviews//resolve",
        "/api/reviews/no/resolve",
    ] {
        assert_eq!(service.request("POST", url, &[], "").status, 400);
    }
    assert_eq!(
        service
            .request("POST", "/api/reviews/999/resolve", &[], "")
            .status,
        404
    );
    for url in [
        "/api/reviews",
        "/api/reviews/2/resolve",
        "/api/runs/1/adopt/p3",
    ] {
        assert_eq!(
            service
                .request(
                    "POST",
                    url,
                    &[("Origin", "https://evil.example")],
                    r#"{"text":"attack"}"#
                )
                .status,
            403
        );
        assert_eq!(
            service
                .request("POST", url, &[("Host", "evil.example")], "")
                .status,
            403
        );
    }
    assert_eq!(ops::get(path, None).unwrap()["version"], 2);
}

#[test]
fn http_adopt_matches_cli_with_candidates_and_existing_rejection_semantics() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, String::new()).unwrap();
    edit(path, 1, json!({"order":["p3"],"pages":[{"id":"p3"}]}));
    let bitmap = path.join("candidate.png");
    let python = std::env::var_os("DECK_TOOLS_PYTHON").unwrap();
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
    let first = ops::run_start(path, "image", &["p3".into()], None).unwrap()["runs"][0]["id"]
        .as_i64()
        .unwrap();
    ops::run_call(path, first, "p3", false).unwrap();
    let first_result = ops::run_result(path, first, "p3", &bitmap).unwrap();
    let first_bytes = std::fs::read(&bitmap).unwrap();
    let id = ops::run_start(path, "image", &["p3".into()], None).unwrap()["runs"][0]["id"]
        .as_i64()
        .unwrap();
    let service = Service::start(path);
    let url = format!("/api/runs/{id}/adopt/p3");
    assert_eq!(service.request("POST", &url, &[], "").status, 400);
    ops::run_call(path, id, "p3", false).unwrap();
    let base = Store::open(path).unwrap().current().unwrap().version;
    edit(
        path,
        base,
        json!({"pages":[{"id":"p3","layout":"依据变化"}]}),
    );
    assert!(
        Command::new(std::env::var_os("DECK_TOOLS_PYTHON").unwrap())
            .args([
                "-c",
                "from PIL import Image; import sys; Image.new('RGB',(16,16),'navy').save(sys.argv[1])"
            ])
            .arg(&bitmap)
            .status()
            .unwrap()
            .success()
    );
    let result = ops::run_result(path, id, "p3", &bitmap).unwrap();
    assert_eq!(result["adopted"], false);
    let workspace = service.request("GET", "/api/deck", &[], "").json();
    assert_eq!(
        workspace["deck"]["pages"][0]["image"]["file"],
        first_result["file"]
    );
    assert_ne!(first_result["file"], result["file"]);
    let candidate = &workspace["runs"][0]["pages"][0];
    assert_eq!(candidate["status"], "unadopted");
    assert!(!candidate["reason"].as_str().unwrap().is_empty());
    assert_eq!(candidate["basis_changed"], true);
    let candidate_bytes = std::fs::read(&bitmap).unwrap();
    assert_ne!(candidate_bytes, first_bytes);
    for (key, expected) in [
        ("result_url", candidate_bytes),
        ("current_image_url", first_bytes),
    ] {
        let image = service.request("GET", candidate[key].as_str().unwrap(), &[], "");
        assert_eq!(image.status, 200);
        assert_eq!(image.body, expected);
        assert!(image.headers["content-security-policy"].contains("sandbox"));
    }
    let adopted = service.request("POST", &url, &[], "");
    assert_eq!(adopted.status, 200);
    let after = service.request("GET", "/api/deck", &[], "").json();
    assert_eq!(after["deck"]["pages"][0]["image"]["file"], result["file"]);
    assert_eq!(
        after["version"].as_i64().unwrap(),
        workspace["version"].as_i64().unwrap() + 1
    );
    assert_eq!(after["artifact_status"]["stale_images"], json!(["p3"]));
    let cli = Command::new(env!("CARGO_BIN_EXE_deck"))
        .arg("--project")
        .arg(path.canonicalize().unwrap())
        .args(["run", "adopt", &id.to_string(), "p3"])
        .output()
        .unwrap();
    assert!(cli.status.success());
    let mut cli: Value = serde_json::from_slice(&cli.stdout).unwrap();
    for page in cli["runs"][0]["pages"].as_array_mut().unwrap() {
        let page = page.as_object_mut().unwrap();
        assert!(page.remove("findings_path").is_some());
        assert!(page.remove("work").is_some());
    }
    assert_eq!(adopted.json(), cli);
    assert_eq!(adopted.json()["runs"][0], after["runs"][0]);
    assert_eq!(
        ops::get(path, None).unwrap()["artifact_status"]["stale_images"],
        json!(["p3"])
    );
    assert_eq!(
        service
            .request("POST", "/api/runs/999/adopt/p3", &[], "")
            .status,
        400
    );
    for url in [
        "/api/runs/no/adopt/p3",
        "/api/runs/1/adopt/",
        "/api/runs/1/adopt/%GG",
    ] {
        assert_eq!(service.request("POST", url, &[], "").status, 400);
    }
}

#[test]
fn http_adopts_cancelled_runs_late_result() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, String::new()).unwrap();
    edit(path, 1, json!({"order":["p3"],"pages":[{"id":"p3"}]}));
    let bitmap = path.join("late.png");
    assert!(
        Command::new(std::env::var_os("DECK_TOOLS_PYTHON").unwrap())
            .args([
                "-c",
                "from PIL import Image; import sys; Image.new('RGB',(8,8)).save(sys.argv[1])"
            ])
            .arg(&bitmap)
            .status()
            .unwrap()
            .success()
    );
    let id = ops::run_start(path, "image", &["p3".into()], None).unwrap()["runs"][0]["id"]
        .as_i64()
        .unwrap();
    ops::run_call(path, id, "p3", false).unwrap();
    let service = Service::start(path);
    assert_eq!(
        service
            .request("POST", &format!("/api/runs/{id}/cancel"), &[], "")
            .status,
        200
    );
    let result = ops::run_result(path, id, "p3", &bitmap).unwrap();
    assert_eq!(result["adopted"], false);
    let before = ops::workspace(path).unwrap();
    assert_eq!(before["runs"][0]["pages"][0]["status"], "unadopted");
    assert_eq!(before["deck"]["pages"][0]["image"], Value::Null);
    let reply = service.request("POST", &format!("/api/runs/{id}/adopt/p3"), &[], "");
    assert_eq!(reply.status, 200);
    assert_eq!(reply.json()["runs"][0]["status"], "cancelled");
    assert_eq!(reply.json()["runs"][0]["pages"][0]["status"], "done");
    let after = ops::workspace(path).unwrap();
    assert_eq!(after["deck"]["pages"][0]["image"]["file"], result["file"]);
    assert_eq!(
        after["version"].as_i64().unwrap(),
        before["version"].as_i64().unwrap() + 1
    );
}

#[test]
fn http_adopts_only_selected_page_of_two_page_run() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, String::new()).unwrap();
    edit(
        path,
        1,
        json!({"order":["p1","p2"],"pages":[{"id":"p1"},{"id":"p2"}]}),
    );
    let bitmap = path.join("current.png");
    assert!(
        Command::new(std::env::var_os("DECK_TOOLS_PYTHON").unwrap())
            .args([
                "-c",
                "from PIL import Image; import sys; Image.new('RGB',(8,8)).save(sys.argv[1])"
            ])
            .arg(&bitmap)
            .status()
            .unwrap()
            .success()
    );
    let pages = ["p1".into(), "p2".into()];
    let first = ops::run_start(path, "image", &pages, None).unwrap()["runs"][0]["id"]
        .as_i64()
        .unwrap();
    for page in &pages {
        ops::run_call(path, first, page, false).unwrap();
        assert_eq!(
            ops::run_result(path, first, page, &bitmap).unwrap()["adopted"],
            true
        );
    }
    let id = ops::run_start(path, "image", &pages, None).unwrap()["runs"][0]["id"]
        .as_i64()
        .unwrap();
    for page in &pages {
        ops::run_call(path, id, page, false).unwrap();
    }
    ops::run_cancel(path, id).unwrap();
    assert!(Command::new(std::env::var_os("DECK_TOOLS_PYTHON").unwrap())
        .args(["-c", "from PIL import Image; import sys; Image.new('RGB',(16,16),'navy').save(sys.argv[1])"])
        .arg(&bitmap).status().unwrap().success());
    for page in &pages {
        assert_eq!(
            ops::run_result(path, id, page, &bitmap).unwrap()["adopted"],
            false
        );
    }
    let before = ops::workspace(path).unwrap();
    let other = &before["runs"][0]["pages"][1];
    assert_eq!(other["page_id"], "p2");
    assert_eq!(other["status"], "unadopted");
    let store = Store::open(path).unwrap();
    let other_file = before["deck"]["pages"][1]["image"]["file"]
        .as_str()
        .unwrap();
    let other_bytes = std::fs::read(store.file(other_file).unwrap()).unwrap();
    let other_result = store.file(other["result_file"].as_str().unwrap()).unwrap();
    let other_result_bytes = std::fs::read(&other_result).unwrap();
    let service = Service::start(path);
    let reply = service.request("POST", &format!("/api/runs/{id}/adopt/p1"), &[], "");
    assert_eq!(reply.status, 200);
    assert_eq!(reply.json()["runs"][0]["pages"][0]["status"], "done");
    assert_eq!(reply.json()["runs"][0]["pages"][1], *other);
    let after = ops::workspace(path).unwrap();
    assert_eq!(
        after["deck"]["pages"][0]["image"]["file"],
        before["runs"][0]["pages"][0]["result_file"]
    );
    assert_ne!(
        after["deck"]["pages"][0]["image"]["file"],
        before["deck"]["pages"][0]["image"]["file"]
    );
    assert_eq!(after["deck"]["pages"][1], before["deck"]["pages"][1]);
    assert_eq!(
        std::fs::read(store.file(other_file).unwrap()).unwrap(),
        other_bytes
    );
    assert_eq!(std::fs::read(other_result).unwrap(), other_result_bytes);
}

#[test]
fn http_rejects_adoption_after_page_deleted() {
    let temp = tempfile::tempdir().unwrap();
    let path = temp.path();
    ops::new(path, String::new()).unwrap();
    edit(path, 1, json!({"order":["p3"],"pages":[{"id":"p3"}]}));
    let bitmap = path.join("candidate.png");
    assert!(
        Command::new(std::env::var_os("DECK_TOOLS_PYTHON").unwrap())
            .args([
                "-c",
                "from PIL import Image; import sys; Image.new('RGB',(8,8)).save(sys.argv[1])"
            ])
            .arg(&bitmap)
            .status()
            .unwrap()
            .success()
    );
    let id = ops::run_start(path, "image", &["p3".into()], None).unwrap()["runs"][0]["id"]
        .as_i64()
        .unwrap();
    ops::run_call(path, id, "p3", false).unwrap();
    ops::run_cancel(path, id).unwrap();
    assert_eq!(
        ops::run_result(path, id, "p3", &bitmap).unwrap()["adopted"],
        false
    );
    edit(path, 2, json!({"order":[],"pages":[{"id":"p3"}]}));
    let before = ops::workspace(path).unwrap();
    assert_eq!(before["deck"]["pages"], json!([]));
    let service = Service::start(path);
    assert_eq!(
        service
            .request("POST", &format!("/api/runs/{id}/adopt/p3"), &[], "")
            .status,
        400
    );
    assert_eq!(ops::workspace(path).unwrap(), before);
}
