#!/usr/bin/env bash
# Hermes Config Kit — clean replies, live progress bubble, mid-task steering, speed.
#
#   curl -fsSL https://raw.githubusercontent.com/mdmosfikur6630-spec/hermes-config/main/install.sh | bash
#
# Flags (pass after `| bash -s --`):
#   --dry-run        print the actions without changing anything
#   --no-patches     only apply config + persona (no source patches; for APT/desktop installs)
#   --no-restart     do not restart a running gateway
#   --yes            no prompts
#
# Nothing secret is downloaded or written by this script.
set -euo pipefail

REPO_SLUG="mdmosfikur6630-spec/hermes-config"
BRANCH="${HERMES_KIT_BRANCH:-main}"
RAW="https://raw.githubusercontent.com/${REPO_SLUG}/${BRANCH}"

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
HERMES_REPO="${HERMES_REPO:-$HERMES_HOME/hermes-agent}"
export HERMES_HOME HERMES_REPO

DRY_RUN=0
APPLY_PATCHES=1
RESTART=1
ASSUME_YES=0

for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=1 ;;
    --no-patches) APPLY_PATCHES=0 ;;
    --no-restart) RESTART=0 ;;
    --yes|-y) ASSUME_YES=1 ;;
    -h|--help)
      sed -n '2,16p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

info()  { printf '\033[36m•\033[0m %s\n' "$*"; }
ok()    { printf '\033[32m✓\033[0m %s\n' "$*"; }
warn()  { printf '\033[33m!\033[0m %s\n' "$*"; }
die()   { printf '\033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

run() {
  if [ "$DRY_RUN" = 1 ]; then
    printf '  [dry-run] %s\n' "$*"
  else
    "$@"
  fi
}

fetch() {
  local url="$1" dest="$2"
  if [ "$DRY_RUN" = 1 ]; then
    printf '  [dry-run] curl %s -> %s\n' "$url" "$dest"
    return 0
  fi
  curl -fsSL --retry 3 "$url" -o "$dest"
}

echo
echo "Hermes Config Kit"
echo "-----------------"

# ── preflight ──────────────────────────────────────────────────────────────
command -v hermes >/dev/null 2>&1 || die "hermes not found on PATH. Install it first: https://hermes-agent.nousresearch.com/docs/getting-started/installation"
[ -d "$HERMES_HOME" ] || die "HERMES_HOME does not exist: $HERMES_HOME"

PYTHON="$(command -v python3 || true)"
[ -n "$PYTHON" ] || die "python3 is required to apply patches"

STAMP="$(date +%Y%m%d-%H%M%S)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

info "Hermes home: $HERMES_HOME"
info "Source checkout: $HERMES_REPO"

# ── 1. persona ─────────────────────────────────────────────────────────────
if [ -f "$HERMES_HOME/SOUL.md" ]; then
  run cp "$HERMES_HOME/SOUL.md" "$HERMES_HOME/SOUL.md.bak.$STAMP"
  ok "backed up SOUL.md -> SOUL.md.bak.$STAMP"
fi
fetch "$RAW/SOUL.md" "$TMP/SOUL.md"
run cp "$TMP/SOUL.md" "$HERMES_HOME/SOUL.md"
ok "persona installed (concise answers + speed rules)"

# ── 2. configuration ───────────────────────────────────────────────────────
[ -f "$HERMES_HOME/config.yaml" ] && run cp "$HERMES_HOME/config.yaml" "$HERMES_HOME/config.yaml.bak.$STAMP"

set_cfg() {
  local key="$1" value="$2"
  if [ "$DRY_RUN" = 1 ]; then
    printf '  [dry-run] hermes config set %s %s\n' "$key" "$value"
    return 0
  fi
  hermes config set --force "$key" "$value" >/dev/null
}

info "applying configuration"
# Clean replies: no engine notices, reasoning, footers or diff spam.
set_cfg display.suppress_warning_notifications true
set_cfg display.credits_notices false
set_cfg display.show_reasoning false
set_cfg display.ephemeral_system_ttl 30
set_cfg display.runtime_footer.enabled false
set_cfg display.interim_assistant_messages false
set_cfg display.inline_diffs false
set_cfg display.turn_summary false
set_cfg display.tool_progress off
set_cfg display.tool_preview_length 160
set_cfg display.file_mutation_verifier false

# Telegram: one live progress bubble, edited in place, deleted after the answer.
set_cfg display.platforms.telegram.streaming true
set_cfg display.platforms.telegram.tool_progress all
set_cfg display.platforms.telegram.tool_progress_grouping replace
set_cfg display.platforms.telegram.cleanup_progress true
set_cfg display.platforms.telegram.interim_assistant_messages false
set_cfg display.platforms.telegram.busy_ack_detail false

# Talk to the bot while it works.
set_cfg display.busy_input_mode steer
set_cfg display.busy_steer_ack_enabled true

# Speed.
set_cfg agent.api_max_retries 1
set_cfg agent.execution_guidance false
set_cfg auxiliary.title_generation.model_upgrade_enabled false
set_cfg auxiliary.title_generation.prefer_fast_model true
set_cfg auxiliary.background_review.enabled false
set_cfg provider_routing.sort latency
set_cfg skills.creation_nudge_interval 0
ok "configuration applied"

# ── 3. patches ─────────────────────────────────────────────────────────────
if [ "$APPLY_PATCHES" = 1 ]; then
  if [ -d "$HERMES_REPO/.git" ]; then
    info "applying source patches"
    for p in 01-live-progress-replace 02-inline-diff-gate 03-steer-ack 04-answer-while-busy; do
      fetch "$RAW/patches/$p.py" "$TMP/$p.py"
      if [ "$DRY_RUN" = 1 ]; then
        printf '  [dry-run] python3 %s\n' "$TMP/$p.py"
      else
        "$PYTHON" "$TMP/$p.py"
      fi
    done
    ok "patches applied (restart the gateway to load them)"
  else
    warn "no git checkout at $HERMES_REPO — skipping source patches (config + persona still applied)"
  fi
else
  info "source patches skipped (--no-patches)"
fi

# ── 4. gateway restart ─────────────────────────────────────────────────────
if [ "$RESTART" = 1 ] && [ "$DRY_RUN" = 0 ]; then
  if hermes gateway status 2>/dev/null | grep -q "Gateway is running"; then
    info "restarting gateway"
    hermes gateway restart >/dev/null 2>&1 || warn "restart failed; run: hermes gateway restart"
  fi
fi

# ── 5. next steps ──────────────────────────────────────────────────────────
echo
ok "done"
cat <<EOF

Add your credentials (this kit never ships secrets):

  echo 'DEEPSEEK_API_KEY=...'              >> $HERMES_HOME/.env
  echo 'TELEGRAM_BOT_TOKEN=...'            >> $HERMES_HOME/.env
  echo 'TELEGRAM_ALLOWED_USERS=123456789'  >> $HERMES_HOME/.env
  echo 'HERMES_TELEGRAM_FOLLOWUP_GRACE_SECONDS=0' >> $HERMES_HOME/.env

Then:  hermes gateway run

Backups written next to the originals:
  $HERMES_HOME/config.yaml.bak.<timestamp>
  $HERMES_HOME/SOUL.md.bak.<timestamp>
EOF
