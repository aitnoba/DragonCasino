#!/usr/bin/env python3
import sys
import os

# Ensure environment variables are set
if not os.getenv("DISCORD_BOT_TOKEN"):
    print("ERROR: DISCORD_BOT_TOKEN not set!")
    sys.exit(1)

# Set defaults for optional vars
os.environ.setdefault("BOT_WALLET_ADDRESS", "2wV9M71BjEUcuDmQBLYwbxveyhap7KLRyVRBPDstPgo2")
os.environ.setdefault("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

print("[STARTUP] Starting Dragon Casino Bot...")
print(f"[STARTUP] Bot Token: {'*' * 10}...{os.getenv('DISCORD_BOT_TOKEN', 'MISSING')[-5:]}")
print(f"[STARTUP] Wallet: {os.getenv('BOT_WALLET_ADDRESS')}")

try:
    from main import bot
    print("[STARTUP] Main bot imported successfully")
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))
except Exception as e:
    print(f"[ERROR] Failed to start bot: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
