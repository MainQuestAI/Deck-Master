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
from .sanitize import attach_hint_findings, sanitize, OperationError
from .compiler.svg import SvgError


def _normalize_image(job):
    from PIL import Image, ImageOps
    from .render import executable

    path = Path(job["path"])
    output = Path(job["output"])
    if job.get("svg"):
        rsvg = executable("rsvg-convert")
        completed = subprocess.run(
            [rsvg, "--format=png", str(path)],
            capture_output=True,
            check=False,
            timeout=120,
        )
        if completed.returncode != 0 or not completed.stdout.startswith(b"\x89PNG\r\n\x1a\n"):
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            raise RendererError(f"SVG 素材转 PNG 失败；请检查 SVG 后重新添加：{detail}")
        output.write_bytes(completed.stdout)
        try:
            with Image.open(output) as image:
                width, height = image.width, image.height
                image.verify()
        except Image.DecompressionBombError as exc:
            raise ValueError(f"图片像素超出安全上限：{exc}") from exc
        return {"path": str(output), "format": "PNG", "normalized": True, "width": width, "height": height}

    try:
        with Image.open(path) as image:
            fmt = image.format
            if fmt not in ("PNG", "JPEG"):
                raise ValueError("图片只支持 PNG 或 JPEG 格式")
            orientation = image.getexif().get(274, 1)
            if orientation != 1:
                transposed = ImageOps.exif_transpose(image)
                if fmt == "JPEG" and transposed.mode not in ("RGB", "L"):
                    transposed = transposed.convert("RGB")
                save_kwargs = {"quality": 95} if fmt == "JPEG" else {}
                transposed.save(output, format=fmt, **save_kwargs)
                width, height = transposed.width, transposed.height
                return {"path": str(output), "format": fmt, "normalized": True, "width": width, "height": height}
            width, height = image.width, image.height
            image.load()
            return {"path": str(path), "format": fmt, "normalized": False, "width": width, "height": height}
    except Image.DecompressionBombError as exc:
        raise ValueError(f"图片像素超出安全上限：{exc}") from exc


def main():
    parser = argparse.ArgumentParser(description="Deck 文件工具")
    parser.add_argument("command", choices=["read-source", "atoms", "check-page", "build", "sanitize", "doctor", "image-info", "normalize-image", "validate-plan", "crop", "render", "assemble"], help="读取材料")
    parser.add_argument("job", type=Path, help="包含 path 的 JSON 文件")
    args = parser.parse_args()
    try:
        job = json.loads(args.job.read_text(encoding="utf-8"))
        if args.command in ("validate-plan", "crop", "render", "assemble"):
            from .native import dispatch
            result = dispatch(args.command, job)
        elif args.command == "read-source":
            result = asdict(read_source(Path(job["path"])))
        elif args.command == "image-info":
            from PIL import Image
            try:
                with Image.open(job["path"]) as image:
                    if image.format not in ("PNG", "JPEG"):
                        raise ValueError("生图文件必须是 PNG 或 JPEG")
                    result = {"format": image.format, "width": image.width, "height": image.height}
                    image.verify()
            except Image.DecompressionBombError as exc:
                raise ValueError(f"图片像素超出安全上限：{exc}") from exc
        elif args.command == "normalize-image":
            result = _normalize_image(job)
        elif args.command == "atoms":
            result = visible_atoms(projection(job["page"]))
        elif args.command == "doctor":
            result = diagnose(job.get("fonts", []))
        elif args.command == "sanitize":
            path = Path(job["path"])
            output = Path(job["output"])
            found = []
            cleaned = sanitize(path.read_bytes(), path.suffix, path.name,
                               preserve_notes=job.get("preserve_notes", False),
                               findings=found)
            with output.open("xb") as stream:
                stream.write(cleaned)
            result = {"path": str(output)}
            if found:
                result["findings"] = attach_hint_findings(
                    {"status": "pass", "findings": []}, found)
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
