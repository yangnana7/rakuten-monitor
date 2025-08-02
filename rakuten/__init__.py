"""Compatibility stubs for tests that still import 'rakuten.*'."""

import importlib
import pathlib as _pl
import sys
from pkgutil import extend_path
from types import ModuleType


def _alias(old: str, new: str) -> None:
    """Create alias for old module path to new module path."""
    module: ModuleType = importlib.import_module(new)
    sys.modules[old] = module


# Create aliases for moved modules
_alias("rakuten.discord_client", "app.notifier.discord")
_alias("rakuten.item_db", "app.db.sqlite_repo")


# Handle attribute access for compatibility
def __getattr__(name: str):
    """Handle attribute access for legacy module names."""
    if name == "discord_client":
        return importlib.import_module("app.notifier.discord")
    elif name == "item_db":
        return importlib.import_module("app.db.sqlite_repo")
    raise AttributeError(f"module 'rakuten' has no attribute '{name}'")


# Legacy namespace package support
__path__ = extend_path(__path__, __name__)

# Inner folder (.../rakuten/rakuten) を検索パスへ追加
_inner = _pl.Path(__file__).resolve().parent / "rakuten"
if _inner.is_dir() and str(_inner) not in __path__:
    __path__.append(str(_inner))
