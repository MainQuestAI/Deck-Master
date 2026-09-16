"""Normal PEP 517 builds include the unique Host Skill source."""
from pathlib import Path
import runpy
from setuptools import setup
BuildPy=runpy.run_path(str(Path(__file__).parent/'tools'/'build_hook.py'))['BuildPy']
setup(cmdclass={'build_py':BuildPy})
