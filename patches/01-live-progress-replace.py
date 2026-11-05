#!/usr/bin/env python3
"""Patch 1/3 — "replace" tool-progress grouping.

One editable progress bubble whose body is swapped for the step currently running
(terminal-style live status) instead of a growing transcript ("accumulate") or one
message per tool ("separate"). Combined with `display.platforms.telegram.cleanup_progress`
the bubble is deleted again once the final answer lands.

Idempotent: exits 0 when the marker is already present.
"""

from __future__ import annotations

import os
import pathlib
import sys

ROOT = pathlib.Path(os.environ.get("HERMES_REPO", pathlib.Path.home() / ".hermes/hermes-agent"))
MARKER = "_progress_replaces_bubble"

files = {
    "display_config": ROOT / "gateway/display_config.py",
    "progress": ROOT / "gateway/run_turn_progress.py",
    "defaults": ROOT / "hermes_cli/config_defaults.py",
}

if not files["progress"].is_file():
    sys.exit(f"not a Hermes source checkout: {ROOT}")

if MARKER in files["progress"].read_text(encoding="utf-8"):
    print("patch 1/3 already applied")
    sys.exit(0)


def patch(path: pathlib.Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        sys.exit(f"FAIL {path}: expected 1 match, found {text.count(old)} (version mismatch?)")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")
    print(f"  patched {path.relative_to(ROOT)}")


patch(
    files["display_config"],
    '    "tool_progress_grouping": "accumulate",  # "accumulate" = edit one bubble; "separate" = one msg per tool',
    '    "tool_progress_grouping": "accumulate",  # "accumulate" = edit one bubble (append); "replace" = edit one bubble (current step only); "separate" = one msg per tool',
)

patch(
    files["display_config"],
    '    "tool_progress_grouping": _norm_choice(("accumulate", "separate")),',
    '    "tool_progress_grouping": _norm_choice(("accumulate", "replace", "separate")),',
)

patch(
    files["progress"],
    '''    def _progress_absorb(self, st, raw) -> Any:
        """Fold a queue item into the bubble buffer; returns the line to render this tick."""
        if isinstance(raw, tuple) and len(raw) == 3 and raw[0] == "__dedup__":
            _, base_msg, count = raw
            if not st.progress_lines:
                return base_msg
            st.progress_lines[-1] = _append_progress_repeat_count(base_msg, count + 1)
            return st.progress_lines[-1]
        st.progress_lines.append(raw)
        return raw
''',
    '''    def _progress_replaces_bubble(self) -> bool:
        """True when the progress bubble mirrors the current step instead of accumulating lines."""
        return str(getattr(self._ctx, "progress_grouping", "") or "").lower() == "replace"

    def _progress_absorb(self, st, raw) -> Any:
        """Fold a queue item into the bubble buffer; returns the line to render this tick."""
        if isinstance(raw, tuple) and len(raw) == 3 and raw[0] == "__dedup__":
            _, base_msg, count = raw
            if not st.progress_lines:
                return base_msg
            st.progress_lines[-1] = _append_progress_repeat_count(base_msg, count + 1)
            return st.progress_lines[-1]
        if self._progress_replaces_bubble():
            # Terminal-style live status: one editable bubble holding only the running step.
            st.progress_lines = [raw]
            return raw
        st.progress_lines.append(raw)
        return raw
''',
)

patch(
    files["defaults"],
    '''        # Gateway tool-progress grouping where edits are supported: "accumulate" edits one bubble |
        # "separate" one message per tool (noisier). Needs tool_progress enabled. Per-platform:''',
    '''        # Gateway tool-progress grouping where edits are supported: "accumulate" edits one bubble
        # (growing transcript) | "replace" edits one bubble that shows only the current step, like a
        # terminal status line | "separate" one message per tool (noisier). Needs tool_progress
        # enabled. Per-platform:''',
)

print("patch 1/3 applied")
