"""Thin legacy shim: setuptools builds the src-layout package via pyproject.toml.

Kept because T05's target list includes it; the isolated build reads packaging
config from pyproject.toml, and tools/build_hook.py syncs Skill method
resources into the package before building (single Skill source in the repo).
"""

from setuptools import setup

setup()
