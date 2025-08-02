"""Backward compatibility shim: keep old 'monitor' import working."""

from app.main import (
    run_monitor_once,  # re-export for scheduler tests
    run_once,
    main,
)

__all__ = ["run_monitor_once", "run_once", "main"]
