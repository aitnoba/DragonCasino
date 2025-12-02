# Dragon Casino Discord Bot

## Overview
A Discord casino bot with provably fair gambling games including Mines, Blackjack, Roulette, and Coinflip. Uses Dragon Coins (DC) as the in-game currency with SOL integration via tip.cc for deposits and withdrawals.

## Project Structure
```
├── main.py          # Main bot entry point and command handlers
├── blackjack.py     # Blackjack game logic
├── roulette.py      # Roulette game logic
├── mines.py         # Mines game logic
├── views.py         # Discord UI components (buttons, views)
├── dragon_casino.db # SQLite database (auto-created)
└── requirements.txt # Python dependencies
```

## Features
- **Games**: Coinflip, Blackjack, Roulette, Mines (5x5 grid)
- **Provably Fair**: HMAC-SHA256 based random number generation with client seeds
- **Currency**: Dragon Coins (DC) pegged at $1.00 USD = real-time SOL value from CoinGecko
- **USD Display**: All DC amounts show USD equivalent in brackets (e.g., 1.00 DC [$1.00])
- **SOL Integration**: Direct Solana wallet integration for deposits and withdrawals
- **Minimum Deposit**: 0.25 DC ($0.25 USD equivalent in SOL)
- **Minimum Withdrawal**: 0.25 DC ($0.25 USD equivalent in SOL)
- **User Profiles**: Balance, stats, client seed management, role-based elite status
- **Wager Requirement**: Users must wager full deposited amount before withdrawing

## Commands

### Profile & Balance
- `.profile` - View profile with DC balance, games played, total wagered/won. Regular users: channel 1444450215796015289 only. Admins/staff: server-wide (anywhere)
- `.balance` - Check DC balance. Regular users: channel 1445047863158640803 only. Admins/staff: server-wide (anywhere). Use `.profile @user` or `.balance @user` to check others
- `.deposit` - Deposit SOL to receive DC (channel 1444450098980454521 only)
- `.withdraw <amount>` - Withdraw DC to SOL (channel 1444450098980454521 only)
- `.leaderboard` - View top 10 players by DC balance (channel 1444450176394596534 only)
- `.botbalance` - (Admin) Check bot's estimated SOL balance from tracked deposits/withdrawals

### Games (Channel-Restricted)
- `.cf <amount>` - Play Coinflip (channel 1444449509944987819 or elite casino)
- `.bj <amount>` - Play Blackjack (channel 1444449583416610930 or elite casino)
- `.rl <amount> <bet_type>` - Play Roulette (channel 1444449686177054821 or elite casino)
- `.mines <amount> <num_mines>` - Play Mines (channel 1444449762408661215 or elite casino)

### Elite Casino Channel
- **Channel ID:** 1444450537398472734
- All games and commands can be played/used here

### Chat Channels (No Commands)
- **General Chat:** 1444449830825885736 - For Dragons and Elite Dragons
- **Elite Chat:** 1444450499540684931 - For Elite Dragons only
- No casino commands work in these channels (chat-only zones)

### Admin Commands
- `.give @user <amount>` - Give DC to a user
- `.zap [limit]` - Delete messages in the channel (default: 100)
- `.thanos` - Snap! Delete all messages in the channel, then delete the snapped message after 10 seconds

### General
- `.help_casino` - Show all available commands

## Solana Deposit System

### Deposits (Three-Step Process)
**User Flow:**

**Step 1: Request Amount**
- Run `.deposit`
- Bot asks: "How many Dragon Coins do you want to deposit?"
- User enters DC amount (e.g., `10` or `50.5`)

**Step 2: Send SOL & Confirm**
- Bot shows:
  - DC amount to deposit
  - USD equivalent
  - SOL required (without fee)
  - Transaction fee (~0.00025 SOL)
  - **Total SOL to send** (amount + fee)
  - Bot's Solana wallet address to copy
- User sends the SOL to the wallet
- User clicks "✅ Done - I Sent SOL" button

**Step 3: Provide Transaction Hash**
- Bot asks for Solana transaction hash
- User enters transaction hash (with warning to double-check)
- Deposit request sent with status "Pending admin verification"

**Admin Flow:**
1. Run `.pending_deposits` to see all pending deposit requests
2. Review requests with transaction hashes shown
3. Run `.approve_deposit <request_id>` to verify on-chain and approve
4. Bot verifies transaction on Solana blockchain automatically
5. DC is instantly credited to user's account

### Withdrawals (Admin-Based)
1. Run `.withdraw <amount>` to request a withdrawal
2. DC is immediately deducted from your balance
3. Request appears pending for admin review
4. Admin runs `.withdrawals` to see all pending requests
5. Admin approves with `.approve <request_id> <your_solana_address>`
6. Admin manually sends SOL from bot's wallet to your address

### Bot Balance Tracking
- Run `.botbalance` to see estimated SOL balance from tracked deposits/withdrawals
- This helps admins know how much SOL is available for withdrawals
- Bot receives SOL to wallet: `2wV9M71BjEUcuDmQBLYwbxveyhap7KLRyVRBPDstPgo2`

## Recent Changes (Dec 1, 2025)
- **Seed Rotation**: Changed from daily (24-hour) to 30-minute epochs - secret seeds and hashes now rotate every 30 minutes and are posted to seed channel
- **Admin Server-Wide Access**: Admins and casino staff can now check any user's profile/balance or their own anywhere on server (no channel restrictions)
- **Fixed Duplicate Bot Instances**: Implemented PID-based locking system in start_bot.sh to prevent multiple instances from spawning
- **Fixed Game Interactions**: Resolved unpacking errors in seed generation and timeout handlers for all games (Coinflip, Blackjack, Roulette, Mines)
- **Previous**: Implemented complete addiction warning system with DM/admin notifications at wager thresholds, daily reset of usage tracking

## Environment Variables
- `DISCORD_BOT_TOKEN` - Your Discord bot token (required)
- `BOT_WALLET_ADDRESS` - Your Solana wallet address for receiving deposits (required)
- `SOLANA_RPC_URL` - Solana RPC endpoint (default: mainnet, optional)

## Running the Bot
The bot runs automatically via the configured workflow. Make sure to set the `DISCORD_BOT_TOKEN` secret in your Replit environment.

## Tech Stack
- Python 3.11
- discord.py 2.x
- SQLite3 (database with provably fair fields and transaction tracking)
- requests (for CoinGecko API to fetch SOL/USD price)
- CoinGecko API (for live SOL pricing)

## Database Schema
- **users table**: user_id, username, dragon_coins, total_wagered, total_won, games_played, is_elite_dragon, client_seed, nonce
- **bot_transactions table**: transaction_id, sol_amount, dc_amount, transaction_type (deposit/withdrawal), timestamp

## Design Notes
- Deposits are automatically detected from tip.cc messages containing "@Dragon Casino" and SOL amounts
- USD to SOL conversion uses live CoinGecko API pricing
- All currency displays show both DC and USD for clarity
- Provably fair system uses HMAC-SHA256 with daily server seed and per-user client seed + nonce
- User can verify game fairness by checking their client seed against the public hash
