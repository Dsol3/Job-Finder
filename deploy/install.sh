#!/usr/bin/env bash
# ---------------------------------------------------------------------------
#  job_finder — one-shot installer for an always-on Linux box
#  Tested on Ubuntu 22.04 / 24.04 and Debian 12 (Oracle Cloud, Hetzner, DO,
#  Lightsail, Raspberry Pi OS all work). Idempotent: safe to re-run.
#
#  Usage, on a fresh server:
#     git clone -b arena/7c5b793b-job-finder https://github.com/Dsol3/Job-Finder.git
#     cd Job-Finder && sudo bash deploy/install.sh
#
#  Non-interactive (no prompts, e.g. from cloud-init):
#     sudo TELEGRAM_BOT_TOKEN=123:ABC TELEGRAM_CHAT_ID=456 bash deploy/install.sh
# ---------------------------------------------------------------------------
set -euo pipefail

APP_USER="${APP_USER:-$(logname 2>/dev/null || echo "${SUDO_USER:-$(id -un)}")}"
APP_DIR="${APP_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
SERVICE="jobfinder"
ENV_FILE="/etc/${SERVICE}.env"
UNIT="/etc/systemd/system/${SERVICE}.service"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
die()  { printf '  \033[31m✗\033[0m %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "run with sudo: sudo bash deploy/install.sh"

say "1/6  Checking Python"
PY="$(command -v python3 || true)"
[[ -n "$PY" ]] || die "python3 not found — apt-get install -y python3"
PYVER="$("$PY" -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
ok "python3 $PYVER at $PY"
if ! "$PY" -c 'import sys;raise SystemExit(0 if sys.version_info>=(3,11) else 1)'; then
  warn "Python $PYVER has no built-in tomllib (needs 3.11+). Installing the tomli backport."
  apt-get update -qq && apt-get install -y -qq python3-pip >/dev/null
  "$PY" -m pip install --user --quiet tomli 2>/dev/null \
    || "$PY" -m pip install --quiet --break-system-packages tomli
  ok "tomli installed as a fallback"
fi

say "2/6  Preparing $APP_DIR"
cd "$APP_DIR"
[[ -f "$APP_DIR/job_finder/__init__.py" ]] || die "run this from inside the Job-Finder checkout"
if [[ ! -f config.toml ]]; then
  cp config.example.toml config.toml
  ok "created config.toml (edit it later to tune keywords)"
else
  ok "config.toml already present, left untouched"
fi
chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
ok "ownership set to $APP_USER"
"$PY" -c "import sys;sys.path.insert(0,'$APP_DIR');import job_finder" \
  || die "the code does not import — check the checkout"
ok "code imports cleanly"

say "3/6  Telegram credentials"
TOKEN="${TELEGRAM_BOT_TOKEN:-}"
CHAT="${TELEGRAM_CHAT_ID:-}"
if [[ -z "$TOKEN" || -z "$CHAT" ]]; then
  if [[ -t 0 ]]; then
    echo "  Paste the bot token from @BotFather (input is hidden), then your chat id."
    echo "  No chat id yet? Run this instead, from your own machine:"
    echo "      python3 -m job_finder --setup-telegram"
    echo "  which discovers it for you, then copy TELEGRAM_CHAT_ID from .env"
    read -rsp "  bot token: " TOKEN; echo
    read -rp  "  chat id  : " CHAT; echo
  else
    die "no credentials. Re-run with TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... or interactively over SSH."
  fi
fi
[[ -n "$TOKEN" && -n "$CHAT" ]] || die "both values are required"

umask 077
cat > "$ENV_FILE" <<EOF
# job_finder secrets — root only
TELEGRAM_BOT_TOKEN=$TOKEN
TELEGRAM_CHAT_ID=$CHAT
PYTHONIOENCODING=utf-8
EOF
chmod 600 "$ENV_FILE"; chown root:root "$ENV_FILE"
ok "wrote $ENV_FILE (chmod 600)"

say "4/6  Verifying the connection to Telegram"
VERIFY="$("$PY" - <<'PYVERIFY'
import os, sys
sys.path.insert(0, os.environ.get("APP_DIR", "."))
from job_finder import telegram
token = os.environ["TELEGRAM_BOT_TOKEN"]; chat = os.environ["TELEGRAM_CHAT_ID"]
me = telegram.get_me(token)
if not me.get("ok"):
    print("fail token: " + str(me.get("description"))); raise SystemExit(1)
got = telegram.get_chat(token, chat)
if not got.get("ok"):
    print("fail chat: " + str(got.get("description"))); raise SystemExit(1)
name = got["result"].get("title") or got["result"].get("first_name") or chat
print(f"ok @{me['result'].get('username')} -> {name} ({chat})")
PYVERIFY
)" || { warn "verification failed: $VERIFY"; die "fix the token/chat id, then re-run"; }
ok "$VERIFY"

say "5/6  Installing the systemd service"
cat > "$UNIT" <<EOF
[Unit]
Description=job_finder — Reddit watcher for content and YouTube roles
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$ENV_FILE
ExecStart=$PY -m job_finder --loop --quiet
Restart=always
RestartSec=60
StandardOutput=journal
StandardError=journal
# hardening: the app only needs to write its own directory
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=read-only
ReadWritePaths=$APP_DIR

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now "$SERVICE" >/dev/null
sleep 2
systemctl is-active --quiet "$SERVICE" && ok "$SERVICE is running and enabled at boot" \
  || die "service failed to start — see: journalctl -u $SERVICE -n 50 --no-pager"

say "6/6  First sweep"
"$PY" -m job_finder --once || warn "--once returned non-zero; the service will keep retrying anyway"
warn "The first sweep only records what already exists, so alerts start from the NEXT new post."
echo
say "Done."
echo "  status : systemctl status $SERVICE --no-pager"
echo "  logs   : journalctl -u $SERVICE -f"
echo "  stop   : sudo systemctl stop $SERVICE"
echo "  tune   : nano $APP_DIR/config.toml   then   sudo systemctl restart $SERVICE"
echo "  trail  : $APP_DIR/matches.jsonl   (every alert ever sent)"
