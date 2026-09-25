"""PEP 517 build hook: copy the sole editable Host Skill into build output."""
from pathlib import Path
import shutil
from setuptools.command.build_py import build_py

class BuildPy(build_py):
    def run(self):
        super().run()
        root=Path(__file__).resolve().parents[1]
        source=root/'skills'/'deck-master'
        target=Path(self.build_lib)/'deck_master'/'resources'/'skill'
        if not (source/'SKILL.md').is_file():
            raise RuntimeError('missing unique deck-master Skill source')
        # build output only; never create a second source copy in src/.
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)
        shutil.copyfile(source/'SKILL.md',target/'SKILL.md')
        for name in ('references','agents'):
            if (source/name).is_dir():
                shutil.copytree(source/name,target/name)
