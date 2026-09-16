"""Explicit-runtime, SVG-derived native presentation compiler."""
from dataclasses import dataclass
from pathlib import Path
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
    node_executable: str
    artifact_module: str
    width_px: float = 960
    height_px: float = 720
    timeout_seconds: int = 120

@dataclass(frozen=True)
class CompileResult:
    pptx_path: Path
    manifest_path: Path

def compile_deck(inputs: list[SvgInput], options: CompileOptions, output_dir: Path) -> CompileResult:
    if not inputs:
        raise ValueError('At least one SVG is required')
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / 'deck.pptx'
    if target.exists():
        raise FileExistsError(target)
    pages = []
    for item in inputs:
        data = Path(item.path).read_bytes()
        page = parse_svg(data, page_id=item.page_id)
        if abs(page['width']/page['height'] - options.width_px/options.height_px) > 1e-6:
            raise ValueError(f'{item.page_id}: SVG and slide aspect ratios differ')
        page['sha256'] = hashlib.sha256(data).hexdigest()
        pages.append(page)
    manifest = output_dir / 'compile-input.json'
    manifest.write_text(json.dumps({'pages': pages, 'width': options.width_px, 'height': options.height_px}, ensure_ascii=False, indent=2))
    script = Path(__file__).parents[1] / 'resources' / 'compiler' / 'native.mjs'
    with tempfile.TemporaryDirectory(prefix='compile-', dir=output_dir) as temporary:
        candidate = Path(temporary) / 'candidate.pptx'
        subprocess.run([options.node_executable, str(script), options.artifact_module, str(manifest), str(candidate)], check=True, timeout=options.timeout_seconds)
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
                                props.set('spc', str(round(spacing[name] * options.width_px / page['width'] * 75)))
                    data = ET.tostring(root, encoding='utf-8', xml_declaration=True)
                dest.writestr(info, data)
        # Never publish a partially exported package.
        patched.rename(target)
    return CompileResult(target, manifest)
