"""Namespace shim so that outer 'rakuten' behaves as a namespace package."""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)

# Inner folder (.../rakuten/rakuten) を検索パスへ追加
import pathlib as _pl

_inner = _pl.Path(__file__).resolve().parent / "rakuten"
if _inner.is_dir() and str(_inner) not in __path__:
    __path__.append(str(_inner))
