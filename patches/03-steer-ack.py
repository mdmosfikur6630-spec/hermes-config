#!/usr/bin/env python3
"""Patch 3/3 — acknowledge steered messages on the gateway's busy fast-path.

`display.busy_input_mode: steer` injected follow-up text into the running turn but the
fast path never sent the "Steered into current run" ack, so a busy bot looked like it was
ignoring the user. Route accepted steers through the existing `_busy_interrupt_and_ack`
helper (which honours `display.busy_steer_ack_enabled` and its 30s debounce).

Idempotent: exits 0 when the marker is already present.
"""

from __future__ import annotations

import os
import pathlib
import sys

ROOT = pathlib.Path(os.environ.get("HERMES_REPO", pathlib.Path.home() / ".hermes/hermes-agent"))
target = ROOT / "gateway/run_inbound.py"
MARKER = "await self._hm_busy_steer"

if not target.is_file():
    sys.exit(f"not a Hermes source checkout: {ROOT}")

src = target.read_text(encoding="utf-8")
if MARKER in src:
    print("patch 3/3 already applied")
    sys.exit(0)

old = '''    def _hm_busy_steer(self, event: MessageEvent, running_agent: Any, _quick_key: str) -> None:
        """Steer mode: inject text mid-run via ``agent.steer()``, else fall back to queue semantics."""
        steer_text = (event.text or "").strip()
        steered = False
        if self._hm_text_only(event) and steer_text and hasattr(running_agent, "steer"):
            try:
                steered = self._steer_running_agent(running_agent, self._steer_text_with_origin(steer_text, event))
            except Exception as exc:
                logger.warning("PRIORITY steer failed for session %s: %s", _quick_key, exc)
        if steered:
            self._fold_into_running_turn(running_agent, _quick_key, event)
            logger.debug("PRIORITY steer for session %s", _quick_key)
            return
'''

new = '''    async def _hm_busy_steer(self, event: MessageEvent, running_agent: Any, _quick_key: str) -> None:
        """Steer mode: inject text mid-run via ``agent.steer()``, else fall back to queue semantics."""
        steer_text = (event.text or "").strip()
        steered = False
        if self._hm_text_only(event) and steer_text and hasattr(running_agent, "steer"):
            try:
                steered = self._steer_running_agent(running_agent, self._steer_text_with_origin(steer_text, event))
            except Exception as exc:
                logger.warning("PRIORITY steer failed for session %s: %s", _quick_key, exc)
        if steered:
            self._fold_into_running_turn(running_agent, _quick_key, event)
            # Tell the user the message landed: the text is consumed after the next tool call, so
            # without an ack a busy bot reads as "ignoring me".
            adapter = self._delivery_adapter_for(event.source)
            if adapter is not None:
                outcome = self._BusySteerOutcome(
                    effective_mode="steer",
                    demoted_for_subagents=False,
                    demoted_for_compression=False,
                    steered=True,
                    redirected=False,
                )
                try:
                    await self._busy_interrupt_and_ack(
                        event, _quick_key, adapter, self._peek_session_state(_quick_key),
                        running_agent, outcome,
                    )
                except Exception as exc:  # ack failure must never drop the steer
                    logger.debug("Steer ack failed for session %s: %s", _quick_key, exc)
            logger.debug("PRIORITY steer for session %s", _quick_key)
            return
'''

if src.count(old) != 1:
    sys.exit(f"FAIL {target}: expected 1 match, found {src.count(old)} (version mismatch?)")
src = src.replace(old, new, 1)

old_call = '''        if effective_busy_input_mode == "steer":
            self._hm_busy_steer(event, running_agent, _quick_key)
            return None'''
new_call = '''        if effective_busy_input_mode == "steer":
            await self._hm_busy_steer(event, running_agent, _quick_key)
            return None'''
if src.count(old_call) != 1:
    sys.exit(f"FAIL {target}: call site not found (version mismatch?)")
src = src.replace(old_call, new_call, 1)

target.write_text(src, encoding="utf-8")
print(f"  patched {target.relative_to(ROOT)}")
print("patch 3/3 applied")
