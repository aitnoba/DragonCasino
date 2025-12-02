#!/usr/bin/env python3
"""Dragon Casino Bot - Startup Script"""
import sys
import os

print("[STARTUP] ================================================")
print("[STARTUP] Dragon Casino Bot Starting...")
print("[STARTUP] ================================================")

# Validate required environment variables
token = os.getenv("DISCORD_BOT_TOKEN")
if not token:
    print("[FATAL] DISCORD_BOT_TOKEN not set!")
    print("[FATAL] Please add DISCORD_BOT_TOKEN to Render Environment tab")
    sys.exit(1)

# Set defaults for optional variables
os.environ.setdefault("BOT_WALLET_ADDRESS", "2wV9M71BjEUcuDmQBLYwbxveyhap7KLRyVRBPDstPgo2")
os.environ.setdefault("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

print(f"[STARTUP] Discord Bot Token: Set ✓")
print(f"[STARTUP] Wallet Address: {os.getenv('BOT_WALLET_ADDRESS')[:20]}...")
print(f"[STARTUP] Solana RPC: {os.getenv('SOLANA_RPC_URL')}")
print("[STARTUP] ================================================")

try:
    print("[STARTUP] Importing bot modules...")
    from main import bot
    
    print("[STARTUP] All modules imported successfully ✓")
    print("[STARTUP] Connecting to Discord Gateway...")
    print("[STARTUP] ================================================")
    print()
    
    bot.run(token)
    
except ImportError as e:
    print(f"[FATAL] Import Error - Missing module: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
except Exception as e:
    print(f"[FATAL] Startup Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
