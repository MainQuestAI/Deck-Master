"""Explicit-runtime, SVG-derived native presentation compiler."""
from dataclasses import dataclass, field
from pathlib import Path
import math
import hashlib
import json
import subprocess
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from .svg import parse_svg

@dataclass(frozen=True)
class SvgInput:
    page_id: str
    path: Path

@dataclass(frozen=True)
class CompileOptions:
    node_executable: str | None = None
    artifact_module: str | None = None
    width_px: float = 1280
    height_px: float = 720
    fonts: dict[str, str] = field(default_factory=dict)
    assets: dict[str, dict[str, str]] = field(default_factory=dict)
    timeout_seconds: int = 120

@dataclass(frozen=True)
class CompileResult:
    """Real compile output. ``manifest_path`` doubles as the object trace: the
    compile-input JSON records every page IR, font and input digest used."""

    pptx_path: Path
    manifest_path: Path
    diagnostics: tuple[dict, ...] = ()

def compile_deck(inputs: list[SvgInput], options: CompileOptions, output_dir: Path) -> CompileResult:
    if not inputs:
        raise ValueError('At least one SVG is required')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    target = output_dir / 'deck.pptx'
    if target.exists():
        raise FileExistsError(target)
    if not all(math.isfinite(v) and v > 0 for v in (options.width_px, options.height_px)):
        raise ValueError("slide dimensions must be positive")
    asset_hashes = {path: hashlib.sha256(Path(path).read_bytes()).hexdigest() for mapping in options.assets.values() for path in mapping.values()}
    pages = []
    for item in inputs:
        data = Path(item.path).read_bytes()
        page = parse_svg(data, page_id=item.page_id, assets=options.assets.get(item.page_id, {}))
        page['sha256'] = hashlib.sha256(data).hexdigest()
        pages.append(page)
    diagnostics = []
    for page in pages:
        scale = min(options.width_px / page['width'], options.height_px / page['height'])
        horizontal = (options.width_px - scale * page['width']) / 2
        vertical = (options.height_px - scale * page['height']) / 2
        if max(horizontal, vertical) > .01:
            diagnostics.append({'page_id': page['page_id'], 'code': 'contained_with_letterbox', 'scale': scale, 'horizontal_margin_px': horizontal, 'vertical_margin_px': vertical})
    manifest = output_dir / 'compile-input.json'
    manifest.write_text(json.dumps({'pages': pages, 'width': options.width_px, 'height': options.height_px, 'diagnostics': diagnostics, 'compiler_version': 'python-native-v1', 'fonts': {k: {'sha256': hashlib.sha256(Path(v).read_bytes()).hexdigest()} for k,v in options.fonts.items()}}, ensure_ascii=False, indent=2))
    script = Path(__file__).parents[1] / 'resources' / 'compiler' / 'native.mjs'
    with tempfile.TemporaryDirectory(prefix='compile-', dir=output_dir) as temporary:
        candidate = Path(temporary) / 'candidate.pptx'
        if options.node_executable:
            subprocess.run([options.node_executable, str(script), options.artifact_module, str(manifest), str(candidate)], check=True, timeout=options.timeout_seconds)
        else:
            from .native import emit
            emit(pages, options.width_px, options.height_px, options.fonts, candidate)
        # Explicit SVG letter spacing becomes editable DrawingML character spacing.
        patched = Path(temporary) / 'patched.pptx'
        ns = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main', 'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
        with zipfile.ZipFile(candidate) as source, zipfile.ZipFile(patched, 'w', zipfile.ZIP_DEFLATED) as dest:
            for info in source.infolist():
                data = source.read(info.filename)
                for index, page in enumerate(pages, 1):
                    if info.filename != f'ppt/slides/slide{index}.xml':
                        continue
                    root = ET.fromstring(data)
                    spacing = {s['atom_id'] or s['id']: s.get('letter_spacing', 0) for s in page['shapes'] if s['kind'] == 'text'}
                    for shape in root.findall('.//p:sp', ns):
                        name = shape.find('p:nvSpPr/p:cNvPr', ns).get('name')
                        if spacing.get(name):
                            for props in shape.findall('.//a:rPr', ns) + shape.findall('.//a:defRPr', ns):
                                props.set('spc', str(round(spacing[name] * min(options.width_px / page['width'], options.height_px / page['height']) * 75)))
                    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
                dest.writestr(info, data)
        for item, page in zip(inputs, pages):
            if hashlib.sha256(Path(item.path).read_bytes()).hexdigest() != page['sha256']:
                raise ValueError(f'{item.page_id}: input changed during compilation')
        for path, digest in asset_hashes.items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
                raise ValueError('approved asset changed during compilation')
        # Exclusive publication also protects against a competing output writer.
        import os
        os.link(patched, target)
    return CompileResult(target, manifest, tuple(diagnostics))
