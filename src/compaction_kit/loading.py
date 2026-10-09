"""Load a compactor from a user-supplied import specification.

`compaction-kit check my_module:MyCompactor` and
`compaction-kit check ./my_compactor.py:MyCompactor` both work. The
loaded object may be a class (instantiated with no arguments), a
factory callable, or an instance; it must expose `compact(...)` and
usually a `name`.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path


def load_compactor(spec: str):
    if ":" not in spec:
        raise ValueError(
            f"invalid compactor spec {spec!r}: expected 'module:Class' "
            "or 'path/to/file.py:Class'"
        )
    module_part, _, attr = spec.rpartition(":")
    if module_part.endswith(".py") or "/" in module_part or "\\" in module_part:
        path = Path(module_part)
        if not path.exists():
            raise ValueError(f"compactor file not found: {module_part}")
        module_name = f"_ck_user_{path.stem}"
        module_spec = importlib.util.spec_from_file_location(module_name, path)
        if module_spec is None or module_spec.loader is None:
            raise ValueError(f"cannot load compactor file: {module_part}")
        module = importlib.util.module_from_spec(module_spec)
        sys.modules[module_name] = module
        module_spec.loader.exec_module(module)
    else:
        try:
            module = importlib.import_module(module_part)
        except ImportError as exc:
            raise ValueError(f"cannot import module {module_part!r}: {exc}") from exc
    obj = module
    for part in attr.split("."):
        if not hasattr(obj, part):
            raise ValueError(f"{module_part!r} has no attribute {attr!r}")
        obj = getattr(obj, part)
    if isinstance(obj, type):
        compactor = obj()
    elif hasattr(obj, "compact"):
        compactor = obj  # already an instance
    elif callable(obj):
        compactor = obj()  # factory function
    else:
        compactor = obj
    if not hasattr(compactor, "compact"):
        raise ValueError(f"{spec!r} does not provide a compactor (no compact method)")
    if not hasattr(compactor, "name"):
        compactor.name = attr
    return compactor
