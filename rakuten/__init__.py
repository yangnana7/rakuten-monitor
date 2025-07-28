"""Namespace shim so that outer 'rakuten' behaves as a namespace package."""
from pkgutil import extend_path
__path__ = extend_path(__path__, __name__)
