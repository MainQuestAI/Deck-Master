"""Normal PEP 517 builds include the unique Host Skill source."""
from pathlib import Path
import runpy
from setuptools import setup
commands = runpy.run_path(str(Path(__file__).parent/'tools'/'build_hook.py'))
setup(cmdclass={'build_py': commands['BuildPy'], 'sdist': commands['Sdist']})
