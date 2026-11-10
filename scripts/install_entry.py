"""Remember only verified legacy entries while their links are being replaced."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path


def identity(path: Path) -> list[int]:
    entry = path.lstat()
    return [entry.st_dev, entry.st_ino]


def link_state(path: Path) -> dict:
    if not path.is_symlink():
        raise ValueError("不是软链接")
    return {"identity": identity(path), "target": os.readlink(path)}


def snapshot(path: Path, action: str) -> dict:
    if action == "replace":
        return link_state(path)
    if path.is_symlink() or not path.is_dir():
        raise ValueError("不是原包装目录")
    return {
        "identity": identity(path),
        "links": {entry.name: link_state(entry) for entry in path.iterdir()},
    }


def matches(path: Path, receipt: dict) -> bool:
    actual = snapshot(path, receipt["action"])
    if actual["identity"] != receipt["entry"]["identity"]:
        return False
    if receipt["action"] == "replace":
        return actual == receipt["entry"]
    expected = receipt["entry"]["links"]
    return all(name in expected and link == expected[name] for name, link in actual["links"].items())


def main() -> None:
    mode, prefix_arg, path_arg, role, source_arg, legacy_arg, action = sys.argv[1:]
    prefix = Path(prefix_arg).resolve()
    # Resolve the containing directory, never the entry being replaced.
    path = Path(path_arg).parent.resolve() / Path(path_arg).name
    key = hashlib.sha256(os.fsencode(path)).hexdigest()
    directory = prefix / "share/deck/entry-migrations"
    if directory.is_symlink():
        raise ValueError("迁移凭据目录不能是软链接")
    receipt_path = directory / f"{key}.json"
    receipt = None
    if receipt_path.exists() or receipt_path.is_symlink():
        if not stat.S_ISREG(receipt_path.lstat().st_mode):
            raise ValueError("迁移凭据不是普通文件")
        receipt = json.loads(receipt_path.read_text())
        if (receipt["path"] != str(path) or receipt["prefix"] != str(prefix)
                or receipt["action"] not in ("replace", "upgrade")):
            raise ValueError("迁移凭据与入口不符")
    if mode == "clear":
        if receipt is not None:
            receipt_path.unlink()
        return
    if mode == "check":
        if receipt is None or not matches(path, receipt):
            raise ValueError("入口已变动或没有迁移凭据")
        print(receipt["action"])
        return
    if mode != "record":
        raise ValueError("未知迁移操作")
    if receipt is not None:
        if not matches(path, receipt) or receipt["action"] != action:
            raise ValueError("入口与迁移凭据不符")
        return
    entry = snapshot(path, action)
    sources = [Path(source_arg)]
    if legacy_arg:
        sources.append(Path(legacy_arg) / "deck-skill")
    if action == "replace":
        allowed = [source if role == "deck" else source / role for source in sources]
        valid = path.resolve() in [target.resolve() for target in allowed]
    else:
        valid = set(entry["links"]) == {"SKILL.md", "references", "assets"} and any(
            (path / "SKILL.md").resolve() in (
                (source / f"{role}.md").resolve(), (source / role / "SKILL.md").resolve()
            ) and all((path / name).resolve() == (source / name).resolve() for name in ("references", "assets"))
            for source in sources
        )
    if not valid:
        raise ValueError("入口不是已确认的旧安装")
    receipt = {"prefix": str(prefix), "path": str(path), "action": action, "entry": entry}
    directory.mkdir(parents=True, exist_ok=True)
    # A partial write must never become proof for a later retry.
    with tempfile.NamedTemporaryFile(mode="w", dir=directory, delete=False) as output:
        temporary = Path(output.name)
        json.dump(receipt, output)
        output.flush()
        os.fsync(output.fileno())
    try:
        os.replace(temporary, receipt_path)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, TypeError) as error:
        if sys.argv[1] == "check":
            raise SystemExit(1)
        print(f"install.sh: 入口迁移凭据检查失败：{error}；未继续清理入口。", file=sys.stderr)
        raise SystemExit(2)
