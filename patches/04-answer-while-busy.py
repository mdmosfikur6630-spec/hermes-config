#!/usr/bin/env python3
"""Patch 4/4 — answer interjections immediately while a turn is busy.

`display.busy_input_mode: steer` injects follow-up text at the next tool boundary, but the
user gets no reply until then — and if the running tool is slow, that can be minutes.
This patch reuses the `/btw` machinery (a transcript-snapshot answer that never touches the
live history) to reply to the incoming message at once, while still steering the text into
the running turn.

Idempotent: exits 0 when the marker is already present.
"""

from __future__ import annotations

import os
import pathlib
import sys

ROOT = pathlib.Path(os.environ.get("HERMES_REPO", pathlib.Path.home() / ".hermes/hermes-agent"))
target = ROOT / "gateway/run_inbound.py"
MARKER = "Busy answer failed for session"

if not target.is_file():
    sys.exit(f"not a Hermes source checkout: {ROOT}")

src = target.read_text(encoding="utf-8")
if MARKER in src:
    print("patch 4/4 already applied")
    sys.exit(0)

old = '''        """Steer mode: inject text mid-run via ``agent.steer()``, else fall back to queue semantics."""
        steer_text = (event.text or "").strip()
        steered = False
'''

new = '''        """Steer mode: inject text mid-run via ``agent.steer()``, else fall back to queue semantics."""
        steer_text = (event.text or "").strip()
        # Reply to the interjection right away from a transcript snapshot (same machinery as
        # /btw): a busy turn must never leave the user on read. The text is still steered below.
        if self._hm_text_only(event) and steer_text:
            try:
                _reply = await self._handle_btw_command(event)
                if _reply:
                    _adapter = self._delivery_adapter_for(event.source)
                    if _adapter is not None:
                        await _adapter.send(event.source.chat_id, _reply)
            except Exception as exc:
                logger.debug("Busy answer failed for session %s: %s", _quick_key, exc)
        steered = False
'''

if src.count(old) != 1:
    sys.exit(f"FAIL {target}: expected 1 match, found {src.count(old)} (apply patch 3 first)")
src = src.replace(old, new, 1)
target.write_text(src, encoding="utf-8")
print(f"  patched {target.relative_to(ROOT)}")
print("patch 4/4 applied")
