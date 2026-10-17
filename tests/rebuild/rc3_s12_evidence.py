"""S12 test evidence only: full commands/SDK observations, no secret export."""
import functools
import hashlib
import json
import os
import subprocess
import traceback
from datetime import datetime, timezone
from pathlib import Path


def utc():
    return datetime.now(timezone.utc).isoformat()


def serial(value):
    if isinstance(value, bytes):
        return {"bytes": len(value), "sha256": hashlib.sha256(value).hexdigest(), "utf8": value.decode(errors="replace")}
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): serial(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [serial(v) for v in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "project_root"):
        return {"actual_Store_project": str(value.project_root)}
    # Do not serialize internals of protected contexts/providers.
    return {"type": type(value).__name__, "repr": str(value)}


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.open("x").write(json.dumps(serial(value), ensure_ascii=False, indent=2) + "\n")


def logged_command(root, name, argv, *, cwd, env=None, timeout=300):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    intent = {"argv": list(map(str, argv)), "cwd": str(cwd), "start_UTC": utc()}
    save(root / (name + ".intent.json"), intent)
    result = None
    stdout, stderr = b"", b""
    failure = None
    try:
        result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=timeout, check=False)
        stdout, stderr = result.stdout, result.stderr
        return result
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        failure = {"type": type(exc).__name__, "message": str(exc)}
        raise
    except BaseException as exc:
        failure = {"type": type(exc).__name__, "message": str(exc)}
        raise
    finally:
        (root / (name + ".stdout.txt")).open("xb").write(stdout)
        (root / (name + ".stderr.txt")).open("xb").write(stderr)
        save(root / (name + ".outcome.json"), {**intent, "end_UTC": utc(),
            "exit": result.returncode if result is not None else None, "execution_error": failure})


class Recorder:
    def __init__(self, root):
        self.root = Path(root)
        self.count = 0

    def wrap(self, module, names):
        for name in names:
            original = getattr(module, name)
            label = module.__name__ + "." + name

            @functools.wraps(original)
            def wrapped(*args, _original=original, _label=label, **kwargs):
                self.count += 1
                number = self.count
                intent = {"operation": _label, "args": serial(args), "kwargs": serial(kwargs), "start_UTC": utc()}
                save(self.root / f"function-{number:04d}.intent.json", intent)
                try:
                    result = _original(*args, **kwargs)
                except BaseException as exc:
                    save(self.root / f"function-{number:04d}.outcome.json", {**intent, "end_UTC": utc(),
                        "error": {"type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc()}})
                    raise
                save(self.root / f"function-{number:04d}.outcome.json", {**intent, "end_UTC": utc(), "result": result})
                return result
            setattr(module, name, wrapped)


def publish_workspace(working, output):
    """Only controlled new neutral projects. Never enumerate the IG key root.

    First prune every 'ig' directory. Then copy only its explicit public
    files/directories. No auth-key file is opened, hashed, listed or uploaded.
    """
    working, output = Path(working), Path(output)
    manifest = []
    if not working.exists():
        return manifest

    def copy_one(source, relative):
        if source.is_symlink() or not source.is_file():
            return
        raw = source.read_bytes()
        dest = output / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists():
            if dest.read_bytes() != raw:
                raise ValueError("evidence copy changed: " + str(relative))
        else:
            dest.open("xb").write(raw)
        manifest.append({"path": str(relative), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})

    for current, dirs, files in os.walk(working, topdown=True, followlinks=False):
        dirs[:] = [d for d in dirs if d not in {"ig", "__pycache__"} and not (Path(current) / d).is_symlink()]
        for name in files:
            source = Path(current) / name
            copy_one(source, source.relative_to(working))
    for scenario in ("positive", "unknown", "bad-callback", "grant-lost-ack", "grant-durable", "role-overrun"):
        ledger = working / scenario / "ig"
        for name in ("event-registration.json", "event-origin.json", "event-legacy-frontier.json",
                     "m02-read-runtime-transition.json", "m02-read-transition-origin.json"):
            copy_one(ledger / name, Path(scenario) / "ig" / name)
        for name in ("dispatches", "event-dispatches", "event-calls", "m02-read-transition-journal"):
            directory = ledger / name
            if directory.exists():
                for current, dirs, files in os.walk(directory, topdown=True, followlinks=False):
                    dirs[:] = [d for d in dirs if not (Path(current) / d).is_symlink()]
                    for filename in files:
                        source = Path(current) / filename
                        copy_one(source, Path(scenario) / "ig" / source.relative_to(ledger))
    return manifest

