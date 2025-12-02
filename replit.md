# Dragon Casino Discord Bot

## Overview
A feature-rich Discord casino bot with provably fair gaming, built with Python and discord.py. Includes games like Blackjack, Roulette, Mines, and Coinflip with Dragon Coins (DC) currency system.

## Project Structure
```
├── main.py           # Main bot logic, commands, and database operations
├── blackjack.py      # Blackjack game implementation
├── roulette.py       # Roulette game implementation
├── mines.py          # Mines game implementation
├── views.py          # Discord UI components (buttons, views)
├── run_bot.py        # Render entrypoint script
├── start.py          # Alternative startup script
├── requirements.txt  # Python dependencies
├── Dockerfile        # Docker configuration for deployment
└── dragon_casino.db  # SQLite database (auto-created on first run)
```

## Database
- **Type**: SQLite (`dragon_casino.db`)
- **Tables**:
  - `users`: Player data, balances, stats, provably fair seeds
  - `bot_transactions`: Deposit/withdrawal records
  - `seed_history`: Provably fair seed rotation history

### Clearing the Database
To start fresh, simply delete the `dragon_casino.db` file. The bot will create a new one on startup.

## Environment Variables
| Variable | Required | Description |
|----------|----------|-------------|
| `DISCORD_BOT_TOKEN` | Yes | Discord bot token from Developer Portal |
| `BOT_WALLET_ADDRESS` | No | Solana wallet address for deposits |
| `SOLANA_RPC_URL` | No | Solana RPC endpoint (defaults to mainnet) |

## Running Locally on Replit
1. Ensure `DISCORD_BOT_TOKEN` is set in Secrets
2. The bot runs via the "Dragon Casino Bot" workflow
3. Check console output for status and errors

## Redeploying to Render

### After Making Code Changes:
1. **Push changes to GitHub**:
   ```bash
   git add .
   git commit -m "Your change description"
   git push origin main
   ```

2. **Render Auto-Deploy** (if enabled):
   - Render will automatically detect the push and redeploy

3. **Manual Deploy on Render**:
   - Go to your Render dashboard
   - Select your Dragon Casino service
   - Click "Manual Deploy" → "Deploy latest commit"

### Environment Variables on Render:
Make sure these are set in Render's Environment tab:
- `DISCORD_BOT_TOKEN`: Your Discord bot token

### Important Notes:
- The database on Render is separate from Replit's database
- To clear Render's database, you'll need to delete the `dragon_casino.db` file on the Render instance or redeploy with a fresh setup
- Only one instance of the bot can run at a time with the same token

## Recent Changes
- **December 2, 2025**: Imported from GitHub, fresh database initialization

## Bot Commands (Prefix: `.`)
- `.balance` - Check your Dragon Coins balance
- `.coinflip <amount> <heads/tails>` - Play coinflip
- `.blackjack <amount>` - Play blackjack
- `.roulette <amount> <bet_type>` - Play roulette
- `.mines <amount>` - Play mines
- `.deposit` - Get deposit instructions
- `.withdraw <amount> <address>` - Withdraw to Solana wallet
- `.leaderboard` - View top players
- `.stats` - View your gambling stats
