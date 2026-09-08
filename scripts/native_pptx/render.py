"""Run-independent LibreOffice/Poppler renderer with bounded execution."""
from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image
from pptx import Presentation

from .contracts import sha256_file


class RenderError(RuntimeError):
    def __init__(self, message: str, code: str = 'NDC_RENDER_FAILED') -> None:
        self.code = code
        super().__init__(message)


def render_deck(pptx: Path, page_ids: list[str], output_root: Path, *, timeout_seconds: float = 120, dpi: int = 144) -> dict[str, Any]:
    """Render a whole deck. Publish only after the exact page set decodes.

    The caller owns an immutable revision output directory. Reusing an
    existing output filename is refused so failed retries preserve evidence.
    """
    pptx = Path(pptx).resolve()
    output_root = Path(output_root).resolve()
    if not (0 < timeout_seconds <= 600) or not (36 <= dpi <= 600):
        raise RenderError('renderer timeout/dpi is outside supported bounds')
    if not page_ids or len(set(page_ids)) != len(page_ids) or any(not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', page_id) for page_id in page_ids):
        raise RenderError('renderer requires a unique, safe, nonempty page set')
    try:
        actual_pages = len(Presentation(pptx).slides)
    except Exception as exc:
        raise RenderError('PPTX cannot be opened for rendering') from exc
    if actual_pages != len(page_ids):
        raise RenderError('PPTX slide count does not match the declared page set')
    soffice, pdftoppm = shutil.which('soffice'), shutil.which('pdftoppm')
    if not soffice or not pdftoppm:
        raise RenderError('soffice and pdftoppm are required for native rendering', 'NDC_RENDERER_UNAVAILABLE')
    destinations = [output_root / f'{page_id}.png' for page_id in page_ids] + [output_root / 'deck.pdf']
    if any(path.exists() for path in destinations):
        raise RenderError('render output already exists; use a fresh revision output directory')
    try:
        with tempfile.TemporaryDirectory(prefix='deck-master-native-render-') as directory:
            temp = Path(directory)
            profile = temp / 'lo-profile'
            profile.mkdir()
            commands = [
                [soffice, f'-env:UserInstallation={profile.as_uri()}', '--headless', '--nologo', '--nodefault', '--nofirststartwizard', '--convert-to', 'pdf', '--outdir', str(temp), str(pptx)],
                [pdftoppm, '-png', '-r', str(dpi), str(temp / f'{pptx.stem}.pdf'), str(temp / 'page')],
            ]
            for command in commands:
                result = subprocess.run(command, capture_output=True, text=True, timeout=timeout_seconds)
                if result.returncode:
                    raise RenderError(f'{Path(command[0]).name} failed: {result.stderr.strip() or result.stdout.strip()}')
                if command is commands[0] and not (temp / f'{pptx.stem}.pdf').is_file():
                    raise RenderError('LibreOffice completed without producing a PDF')
            numbered: dict[int, Path] = {}
            for path in temp.glob('page-*.png'):
                match = re.fullmatch(r'page-(\d+)\.png', path.name)
                if not match or int(match[1]) in numbered:
                    raise RenderError('renderer returned an ambiguous page set')
                numbered[int(match[1])] = path
            if set(numbered) != set(range(1, len(page_ids) + 1)):
                raise RenderError('renderer returned an incomplete or extra page set')
            staged = temp / 'validated'
            staged.mkdir()
            for index, page_id in enumerate(page_ids, 1):
                with Image.open(numbered[index]) as image:
                    image.load()
                    if image.width <= 0 or image.height <= 0:
                        raise RenderError('renderer produced an empty page')
                    image.convert('RGB').save(staged / f'{page_id}.png', format='PNG')
            shutil.copyfile(temp / f'{pptx.stem}.pdf', staged / 'deck.pdf')
            output_root.mkdir(parents=True, exist_ok=True)
            for destination in destinations:
                # Exclusive creation also protects against concurrent retries.
                with destination.open('xb') as stream:
                    stream.write((staged / destination.name).read_bytes())
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f'native render timed out after {timeout_seconds:g}s', 'NDC_RENDER_TIMEOUT') from exc
    except (OSError, ValueError) as exc:
        raise RenderError(f'native render failed: {exc}') from exc
    return {
        'schema_version': 'deck_native_render.v1', 'status': 'rendered',
        'pptx_sha256': sha256_file(pptx), 'pdf_path': str(output_root / 'deck.pdf'),
        'pdf_sha256': sha256_file(output_root / 'deck.pdf'),
        'pages': [{'page_id': page_id, 'order': index, 'path': str(output_root / f'{page_id}.png'), 'sha256': sha256_file(output_root / f'{page_id}.png')} for index, page_id in enumerate(page_ids, 1)],
        'renderer': {'pptx_to_pdf': 'soffice', 'pdf_to_png': 'pdftoppm', 'dpi': dpi, 'isolated_profile': True},
    }
