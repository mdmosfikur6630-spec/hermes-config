#!/usr/bin/env python3
"""Patch 2/3 — honour `display.inline_diffs` in quiet one-shot replies.

`hermes chat -q ... -Q` (and the local viewer) printed a raw diff block
("│ path / │ @@ ... / │ +line") into stdout before the actual answer, because
`hermes_cli/gateway_agent.py` emitted the inline diff unconditionally and the
renderer itself never consulted the config flag.

Idempotent: exits 0 when the marker is already present.
"""

from __future__ import annotations

import os
import pathlib
import sys

ROOT = pathlib.Path(os.environ.get("HERMES_REPO", pathlib.Path.home() / ".hermes/hermes-agent"))
MARKER = "_inline_diffs_allowed"

display = ROOT / "agent/display.py"
gateway_agent = ROOT / "hermes_cli/gateway_agent.py"

for target in (display, gateway_agent):
    if not target.is_file():
        sys.exit(f"not a Hermes source checkout: {ROOT}")

if MARKER in display.read_text(encoding="utf-8"):
    print("patch 2/3 already applied")
    sys.exit(0)


def patch(path: pathlib.Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        sys.exit(f"FAIL {path}: expected 1 match, found {text.count(old)} (version mismatch?)")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  patched {path.relative_to(ROOT)}")


patch(
    display,
    '''def render_edit_diff_with_delta(
    tool_name: str, result: str | None, *,
    function_args: dict | None = None, snapshot: LocalEditSnapshot | None = None, print_fn=None,
) -> bool:
    """Render an edit diff inline without taking over the terminal UI."""
    diff = extract_edit_diff(tool_name, result, function_args=function_args, snapshot=snapshot)
''',
    '''def _inline_diffs_allowed() -> bool:
    """`display.inline_diffs` (default True); never let a config read break rendering."""
    try:
        from hermes_cli.config import load_config_readonly

        display = (load_config_readonly() or {}).get("display") or {}
        if not isinstance(display, dict):
            return True
        value = display.get("inline_diffs", True)
        if isinstance(value, str):
            return value.strip().lower() not in ("false", "0", "off", "no")
        return bool(value)
    except Exception:
        return True


def render_edit_diff_with_delta(
    tool_name: str, result: str | None, *,
    function_args: dict | None = None, snapshot: LocalEditSnapshot | None = None, print_fn=None,
) -> bool:
    """Render an edit diff inline without taking over the terminal UI."""
    if not _inline_diffs_allowed():
        return False
    diff = extract_edit_diff(tool_name, result, function_args=function_args, snapshot=snapshot)
''',
)

patch(
    gateway_agent,
    '''        diff = payload.get("inline_diff")
        if isinstance(diff, str) and diff:
            from cli import _cprint''',
    '''        diff = payload.get("inline_diff")
        from agent.display import _inline_diffs_allowed as _inline_diffs_ok
        if (
            isinstance(diff, str) and diff
            and not getattr(self, "quiet_mode", False)
            and _inline_diffs_ok()
        ):
            from cli import _cprint''',
)

print("patch 2/3 applied")
