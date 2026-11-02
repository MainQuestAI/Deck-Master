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
from .atoms import visible_atoms
from .doctor import diagnose
from .jobs import compile_job, projection
from .render import NeedsTool, RendererError
from .sanitize import sanitize, OperationError
from .compiler.svg import SvgError


def main():
    parser = argparse.ArgumentParser(description="Deck 文件工具")
    parser.add_argument("command", choices=["read-source", "atoms", "check-page", "build", "sanitize", "doctor", "image-info"], help="读取材料")
    parser.add_argument("job", type=Path, help="包含 path 的 JSON 文件")
    args = parser.parse_args()
    try:
        job = json.loads(args.job.read_text(encoding="utf-8"))
        if args.command == "read-source":
            result = asdict(read_source(Path(job["path"])))
        elif args.command == "image-info":
            from PIL import Image
            with Image.open(job["path"]) as image:
                if image.format not in ("PNG", "JPEG"):
                    raise ValueError("生图文件必须是 PNG 或 JPEG")
                result = {"format": image.format, "width": image.width, "height": image.height}
                image.verify()
        elif args.command == "atoms":
            result = visible_atoms(projection(job["page"]))
        elif args.command == "doctor":
            result = diagnose(job.get("fonts", []))
        elif args.command == "sanitize":
            path = Path(job["path"])
            output = Path(job["output"])
            cleaned = sanitize(path.read_bytes(), path.suffix, path.name,
                               preserve_notes=job.get("preserve_notes", False))
            with output.open("xb") as stream:
                stream.write(cleaned)
            result = {"path": str(output)}
        else:
            result = compile_job(job, preview=args.command == "check-page")
        print(json.dumps(result, ensure_ascii=False))
    except NeedsTool as exc:
        print(f"缺少生产工具：{exc}；请安装工具或字体后重试", file=sys.stderr)
        return 3
    except (RendererError, OperationError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"生产工具失败：{exc}；请修正输入或工具配置后重试", file=sys.stderr)
        return 4
    except SvgError as exc:
        print(json.dumps(exc.diagnostic, ensure_ascii=False), file=sys.stderr)
        return 4
    except SourceUnreadable as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    except (OSError, ValueError, KeyError, TypeError, ET.ParseError,
            subprocess.TimeoutExpired) as exc:
        print(f"文件工具失败：{exc}；请检查输入文件后重试", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
