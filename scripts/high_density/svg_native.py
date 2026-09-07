"""SC-1.1 ND-01 compatibility shim: single implementation lives in native_pptx.svg_native."""

import sys as _sys

import native_pptx.svg_native as _impl

_sys.modules[__name__] = _impl
