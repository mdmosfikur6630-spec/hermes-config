# Hermes Config Kit

An opinionated, one-command configuration layer for [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research), focused on three things:

1. **Clean replies** — the chat gets the answer, not diffs, warnings, reasoning, footers or progress spam.
2. **A live progress bubble** — one message per task, edited in place step by step like a terminal, deleted once the final answer lands.
3. **Mid-task steering** — talk to the bot while it works; your message is folded into the running task instead of being refused or queued until it finishes.

Plus a speed pass (batching, no redundant verification, low-latency provider routing) and a concise-output persona.

Nothing here contains credentials. You add your own keys after install.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/mdmosfikur6630-spec/hermes-config/main/install.sh | bash
```

Useful flags:

```bash
# preview changes
curl -fsSL .../install.sh | bash -s -- --dry-run

# config + persona only (no source patches — e.g. the Termux APT package)
curl -fsSL .../install.sh | bash -s -- --no-patches

# don't touch a running gateway
curl -fsSL .../install.sh | bash -s -- --no-restart
```

Requirements: Hermes Agent installed (`hermes` on `PATH`), `python3`, `curl`. Linux/macOS/WSL2 or any host with a git source checkout for the patches.

## What it changes

### Display — clean, quiet chat

| Key | Value | Why |
|---|---|---|
| `display.suppress_warning_notifications` | `true` | hides compression/retry/fallback/credit/subagent notices |
| `display.credits_notices` | `false` | no usage-grant chatter |
| `display.show_reasoning` | `false` | no reasoning blocks in the reply |
| `display.ephemeral_system_ttl` | `30` | auto-deletes "✨ New session" style notices |
| `display.runtime_footer.enabled` | `false` | no `model · 68% · ~/dir` footer |
| `display.interim_assistant_messages` | `false` | no mid-turn commentary messages |
| `display.inline_diffs` | `false` | no diff blocks in one-shot/CLI output |
| `display.turn_summary` | `false` | no post-turn stats line in the CLI |
| `display.tool_progress` | `off` | CLI stays silent; Telegram overrides below |
| `display.tool_preview_length` | `160` | caps tool previews |
| `display.file_mutation_verifier` | `false` | no post-write advisory pass |

### Telegram — one live progress bubble

| Key | Value |
|---|---|
| `display.platforms.telegram.tool_progress` | `all` |
| `display.platforms.telegram.tool_progress_grouping` | `replace` |
| `display.platforms.telegram.cleanup_progress` | `true` |
| `display.platforms.telegram.streaming` | `true` |
| `display.platforms.telegram.interim_assistant_messages` | `false` |
| `display.platforms.telegram.busy_ack_detail` | `false` |

`replace` is a new grouping mode this kit patches in: the single editable progress message shows **only the step currently running**. When the answer is delivered, the bubble is deleted (`cleanup_progress`).

### Steering — talk while it works

| Key | Value |
|---|---|
| `display.busy_input_mode` | `steer` |
| `display.busy_steer_ack_enabled` | `true` |

Plain text sent during a running turn is injected into that turn (`agent.steer()`) and picked up after the current tool call. The kit also patches in an immediate **"⏩ Steered into current run"** acknowledgement, because upstream steers silently.

Recommended extra (not set by the script, it is an env var):

```bash
echo 'HERMES_TELEGRAM_FOLLOWUP_GRACE_SECONDS=0' >> ~/.hermes/.env
```

Upstream queues Telegram follow-ups that arrive within 3 seconds of task start instead of steering them.

### Speed

| Key | Value | Why |
|---|---|---|
| `agent.execution_guidance` | `false` | drops the mandatory read-back/verify loop |
| `agent.api_max_retries` | `1` | fail over instead of retrying 3× |
| `auxiliary.title_generation.model_upgrade_enabled` | `false` | no extra model call per session |
| `auxiliary.title_generation.prefer_fast_model` | `true` | title call uses the fast tier |
| `auxiliary.background_review.enabled` | `false` | no post-turn self-review replay |
| `provider_routing.sort` | `latency` | OpenRouter picks the lowest time-to-first-token provider |
| `skills.creation_nudge_interval` | `0` | no skill-creation nudges mid-task |

Trade-off: with `execution_guidance: false` the agent no longer forces a read-back after writes. Set it back with `hermes config set agent.execution_guidance auto` for risky work.

### Persona

`SOUL.md` adds two blocks on top of the upstream persona:

- **Output discipline** — the reply is the answer; no narration, no raw stdout/stderr, no step logs.
- **Speed** — plan once then act, batch independent tool calls, never re-read what you just wrote, stop verifying once the goal is met.

## The patches

Upstream Hermes has no release that includes these behaviours, so the kit applies three small, idempotent patches to the source checkout at `~/.hermes/hermes-agent`:

| Patch | Files | What it fixes |
|---|---|---|
| `01-live-progress-replace` | `gateway/display_config.py`, `gateway/run_turn_progress.py`, `hermes_cli/config_defaults.py` | adds `tool_progress_grouping: replace` |
| `02-inline-diff-gate` | `agent/display.py`, `hermes_cli/gateway_agent.py` | `display.inline_diffs: false` is actually honoured; no diff blocks in `-Q` output |
| `03-steer-ack` | `gateway/run_inbound.py` | steered messages get an immediate acknowledgement |

Each script checks for its marker first, so re-running the installer is safe. If upstream changes the surrounding code, the patch aborts with a `version mismatch` message instead of guessing.

## After installing

```bash
# credentials (never committed here)
echo 'DEEPSEEK_API_KEY=...'             >> ~/.hermes/.env
echo 'TELEGRAM_BOT_TOKEN=...'           >> ~/.hermes/.env
echo 'TELEGRAM_ALLOWED_USERS=123456789' >> ~/.hermes/.env

hermes gateway run
```

Backups: `~/.hermes/config.yaml.bak.<timestamp>`, `~/.hermes/SOUL.md.bak.<timestamp>`.

## Uninstall

- Restore the newest `config.yaml.bak.*` and `SOUL.md.bak.*`.
- Revert the patches in the checkout: `cd ~/.hermes/hermes-agent && git checkout -- gateway/display_config.py gateway/run_turn_progress.py hermes_cli/config_defaults.py agent/display.py hermes_cli/gateway_agent.py gateway/run_inbound.py`
- Or reinstall Hermes / `hermes update`.

## Security

This repository contains **no** API keys, bot tokens, chat IDs or session data. The installer only writes configuration keys, a persona file, and the three source patches. Review `install.sh` and `patches/*.py` before running — it is a few hundred lines.

## License

MIT — see [LICENSE](LICENSE).
