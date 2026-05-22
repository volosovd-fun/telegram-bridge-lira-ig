#!/bin/bash
# telegram-bridge-lira-ig — Trinity setup
# КРИТИЧНО: Trinity ігнорує `entrypoint` у template.yaml.
# Цей файл виконується при старті контейнера — тут запускаємо bot.py.

set -e

WORKSPACE="/home/developer"
LOG_DIR="$WORKSPACE/logs"
mkdir -p "$LOG_DIR"

echo "[setup.sh] telegram-bridge-lira-ig starting..."

# Install Python deps
echo "[setup.sh] Installing Python deps..."
pip install --user --quiet -r "$WORKSPACE/requirements.txt" || {
    echo "[setup.sh] ✗ pip install failed"
    exit 1
}

# Idempotent — не запускаємо двічі
if pgrep -f "python3.*bot\.py" > /dev/null 2>&1; then
    echo "[setup.sh] bot.py already running — skipping"
    exit 0
fi

# Run bot.py in background
echo "[setup.sh] Starting bot.py in background..."
cd "$WORKSPACE"
nohup python3 bot.py > "$LOG_DIR/bot.log" 2>&1 &
BOT_PID=$!

# Verify it's alive after 2 seconds
sleep 2
if kill -0 "$BOT_PID" 2>/dev/null; then
    echo "[setup.sh] ✓ bot.py running PID=$BOT_PID"
else
    echo "[setup.sh] ✗ bot.py died — last log lines:"
    tail -30 "$LOG_DIR/bot.log" 2>/dev/null
    exit 1
fi
