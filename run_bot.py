#!/usr/bin/env python3
"""
Dragon Casino Bot - Render Entrypoint
Starts the bot with proper error handling and environment setup
"""
import os
import sys

# Validate and set environment
token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    print("[ERROR] DISCORD_BOT_TOKEN is not set!", file=sys.stderr)
    sys.exit(1)

# Set optional defaults
os.environ.setdefault("BOT_WALLET_ADDRESS", "2wV9M71BjEUcuDmQBLYwbxveyhap7KLRyVRBPDstPgo2")
os.environ.setdefault("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

print("[BOT] Starting Dragon Casino Bot...")

try:
    from main import bot
    print("[BOT] Importing main.py... OK")
    print("[BOT] Running bot.run()...")
    bot.run(token)
except KeyboardInterrupt:
    print("[BOT] Shutdown signal received")
    sys.exit(0)
except Exception as e:
    print(f"[ERROR] {e}", file=sys.stderr)
    import traceback
    traceback.print_exc()
    sys.exit(1)
