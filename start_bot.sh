#!/bin/bash

# Lock file to prevent duplicate instances
LOCK_FILE="/tmp/dragon_casino_bot.lock"
PID_FILE="/tmp/dragon_casino_bot.pid"

# Check if bot is already running
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        # Process is still running, don't start a duplicate
        exit 0
    fi
fi

# Kill any stray processes
killall -9 python 2>/dev/null || true
sleep 1

# Start the bot and store its PID
python main.py &
BOT_PID=$!
echo $BOT_PID > "$PID_FILE"
wait $BOT_PID
