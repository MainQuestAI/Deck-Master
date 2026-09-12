"""SC-1.1 ND-01 compatibility shim: single implementation lives in native_pptx.visibility."""

import sys as _sys

import native_pptx.visibility as _impl

_sys.modules[__name__] = _impl
