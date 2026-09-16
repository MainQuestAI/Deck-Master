"""Pure SVG-to-native-slide entrypoint (current single-page subset)."""
from .api import CompileOptions, CompileResult, SvgInput, compile_deck

__all__ = ['CompileOptions', 'CompileResult', 'SvgInput', 'compile_deck']
