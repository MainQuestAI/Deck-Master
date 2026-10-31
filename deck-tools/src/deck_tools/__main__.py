"""JSON subprocess entrypoint. Files are inputs; no project state is opened."""

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from .errors import SourceUnreadable
from .sources import read_source


def main():
    parser = argparse.ArgumentParser(description="Deck 文件工具")
    parser.add_argument("command", choices=["read-source"], help="读取材料")
    parser.add_argument("job", type=Path, help="包含 path 的 JSON 文件")
    args = parser.parse_args()
    try:
        job = json.loads(args.job.read_text(encoding="utf-8"))
        path = Path(job["path"])
        result = asdict(read_source(path))
        print(json.dumps(result, ensure_ascii=False))
    except SourceUnreadable as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError,
            subprocess.TimeoutExpired) as exc:
        print(f"读取材料失败：{exc}；请检查输入文件后重试", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
