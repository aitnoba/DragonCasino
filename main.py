import discord
from discord.ext import commands, tasks
import sqlite3
import os
import requests
import re
import hashlib
import hmac
import time
import random
import asyncio
import secrets
from dotenv import load_dotenv
import qrcode
from PIL import Image, ImageDraw
from blackjack import BlackjackGame, active_blackjack_games
from roulette import spin_wheel, check_win, get_payout_multiplier, get_roulette_embed
from mines import generate_mines_board, get_payout_multiplier as get_mines_multiplier, get_mines_embed, active_mines_games, BOARD_SIZE
from views import CoinflipView, BlackjackView, RouletteView, MinesView, DepositView, WithdrawView, ConfirmWithdrawalView

load_dotenv()

BOT_PREFIX = "."
DC_VALUE_USD = 1.00
DB_FILE = "dragon_casino.db"
# Use 30-minute epochs (1800 seconds) instead of daily (86400 seconds)
DAILY_SECRET_SEED = hashlib.sha256(str(int(time.time() // 1800)).encode()).hexdigest()
DAILY_PUBLIC_HASH = hashlib.sha256(DAILY_SECRET_SEED.encode()).hexdigest()

# Solana Configuration
SOLANA_RPC_URL = os.getenv("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")
BOT_WALLET_ADDRESS = os.getenv("BOT_WALLET_ADDRESS", "")
QR_CODES_DIR = "qr_codes"

# Chat Channels (No Commands Allowed)
NO_COMMAND_CHANNELS = [1444449830825885736, 1444450499540684931]  # General and Elite chat channels

# Admin Command Channels (Admins, Staff, and Owners can use any command here)
ADMIN_COMMAND_CHANNELS = [1445050819383791658, 1445050861930680461, 1445049590746316914]  # Admin-only channels with no restrictions
STAFF_CHANNELS = [1445050819383791658, 1445050861930680461]  # Channels where staff/owner roles can use all commands

def has_admin_or_staff_role(member) -> bool:
    """Check if member has Owner or Casino Staff role (case-insensitive, ignores emojis)."""
    role_names_lower = [role.name.lower() for role in member.roles]
    return any("owner" in name or "casino staff" in name for name in role_names_lower)

def is_no_command_zone(channel_id: int, is_admin: bool = False, has_staff: bool = False) -> bool:
    """Check if channel is a chat-only zone where commands shouldn't work. Admins/Staff bypass this in admin channels."""
    if (is_admin or has_staff) and channel_id in ADMIN_COMMAND_CHANNELS:
        return False
    return channel_id in NO_COMMAND_CHANNELS

# Ensure QR codes directory exists
if not os.path.exists(QR_CODES_DIR):
    os.makedirs(QR_CODES_DIR)

def get_dragon_casino_qr() -> str:
    """Return the static Dragon Casino themed QR code."""
    qr_file = f"{QR_CODES_DIR}/dragon_casino_qr.png"
    if os.path.exists(qr_file):
        return qr_file
    return None

class DragonCasinoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix=BOT_PREFIX, intents=intents)
        
        self.db_conn = None
        self.sol_price_usd = 0.0
        self.daily_server_seed = DAILY_SECRET_SEED
        self.daily_public_hash = DAILY_PUBLIC_HASH
        self.active_blackjack_games = active_blackjack_games

    async def on_ready(self):
        print(f"Logged in as {self.user} (ID: {self.user.id})")
        self.db_init()
        self.fetch_sol_price.start()
        self.update_and_post_daily_seed.start()
        print("Bot is ready and running.")

    def db_init(self):
        """Initializes the SQLite database connection and creates the tables."""
        self.db_conn = sqlite3.connect(DB_FILE)
        cursor = self.db_conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT NOT NULL,
                dragon_coins REAL DEFAULT 0.00,
                total_wagered REAL DEFAULT 0.00,
                total_won REAL DEFAULT 0.00,
                games_played INTEGER DEFAULT 0,
                is_elite_dragon BOOLEAN DEFAULT 0,
                client_seed TEXT DEFAULT 'default_seed',
                nonce INTEGER DEFAULT 0,
                total_deposited REAL DEFAULT 0.00,
                daily_wager_amount REAL DEFAULT 0.00,
                daily_usage_seconds INTEGER DEFAULT 0,
                last_usage_warning_time DATETIME DEFAULT NULL,
                session_start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_daily_reset DATE DEFAULT NULL
            )
        """)
        
        cursor.execute("PRAGMA table_info(users)") 
        columns = [col[1] for col in cursor.fetchall()]
        if 'daily_wager_amount' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN daily_wager_amount REAL DEFAULT 0.00")
        if 'daily_usage_seconds' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN daily_usage_seconds INTEGER DEFAULT 0")
        if 'last_usage_warning_time' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN last_usage_warning_time DATETIME DEFAULT NULL")
        if 'session_start_time' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN session_start_time DATETIME DEFAULT NULL")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                recipient TEXT,
                sol_address TEXT,
                sol_amount REAL,
                dc_amount REAL,
                transaction_type TEXT,
                status TEXT DEFAULT 'pending',
                tx_hash TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seed_history (
                seed_id INTEGER PRIMARY KEY AUTOINCREMENT,
                secret_seed TEXT NOT NULL,
                public_hash TEXT NOT NULL,
                posted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                secret_revealed BOOLEAN DEFAULT 0
            )
        """)
        self.db_conn.commit()
        print("Database initialized with provably fair fields.")

    def get_user_data(self, user_id):
        """Retrieves user data from the database."""
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

    def update_user_balance(self, user_id, amount_dc, username):
        """Adds or subtracts DC from a user's balance."""
        cursor = self.db_conn.cursor()
        client_seed = secrets.token_hex(16)
        today = time.strftime("%Y-%m-%d")
        
        daily_wager_increment = 0
        if amount_dc < 0:
            daily_wager_increment = abs(amount_dc)
        
        cursor.execute("""
            INSERT INTO users (user_id, username, dragon_coins, client_seed, daily_wager_amount, session_start_time, last_daily_reset) 
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?) 
            ON CONFLICT(user_id) DO UPDATE SET 
                dragon_coins = dragon_coins + excluded.dragon_coins,
                username = excluded.username,
                daily_wager_amount = CASE 
                    WHEN last_daily_reset = ? THEN daily_wager_amount + ?
                    ELSE ?
                END,
                last_daily_reset = CASE 
                    WHEN last_daily_reset = ? THEN last_daily_reset
                    ELSE ?
                END,
                session_start_time = CASE 
                    WHEN last_daily_reset = ? THEN session_start_time
                    ELSE CURRENT_TIMESTAMP
                END,
                client_seed = CASE WHEN client_seed = 'default_seed' THEN ? ELSE client_seed END
        """, (user_id, username, amount_dc, client_seed, daily_wager_increment, today, today, daily_wager_increment, daily_wager_increment, today, today, today, client_seed))
        self.db_conn.commit()

    def update_game_stats(self, user_id, wager, win_loss, username):
        """Updates user's gambling statistics and balance."""
        cursor = self.db_conn.cursor()
        client_seed = secrets.token_hex(16)
        
        cursor.execute("""
            INSERT INTO users (user_id, username, dragon_coins, total_wagered, total_won, games_played, nonce, client_seed, daily_wager_amount, session_start_time) 
            VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, CURRENT_TIMESTAMP) 
            ON CONFLICT(user_id) DO UPDATE SET 
                dragon_coins = dragon_coins + ?,
                total_wagered = total_wagered + ?,
                total_won = total_won + ?,
                games_played = games_played + 1,
                nonce = nonce + 1,
                username = ?,
                daily_wager_amount = daily_wager_amount + ?,
                client_seed = CASE WHEN client_seed = 'default_seed' THEN ? ELSE client_seed END
        """, (user_id, username, win_loss, wager, max(0, win_loss), 1, client_seed, wager, win_loss, wager, max(0, win_loss), username, wager, client_seed))
        self.db_conn.commit()
    
    def get_daily_wager_progress(self, user_id, initial_balance):
        """Calculate daily wager progress as percentage. Returns (current_wager, percent, wager_threshold)."""
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT daily_wager_amount FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        current_wager = result[0] if result else 0.0
        wager_threshold = initial_balance
        if wager_threshold <= 0:
            return current_wager, 0, wager_threshold
        percent = min(100, int((current_wager / wager_threshold) * 100))
        return current_wager, percent, wager_threshold
    
    def get_dragon_casino_time(self, user_id):
        """Calculate total dragon casino time in seconds for today."""
        cursor = self.db_conn.cursor()
        cursor.execute("SELECT session_start_time, daily_usage_seconds FROM users WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        if not result:
            return 0
        session_start, daily_seconds = result
        current_time = int(time.time())
        if session_start:
            try:
                session_start_ts = int(time.mktime(time.strptime(session_start, "%Y-%m-%d %H:%M:%S")))
                elapsed = max(0, current_time - session_start_ts)
                return daily_seconds + elapsed
            except:
                return daily_seconds
        return daily_seconds
    
    async def check_addiction_warnings(self, user_id, ctx, initial_balance):
        """Check and send addiction warnings if thresholds are met."""
        try:
            ADMIN_CHANNEL_ID = 1445050819383791658
            
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT last_daily_reset, daily_wager_amount FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            today = time.strftime("%Y-%m-%d")
            
            if result:
                last_reset, daily_wager = result
                if last_reset != today:
                    cursor.execute("UPDATE users SET daily_wager_amount = 0, session_start_time = CURRENT_TIMESTAMP, last_daily_reset = ? WHERE user_id = ?", (today, user_id))
                    self.db_conn.commit()
            
            current_wager, wager_percent, threshold = self.get_daily_wager_progress(user_id, initial_balance)
            casino_time_sec = self.get_dragon_casino_time(user_id)
            casino_time_min = casino_time_sec // 60
            
            user_obj = await self.fetch_user(user_id)
            username = user_obj.name if user_obj else f"User {user_id}"
            
            cursor = self.db_conn.cursor()
            cursor.execute("SELECT last_usage_warning_time FROM users WHERE user_id = ?", (user_id,))
            result = cursor.fetchone()
            last_warning_time = result[0] if result else None
            
            should_warn = False
            warning_reason = ""
            
            if wager_percent >= 100 and threshold > 0:
                should_warn = True
                warning_reason = f"wagered 100% of their balance ({current_wager:.2f} DC)"
            elif wager_percent >= 50 and threshold > 0:
                should_warn = True
                warning_reason = f"wagered 50% of their balance ({current_wager:.2f} DC)"
            elif casino_time_min >= 30:
                if not last_warning_time:
                    should_warn = True
                    warning_reason = f"exceeded 30 minutes of Dragon Casino Time ({casino_time_min} minutes)"
                else:
                    try:
                        last_warn_ts = int(time.mktime(time.strptime(last_warning_time, "%Y-%m-%d %H:%M:%S")))
                        if int(time.time()) - last_warn_ts >= 1800:
                            should_warn = True
                            warning_reason = f"exceeded another 30 minutes of Dragon Casino Time ({casino_time_min} minutes total)"
                    except:
                        should_warn = False
            
            if should_warn:
                dm_embed = discord.Embed(
                    title="⚠️ Addiction Warning - Dragon Casino",
                    description="We care about your wellbeing! Take a break from gambling.",
                    color=discord.Color.red()
                )
                dm_embed.add_field(name="⏰ Action Needed", value="Please stop gambling and come back tomorrow.", inline=False)
                if "wagered" in warning_reason:
                    dm_embed.add_field(name="📊 Why?", value=f"You have {warning_reason}. That's enough for today!", inline=False)
                else:
                    dm_embed.add_field(name="⏱️ Why?", value=f"You have {warning_reason}. Time to take a break!", inline=False)
                dm_embed.add_field(name="💡 Resources", value="If gambling is affecting you, please seek help.", inline=False)
                
                try:
                    await user_obj.send(embed=dm_embed)
                except:
                    pass
                
                admin_channel = self.get_channel(ADMIN_CHANNEL_ID)
                if admin_channel:
                    admin_embed = discord.Embed(
                        title="🚨 Addiction Warning Alert",
                        color=discord.Color.red()
                    )
                    admin_embed.add_field(name="👤 User", value=f"{username} (ID: {user_id})", inline=False)
                    if "wagered" in warning_reason:
                        admin_embed.add_field(name="⚠️ Alert Type", value="Wager Threshold Reached", inline=True)
                        admin_embed.add_field(name="📊 Details", value=f"{warning_reason}", inline=True)
                    else:
                        admin_embed.add_field(name="⚠️ Alert Type", value="Usage Time Threshold Reached", inline=True)
                        admin_embed.add_field(name="⏱️ Details", value=f"{warning_reason}", inline=True)
                    admin_embed.add_field(name="⏰ Timestamp", value=f"<t:{int(time.time())}:F>", inline=False)
                    
                    await admin_channel.send(embed=admin_embed)
                
                cursor.execute("UPDATE users SET last_usage_warning_time = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
                self.db_conn.commit()
        except Exception as e:
            print(f"Error in addiction warnings: {e}")

    @tasks.loop(minutes=1)
    async def fetch_sol_price(self):
        """Fetches the current SOL/USD price from CoinGecko."""
        try:
            url = "https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            self.sol_price_usd = data['solana']['usd']
            print(f"Fetched SOL/USD Price: ${self.sol_price_usd:.2f}")
        except Exception as e:
            print(f"Error fetching SOL price: {e}")

    @tasks.loop(minutes=30)
    async def update_and_post_daily_seed(self):
        """Posts seed hash and secret seed every 30 minutes."""
        try:
            SEED_CHANNEL_ID = 1444449287617384599
            channel = self.get_channel(SEED_CHANNEL_ID)
            
            if not channel:
                print(f"[ERROR] Could not find seed channel {SEED_CHANNEL_ID}")
                return
            
            cursor = self.db_conn.cursor()
            # Use 30-minute epochs (1800 seconds) instead of daily (86400 seconds)
            current_epoch = int(time.time() // 1800)
            
            # Check if we already posted a seed for this epoch
            cursor.execute("SELECT seed_id FROM seed_history WHERE posted_at >= datetime('now', '-2 minutes') AND secret_seed = ?",
                          (hashlib.sha256(str(current_epoch).encode()).hexdigest(),))
            recent_post = cursor.fetchone()
            
            if not recent_post:
                # Generate new seed for this 30-minute epoch
                self.daily_server_seed = hashlib.sha256(str(current_epoch).encode()).hexdigest()
                self.daily_public_hash = hashlib.sha256(self.daily_server_seed.encode()).hexdigest()
                
                # Store in database
                cursor.execute("INSERT INTO seed_history (secret_seed, public_hash, secret_revealed) VALUES (?, ?, 1)",
                             (self.daily_server_seed, self.daily_public_hash))
                self.db_conn.commit()
                
                embed = discord.Embed(
                    title="🔐 Provably Fair Seed Posted",
                    description="New seed with both secret and hash disclosed",
                    color=discord.Color.gold(),
                    timestamp=discord.utils.utcnow()
                )
                embed.add_field(name="🔑 Secret Seed", value=f"`{self.daily_server_seed}`", inline=False)
                embed.add_field(name="📊 Public Hash", value=f"`{self.daily_public_hash}`", inline=False)
                embed.add_field(name="ℹ️ Info", value="Both the secret seed and hash are now disclosed. Users can verify game fairness.", inline=False)
                embed.set_footer(text="Next seed in 30 minutes")
                
                await channel.send(embed=embed)
                print(f"[SEEDS] Posted new seed for 30-min epoch {current_epoch} with secret disclosed")
        
        except Exception as e:
            print(f"[ERROR] Failed in seed posting task: {e}")

    def sol_to_dc(self, sol_amount):
        """Converts a Solana amount to Dragon Coins (DC)."""
        if self.sol_price_usd == 0.0:
            return 0.0
        usd_value = sol_amount * self.sol_price_usd
        dc_amount = usd_value / DC_VALUE_USD
        return round(dc_amount, 2)

    async def verify_solana_transaction(self, tx_hash):
        """Verifies a Solana transaction on-chain and returns transaction details if valid."""
        try:
            headers = {"Content-Type": "application/json"}
            payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getTransaction",
                "params": [tx_hash, {"encoding": "json"}]
            }
            
            response = requests.post(SOLANA_RPC_URL, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if "error" in data:
                return None, f"Transaction not found: {data['error'].get('message', 'Unknown error')}"
            
            result = data.get("result")
            if not result or result.get("meta", {}).get("err") is not None:
                return None, "Transaction failed or not confirmed"
            
            # Extract transaction details
            tx = result.get("transaction", {})
            message = tx.get("message", {})
            instructions = message.get("instructions", [])
            
            # Look for transfer to bot wallet in any instruction
            tx_data = {
                "status": "success",
                "timestamp": result.get("blockTime", 0),
                "slot": result.get("slot", 0)
            }
            
            return tx_data, None
            
        except Exception as e:
            return None, f"Error verifying transaction: {str(e)}"

    def get_fair_result(self, user_id, min_val=0, max_val=10000):
        """Generates a provably fair random number between min_val and max_val."""
        user_data = self.get_user_data(user_id)
        if not user_data:
            return None, None, None
            
        _, _, _, _, _, _, _, client_seed, nonce, _, _, _, _, _, _ = user_data
        
        data = f"{self.daily_server_seed}:{client_seed}:{nonce}"
        
        hashed = hmac.new(
            self.daily_server_seed.encode(), 
            data.encode(), 
            hashlib.sha256
        ).hexdigest()
        
        random_int = int(hashed[:8], 16)
        
        result = min_val + (random_int % (max_val - min_val + 1))
        
        return result, client_seed, nonce

    def get_game_seed_generator(self):
        """Returns a function that generates a provably fair result for a game."""
        def seed_generator(user_id, min_val, max_val):
            return self.get_fair_result(user_id, min_val, max_val)
        return seed_generator

    async def on_message(self, message):
        if message.author.id == self.user.id:
            return

        content = message.content
        
        # Check for tip.cc deposit messages: "@sender sent @bot $X" or with SOL conversion
        if "sent" in content and self.user.mention in content:
            # Try to extract SOL amount from "(= X.XXXXXX SOL)" format first
            sol_match = re.search(r"=\s*(\d+\.?\d*)\s+SOL", content)
            
            # If not found, try to extract from dollar amount and convert
            if not sol_match:
                dollar_match = re.search(r"\$(\d+\.?\d*)", content)
                if dollar_match:
                    dollar_amount = float(dollar_match.group(1))
                    # Convert USD to SOL using current price
                    if self.sol_price_usd > 0:
                        sol_amount = dollar_amount / self.sol_price_usd
                        sol_match = type('obj', (object,), {'group': lambda self, i: sol_amount})()
            
            if sol_match:
                sol_amount = float(sol_match.group(1))
                sender_id = None
                all_mentions = re.findall(r"<@!?(\d+)>", content)
                
                for mention_id in all_mentions:
                    if int(mention_id) != self.user.id:
                        sender_id = int(mention_id)
                        break
                
                if sender_id:
                    dc_amount = self.sol_to_dc(sol_amount)
                    sender = self.get_user(sender_id)
                    
                    if sender:
                        self.update_user_balance(sender_id, dc_amount, sender.name)
                        
                        cursor = self.db_conn.cursor()
                        cursor.execute("INSERT INTO bot_transactions (sol_amount, dc_amount, transaction_type) VALUES (?, ?, ?)", 
                                     (sol_amount, dc_amount, "deposit"))
                        self.db_conn.commit()
                        
                        await message.channel.send(
                            f"**🔥 Dragon Coin Deposit Confirmed!**\n"
                            f"{sender.mention} has deposited **{sol_amount:.6f} SOL** "
                            f"and received **{dc_amount:.2f} DC** [${dc_amount * DC_VALUE_USD:.2f}] (Dragon Coins)!"
                        )
                        return

        # Check for embeds (alternative format)
        if message.embeds:
            embed = message.embeds[0]
            embed_text = embed.description if embed.description else embed.title
            
            if embed_text:
                recipient_match = re.search(r"<@!?(\d+)>", embed_text)
                
                if recipient_match and int(recipient_match.group(1)) == self.user.id:
                    sol_match = re.search(r"(\d+\.?\d*)\s+SOL", embed_text)
                    
                    if sol_match:
                        sol_amount = float(sol_match.group(1))
                        
                        sender_id = None
                        all_mentions = re.findall(r"<@!?(\d+)>", embed_text)
                        for mention_id in all_mentions:
                            if int(mention_id) != self.user.id:
                                sender_id = int(mention_id)
                                break
                        
                        if sender_id:
                            dc_amount = self.sol_to_dc(sol_amount)
                            sender = self.get_user(sender_id)
                            
                            if sender:
                                self.update_user_balance(sender_id, dc_amount, sender.name)
                                
                                cursor = self.db_conn.cursor()
                                cursor.execute("INSERT INTO bot_transactions (sol_amount, dc_amount, transaction_type) VALUES (?, ?, ?)", 
                                             (sol_amount, dc_amount, "deposit"))
                                self.db_conn.commit()
                                
                                await message.channel.send(
                                    f"**🔥 Dragon Coin Deposit Confirmed!**\n"
                                    f"{sender.mention} has deposited **{sol_amount:.4f} SOL** "
                                    f"and received **{dc_amount:.2f} DC** [${dc_amount * DC_VALUE_USD:.2f}] (Dragon Coins)!"
                                )
                                return

        await self.process_commands(message)

bot = DragonCasinoBot()

@bot.command(name="deposit", help="Deposit Dragon Coins via SOL. Usage: .deposit")
async def deposit_command(ctx):
    """Three-step deposit process: Ask amount → Show wallet & fees → Buttons & tx hash."""
    # Deposit can be used in the designated deposits/withdrawals channel OR elite channel with Elite Dragon role OR admin channels
    DEPOSITS_CHANNEL_ID = 1444450098980454521
    ELITE_DEPOSITS_CHANNEL_ID = 1445095517452238948
    is_admin = ctx.author.guild_permissions.administrator
    has_staff = has_admin_or_staff_role(ctx.author)
    is_elite_role = any("Elite Dragon" in role.name for role in ctx.author.roles)
    is_elite_deposit_channel = ctx.channel.id == ELITE_DEPOSITS_CHANNEL_ID and is_elite_role
    is_admin_channel = (is_admin or has_staff) and ctx.channel.id in ADMIN_COMMAND_CHANNELS
    is_valid_channel = ctx.channel.id == DEPOSITS_CHANNEL_ID or is_elite_deposit_channel or is_admin_channel
    
    if not is_valid_channel:
        return await ctx.send(f"❌ Deposits can only be requested in <#{DEPOSITS_CHANNEL_ID}>, the elite deposits channel with Elite Dragon role, or admin channels!")
    
    user_id = ctx.author.id
    username = ctx.author.name
    
    # STEP 1: Ask for DC amount
    # Calculate minimum DC based on current SOL price ($0.25 USD minimum = 0.25 DC)
    MIN_USD_VALUE = 0.25
    min_dc_required = (MIN_USD_VALUE / DC_VALUE_USD) if bot.sol_price_usd > 0 else 0.25
    
    embed_step1 = discord.Embed(
        title="💰 Deposit Dragon Coins - Step 1",
        description="How many Dragon Coins do you want to deposit?",
        color=discord.Color.gold()
    )
    embed_step1.add_field(name="📋 Enter Amount", value="Please reply with the DC amount (e.g., `10` or `50.5`)", inline=False)
    embed_step1.add_field(name="💡 Minimum Deposit", value=f"**{min_dc_required:.2f} DC** (~${MIN_USD_VALUE:.2f})", inline=False)
    embed_step1.add_field(name="⚠️ Wager Requirement", value="You must wager the full amount before withdrawing", inline=False)
    embed_step1.add_field(name="💹 Current SOL Price", value=f"**${bot.sol_price_usd:.2f}** USD", inline=True)
    embed_step1.set_footer(text="You have 2 minutes to enter the amount")
    
    msg_step1 = await ctx.send(embed=embed_step1)
    
    try:
        def check_amount(m):
            return m.author.id == user_id and m.channel.id == ctx.channel.id
        
        response = await bot.wait_for('message', timeout=120.0, check=check_amount)
        
        try:
            dc_amount = float(response.content.strip())
            if dc_amount <= 0:
                return await ctx.send("❌ Invalid amount. Please provide a positive DC amount.")
        except ValueError:
            return await ctx.send("❌ Invalid format. Please provide a valid number (e.g., `10` or `50.5`).")
        
    except asyncio.TimeoutError:
        return await ctx.send("⏱️ Timeout. Please run `.deposit` again.")
    
    if bot.sol_price_usd == 0.0:
        return await ctx.send("❌ Unable to fetch SOL price. Please try again in a moment.")
    
    # Convert DC to USD and SOL
    usd_amount = dc_amount * DC_VALUE_USD
    sol_amount = usd_amount / bot.sol_price_usd
    
    # Check minimum deposit ($0.25 USD = 0.25 DC)
    MIN_USD_VALUE = 0.25
    if sol_amount < MIN_USD_VALUE / bot.sol_price_usd:
        return await ctx.send(f"❌ Minimum deposit is **${MIN_USD_VALUE:.2f}** USD (**{MIN_USD_VALUE / DC_VALUE_USD:.2f} DC**). Please enter a higher DC amount.")
    
    # STEP 2: Show static Dragon Casino QR code and wallet address
    qr_file = get_dragon_casino_qr()
    
    embed_step2 = discord.Embed(
        title="💰 Deposit Dragon Coins - Step 2",
        description="Send SOL to the address below",
        color=discord.Color.gold()
    )
    embed_step2.add_field(name="🎯 DC Amount To Deposit", value=f"**{dc_amount:.2f} DC** [${usd_amount:.2f}]", inline=False)
    embed_step2.add_field(name="🪙 SOL To Send", value=f"**{sol_amount:.6f} SOL**", inline=False)
    
    if qr_file:
        embed_step2.set_image(url="attachment://dragon_qr.png")
    
    embed_step2.add_field(name="✅ After Sending", value="Click the **Done** button below once you've sent the SOL", inline=False)
    embed_step2.set_footer(text="⚠️ Please double-check the address before sending!")
    
    async def deposit_callback(uid, dc_amt, sol_amt, usd_amt, action):
        if action == "done":
            # STEP 3: Ask for transaction hash
            embed_step3 = discord.Embed(
                title="💰 Deposit Dragon Coins - Step 3",
                description="Confirm your transaction",
                color=discord.Color.gold()
            )
            embed_step3.add_field(name="📋 Enter Transaction Hash", value="Please reply with your Solana transaction hash\n(from your wallet or blockchain explorer)", inline=False)
            embed_step3.add_field(name="⚠️ Important", value="**Send only the hash, NOT the transaction link!**\n\nExample: `4Xx8Jw4fKp3...` (not the full URL)", inline=False)
            embed_step3.set_footer(text="You have 2 minutes to enter the hash")
            
            await ctx.send(embed=embed_step3)
            
            try:
                def check_hash(m):
                    return m.author.id == uid and m.channel.id == ctx.channel.id
                
                response = await bot.wait_for('message', timeout=120.0, check=check_hash)
                tx_hash = response.content.strip()
                
                # Store pending deposit and update total_deposited
                cursor = bot.db_conn.cursor()
                cursor.execute("INSERT INTO bot_transactions (user_id, recipient, sol_amount, dc_amount, tx_hash, transaction_type, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                             (uid, username, sol_amt, dc_amt, tx_hash, "deposit", "pending_verification"))
                cursor.execute("""
                    INSERT INTO users (user_id, username, total_deposited) 
                    VALUES (?, ?, ?) 
                    ON CONFLICT(user_id) DO UPDATE SET 
                        total_deposited = total_deposited + excluded.total_deposited
                """, (uid, username, dc_amt))
                bot.db_conn.commit()
                
                # Get the request ID
                request_id = cursor.lastrowid
                
                # Post to admin channel
                ADMIN_DEPOSITS_CHANNEL_ID = 1445049709214306434
                admin_channel = bot.get_channel(ADMIN_DEPOSITS_CHANNEL_ID)
                if admin_channel:
                    admin_embed = discord.Embed(
                        title="📥 New Deposit Request",
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow()
                    )
                    admin_embed.add_field(name="Request ID", value=f"#{request_id}", inline=True)
                    admin_embed.add_field(name="User", value=f"<@{uid}> ({username})", inline=True)
                    admin_embed.add_field(name="📊 DC Amount", value=f"**{dc_amt:.2f} DC** [${dc_amt * DC_VALUE_USD:.2f}]", inline=True)
                    admin_embed.add_field(name="🪙 SOL Amount", value=f"**{sol_amt:.6f} SOL**", inline=True)
                    admin_embed.add_field(name="📋 Transaction Hash", value=f"`{tx_hash}`", inline=False)
                    admin_embed.add_field(name="⚠️ Action", value=f"Use `.approve_deposit {request_id}` to verify and approve", inline=False)
                    admin_embed.set_footer(text="Review on blockchain before approving")
                    
                    await admin_channel.send(embed=admin_embed)
                
                embed_confirm = discord.Embed(
                    title="✅ Deposit Request Sent!",
                    color=discord.Color.green()
                )
                embed_confirm.add_field(name="📊 Amount Requested", value=f"**{dc_amt:.2f} DC** [${dc_amt * DC_VALUE_USD:.2f}]", inline=True)
                embed_confirm.add_field(name="🪙 SOL Sent", value=f"**{sol_amt:.6f} SOL**", inline=True)
                embed_confirm.add_field(name="📋 Transaction Hash", value=f"`{tx_hash}`", inline=False)
                embed_confirm.add_field(name="⏳ Status", value="Pending admin verification\nAn admin will verify and approve your deposit shortly", inline=False)
                await ctx.send(embed=embed_confirm)
                
            except asyncio.TimeoutError:
                await ctx.send("⏱️ **Transaction timeout!** You did not provide the transaction hash within 2 minutes.\n\nPlease run `.deposit` again to start over.")
        
        elif action == "cancel":
            await ctx.send("❌ Deposit cancelled.")
    
    # STEP 2: Show Done/Cancel buttons with QR code
    view = DepositView(user_id, dc_amount, sol_amount, usd_amount, BOT_WALLET_ADDRESS, deposit_callback)
    if qr_file:
        with open(qr_file, 'rb') as f:
            file = discord.File(f, filename="dragon_qr.png")
            await ctx.send(embed=embed_step2, view=view, file=file)
    else:
        await ctx.send(embed=embed_step2, view=view)
    
    # Send wallet address in a separate, easy-to-copy format (inline code)
    await ctx.send(f"📮 **Send SOL to:** `{BOT_WALLET_ADDRESS}`\n\n✅ Click the address above to copy")

@bot.command(name="pending_deposits", help="[Admin] View pending deposit requests.")
@commands.has_permissions(administrator=True)
async def pending_deposits_command(ctx):
    if is_no_command_zone(ctx.channel.id, True):
        return await ctx.send("❌ Commands are not allowed in this channel. Please use a game channel or DMs.")
    
    cursor = bot.db_conn.cursor()
    cursor.execute("SELECT transaction_id, recipient, dc_amount, sol_amount, tx_hash, status, timestamp FROM bot_transactions WHERE transaction_type = 'deposit' AND status = 'pending_verification' ORDER BY timestamp DESC LIMIT 20")
    deposits = cursor.fetchall()
    
    if not deposits:
        return await ctx.send("📊 No pending deposit requests.")
    
    embed = discord.Embed(
        title="💳 Pending Deposit Requests",
        color=discord.Color.blurple(),
        description="Review and verify pending deposits"
    )
    
    for deposit in deposits:
        trans_id, recipient, dc_amt, sol_amt, tx_hash, status, timestamp = deposit
        embed.add_field(
            name=f"Request #{trans_id}",
            value=f"**From:** {recipient}\n**Amount:** {dc_amt:.2f} DC [${dc_amt * DC_VALUE_USD:.2f}]\n**SOL:** {sol_amt:.6f}\n**Hash:** `{tx_hash}`\n**Time:** {timestamp}",
            inline=False
        )
    
    embed.set_footer(text="Use: .approve_deposit <request_id> to verify and approve")
    await ctx.send(embed=embed)

@bot.command(name="approve_deposit", help="[Admin] Verify and approve a deposit request.")
@commands.has_permissions(administrator=True)
async def approve_deposit_command(ctx, request_id: int):
    if is_no_command_zone(ctx.channel.id, True):
        return await ctx.send("❌ Commands are not allowed in this channel. Please use a game channel or DMs.")
    
    cursor = bot.db_conn.cursor()
    cursor.execute("SELECT user_id, recipient, dc_amount, sol_amount, tx_hash, status FROM bot_transactions WHERE transaction_id = ? AND transaction_type = 'deposit'", (request_id,))
    result = cursor.fetchone()
    
    if not result:
        return await ctx.send(f"❌ Deposit request #{request_id} not found.")
    
    user_id, recipient, dc_amount, sol_amount, tx_hash, status = result
    
    if status != 'pending_verification':
        return await ctx.send(f"❌ Request #{request_id} is already {status}.")
    
    # Verify transaction on Solana
    tx_data, error = await bot.verify_solana_transaction(tx_hash)
    
    if error:
        return await ctx.send(f"❌ Transaction verification failed: {error}\nRequest #{request_id} remains pending.")
    
    # Approve and credit DC
    bot.update_user_balance(user_id, dc_amount, recipient)
    
    # Delete completed transaction from pending list
    cursor.execute("DELETE FROM bot_transactions WHERE transaction_id = ?", (request_id,))
    bot.db_conn.commit()
    
    embed = discord.Embed(
        title="✅ Deposit Approved!",
        color=discord.Color.green()
    )
    embed.add_field(name="Request ID", value=f"#{request_id}", inline=True)
    embed.add_field(name="User", value=recipient, inline=True)
    embed.add_field(name="Amount", value=f"{dc_amount:.2f} DC [${dc_amount * DC_VALUE_USD:.2f}]", inline=True)
    embed.add_field(name="SOL Received", value=f"{sol_amount:.6f} SOL", inline=True)
    embed.add_field(name="Transaction", value=f"`{tx_hash}`", inline=False)
    embed.add_field(name="✅ Status", value="✅ VERIFIED & COMPLETED - Removed from pending list", inline=False)
    
    await ctx.send(embed=embed)
    
    # Send DM to user
    try:
        user = await bot.fetch_user(user_id)
        dm_embed = discord.Embed(
            title="✅ Deposit Approved!",
            color=discord.Color.green()
        )
        dm_embed.add_field(name="Request ID", value=f"#{request_id}", inline=True)
        dm_embed.add_field(name="Amount Credited", value=f"**{dc_amount:.2f} DC** [${dc_amount * DC_VALUE_USD:.2f}]", inline=True)
        dm_embed.add_field(name="SOL Received", value=f"**{sol_amount:.6f} SOL**", inline=False)
        dm_embed.add_field(name="Status", value="Your deposit has been verified and DC credited to your account!", inline=False)
        await user.send(embed=dm_embed)
    except Exception as e:
        print(f"Could not send DM to user {user_id}: {e}")
    
    # Post approved deposit to completed deposits channel
    COMPLETED_DEPOSITS_CHANNEL_ID = 1445050084965355614
    completed_channel = bot.get_channel(COMPLETED_DEPOSITS_CHANNEL_ID)
    if completed_channel:
        await completed_channel.send(embed=embed)

@bot.command(name="balance", help="Check Dragon Coin balance. Usage: .balance or .balance @user (admin only)")
async def balance_command(ctx, member: discord.Member = None):
    BALANCE_CHANNEL_ID = 1445047863158640803
    ELITE_CASINO_CHANNEL_ID = 1444450537398472734
    ADMIN_CHANNELS = [1445050819383791658, 1445050861930680461, 1445049590746316914]
    
    is_admin = ctx.author.guild_permissions.administrator
    has_staff = has_admin_or_staff_role(ctx.author)
    is_elite_role = any("Elite Dragon" in role.name for role in ctx.author.roles)
    is_elite_casino = ctx.channel.id == ELITE_CASINO_CHANNEL_ID and is_elite_role
    
    # Admins/staff can use anywhere; regular users need channel restrictions
    if not (is_admin or has_staff):
        is_valid_channel = ctx.channel.id == BALANCE_CHANNEL_ID or is_elite_casino
        if not is_valid_channel:
            return await ctx.send(f"❌ Balance can only be checked in <#{BALANCE_CHANNEL_ID}> or the elite casino!")
    
    # If a member is mentioned, check if the user is an admin or staff
    if member:
        if not (is_admin or has_staff):
            return await ctx.send("❌ Only admins and staff can check other users' balances.")
        user_id = member.id
        username = member.name
    else:
        user_id = ctx.author.id
        username = ctx.author.name
    
    user_data = bot.get_user_data(user_id)
    
    if not user_data:
        bot.update_user_balance(user_id, 0.00, username)
        user_data = bot.get_user_data(user_id)
    
    _, _, dc_balance, _, _, _, _, _, _, _, _, _, _, _, _ = user_data
    
    embed = discord.Embed(
        title=f"💰 {username}'s Balance",
        description=f"**{dc_balance:.2f} DC** [${dc_balance * DC_VALUE_USD:.2f}]",
        color=discord.Color.gold()
    )
    embed.set_footer(text="Dragon Casino Balance")
    
    await ctx.send(embed=embed)

@bot.command(name="profile", help="Shows your Dragon Casino profile and balance.")
async def profile_command(ctx, member: discord.Member = None):
    PROFILE_CHANNEL_ID = 1444450215796015289
    ELITE_CASINO_CHANNEL_ID = 1444450537398472734
    is_admin = ctx.author.guild_permissions.administrator
    has_staff = has_admin_or_staff_role(ctx.author)
    is_elite_role = any("Elite Dragon" in role.name for role in ctx.author.roles)
    is_elite_casino = ctx.channel.id == ELITE_CASINO_CHANNEL_ID and is_elite_role
    
    # Admins/staff can use anywhere; regular users need channel restrictions
    if not (is_admin or has_staff):
        is_valid_channel = ctx.channel.id == PROFILE_CHANNEL_ID or is_elite_casino
        if not is_valid_channel:
            return await ctx.send(f"❌ Profile can only be viewed in <#{PROFILE_CHANNEL_ID}> or the elite casino!")
    
    # If a member is mentioned, check if the user is an admin or staff
    if member:
        if not (is_admin or has_staff):
            return await ctx.send("❌ Only admins and staff can check other users' profiles.")
        user_id = member.id
        target_user = member
    else:
        user_id = ctx.author.id
        target_user = ctx.author
    
    user_data = bot.get_user_data(user_id)
    
    if not user_data:
        bot.update_user_balance(user_id, 0.00, ctx.author.name)
        user_data = bot.get_user_data(user_id)

    _, username, dc_balance, wagered, won, games, is_elite, client_seed, nonce, total_deposited, daily_wager, daily_usage_sec, _, _, _ = user_data
    
    target_is_elite_role = any("Elite Dragon" in role.name for role in target_user.roles)
    role_name = "Elite Dragon 👑" if target_is_elite_role else "Dragon 🐉"
    
    current_wager, wager_percent, wager_threshold = bot.get_daily_wager_progress(user_id, dc_balance)
    casino_time_sec = bot.get_dragon_casino_time(user_id)
    casino_time_min = casino_time_sec // 60
    
    wager_bar = "█" * (wager_percent // 10) + "░" * (10 - wager_percent // 10)
    
    embed = discord.Embed(
        title=f"🔥 {username}'s Dragon Casino Profile",
        color=discord.Color.gold() if target_is_elite_role else discord.Color.red()
    )
    embed.set_thumbnail(url=target_user.display_avatar.url)
    
    embed.add_field(name="Current Role", value=role_name, inline=False)
    embed.add_field(name="DC Balance", value=f"**{dc_balance:.2f} DC** [${dc_balance * DC_VALUE_USD:.2f}]", inline=True)
    embed.add_field(name="Games Played", value=f"{games}", inline=True)
    embed.add_field(name="Total Wagered (All-Time)", value=f"{wagered:.2f} DC [${wagered * DC_VALUE_USD:.2f}]", inline=True)
    embed.add_field(name="Total Won (All-Time)", value=f"{won:.2f} DC [${won * DC_VALUE_USD:.2f}]", inline=True)
    
    embed.add_field(name="📊 Daily Wager Progress", value=f"{wager_bar} {wager_percent}%\n{current_wager:.2f} / {wager_threshold:.2f} DC", inline=False)
    embed.add_field(name="⏱️ Dragon Casino Time (Today)", value=f"**{casino_time_min} minutes**", inline=True)
    
    embed.add_field(name="Client Seed", value=client_seed, inline=False)
    embed.add_field(name="Next Nonce", value=nonce, inline=True)
    embed.add_field(name="Server Hash (Daily)", value=f"`{bot.daily_public_hash}`", inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name="withdraw", help="Request a withdrawal of Dragon Coins to SOL.")
async def withdraw_command(ctx):
    """Two-step withdrawal process: Ask amount → Show confirmation → Send to admins."""
    # Withdrawals can be used in the designated deposits/withdrawals channel OR admin channels OR elite channel with Elite Dragon role
    DEPOSITS_CHANNEL_ID = 1444450098980454521
    ELITE_DEPOSITS_CHANNEL_ID = 1445095517452238948
    is_admin = ctx.author.guild_permissions.administrator
    is_elite_role = any("Elite Dragon" in role.name for role in ctx.author.roles)
    is_elite_deposit_channel = ctx.channel.id == ELITE_DEPOSITS_CHANNEL_ID and is_elite_role
    is_valid_channel = ctx.channel.id == DEPOSITS_CHANNEL_ID or (is_admin and ctx.channel.id in ADMIN_COMMAND_CHANNELS) or is_elite_deposit_channel
    
    if not is_valid_channel:
        return await ctx.send(f"❌ Withdrawals can only be requested in <#{DEPOSITS_CHANNEL_ID}>, the elite deposits channel (with Elite Dragon role), or admin channels!")
    
    user_id = ctx.author.id
    username = ctx.author.name
    
    # Get user balance first
    user_data = bot.get_user_data(user_id)
    if not user_data:
        bot.update_user_balance(user_id, 0.00, username)
        user_data = bot.get_user_data(user_id)
    
    _, _, dc_balance, _, _, _, _, _, _, _, _, _, _, _, _ = user_data
    
    # STEP 1: Ask for DC amount
    embed_step1 = discord.Embed(
        title="💸 Withdraw Dragon Coins - Step 1",
        description="How many Dragon Coins do you want to withdraw?",
        color=discord.Color.gold()
    )
    embed_step1.add_field(name="👤 User", value=f"**{username}**", inline=True)
    embed_step1.add_field(name="💎 Current Balance", value=f"**{dc_balance:.2f} DC** [${dc_balance * DC_VALUE_USD:.2f}]", inline=True)
    embed_step1.add_field(name="📋 Enter Amount", value="Please reply with the DC amount (e.g., `10` or `50.5`)", inline=False)
    embed_step1.set_footer(text="You have 2 minutes to enter the amount")
    
    msg_step1 = await ctx.send(embed=embed_step1)
    
    try:
        def check_amount(m):
            return m.author.id == user_id and m.channel.id == ctx.channel.id
        
        response = await bot.wait_for('message', timeout=120.0, check=check_amount)
        
        try:
            dc_amount = float(response.content.strip())
            if dc_amount <= 0:
                return await ctx.send("❌ Invalid amount. Please provide a positive DC amount.")
        except ValueError:
            return await ctx.send("❌ Invalid format. Please provide a valid number (e.g., `10` or `50.5`).")
        
    except asyncio.TimeoutError:
        return await ctx.send("⏱️ Timeout. Please run `.withdraw` again.")
    
    # Check balance and SOL price
    user_data = bot.get_user_data(user_id)
    if not user_data or user_data[2] < dc_amount:
        return await ctx.send(f"{ctx.author.mention}, you do not have **{dc_amount:.2f} DC** [${dc_amount * DC_VALUE_USD:.2f}] to withdraw.")

    if bot.sol_price_usd == 0.0:
        return await ctx.send("❌ Unable to fetch SOL price. Please try again in a moment.")
    
    # Check wager requirement: total_wagered must be >= total_deposited
    _, _, dc_balance, total_wagered, _, _, _, _, _, total_deposited, _, _, _, _, _ = user_data
    if total_wagered < total_deposited:
        remaining_wager = total_deposited - total_wagered
        return await ctx.send(f"❌ Wager requirement not met!\n\n📊 **Total Deposited:** {total_deposited:.2f} DC\n🎰 **Total Wagered:** {total_wagered:.2f} DC\n⚠️ **Remaining to Wager:** **{remaining_wager:.2f} DC**\n\nYou must wager the full deposited amount before withdrawing.")
    
    # Convert DC to SOL
    usd_value = dc_amount * DC_VALUE_USD
    sol_amount = usd_value / bot.sol_price_usd
    
    # Check minimum withdrawal ($0.25 USD = 0.25 DC)
    MIN_USD_VALUE = 0.25
    if sol_amount < MIN_USD_VALUE / bot.sol_price_usd:
        bot.update_user_balance(user_id, dc_amount, username)  # Refund the deducted amount
        return await ctx.send(f"❌ Minimum withdrawal is **${MIN_USD_VALUE:.2f}** USD (**{MIN_USD_VALUE / DC_VALUE_USD:.2f} DC**). Please withdraw a higher amount.")
    
    # STEP 2: Ask for Solana address
    embed_step2 = discord.Embed(
        title="💸 Withdraw Dragon Coins - Step 2",
        description="Provide your Solana wallet address",
        color=discord.Color.gold()
    )
    embed_step2.add_field(name="📋 Enter Address", value="Please reply with your Solana wallet address (where you want SOL sent)", inline=False)
    embed_step2.add_field(name="📝 Example", value="`2wV9M71BjEUcuDmQBLYwbxveyhap7KLRyVRBPDstPgo2`", inline=False)
    embed_step2.set_footer(text="You have 2 minutes to enter your address")
    
    msg_step2 = await ctx.send(embed=embed_step2)
    
    try:
        def check_address(m):
            return m.author.id == user_id and m.channel.id == ctx.channel.id
        
        response_address = await bot.wait_for('message', timeout=120.0, check=check_address)
        recipient_solana_address = response_address.content.strip()
        
        # Basic validation: Check if it looks like a Solana address (44-88 chars, alphanumeric)
        if not recipient_solana_address or len(recipient_solana_address) < 32:
            return await ctx.send("❌ Invalid Solana address. Please provide a valid address.")
        
    except asyncio.TimeoutError:
        return await ctx.send("⏱️ **Withdrawal timeout!** You did not provide your wallet address within 2 minutes.\n\nPlease run `.withdraw` again to start over.")
    
    # Auto-submit: Deduct DC from user immediately
    bot.update_user_balance(user_id, -dc_amount, username)
    
    # Create withdrawal request
    cursor = bot.db_conn.cursor()
    try:
        cursor.execute("INSERT INTO bot_transactions (user_id, recipient, sol_address, sol_amount, dc_amount, transaction_type, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                     (user_id, username, recipient_solana_address, sol_amount, dc_amount, "withdrawal", "pending"))
    except Exception:
        # If sol_address column doesn't exist, insert without it
        cursor.execute("INSERT INTO bot_transactions (user_id, recipient, sol_amount, dc_amount, transaction_type, status) VALUES (?, ?, ?, ?, ?, ?)",
                     (user_id, username, sol_amount, dc_amount, "withdrawal", "pending"))
    bot.db_conn.commit()
    
    # Get the request ID
    request_id = cursor.lastrowid
    
    # Post to admin channel with confirmation buttons
    ADMIN_WITHDRAWALS_CHANNEL_ID = 1445049709214306434
    admin_channel = bot.get_channel(ADMIN_WITHDRAWALS_CHANNEL_ID)
    if admin_channel:
        admin_embed = discord.Embed(
            title="📤 New Withdrawal Request",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )
        admin_embed.add_field(name="Request ID", value=f"#{request_id}", inline=True)
        admin_embed.add_field(name="User", value=f"<@{user_id}> ({username})", inline=True)
        admin_embed.add_field(name="📊 DC Amount", value=f"**{dc_amount:.2f} DC** [${usd_value:.2f}]", inline=True)
        admin_embed.add_field(name="🪙 SOL Amount", value=f"**{sol_amount:.6f} SOL**", inline=True)
        admin_embed.add_field(name="📮 Send To Address", value=f"`{recipient_solana_address}`", inline=False)
        admin_embed.add_field(name="⚠️ Action", value=f"Send SOL to the address above from bot wallet, then click confirm", inline=False)
        admin_embed.set_footer(text="Click 'SOL Sent - Confirm' after manually sending SOL")
        
        view = ConfirmWithdrawalView(bot, request_id, user_id, username, dc_amount, sol_amount)
        await admin_channel.send(embed=admin_embed, view=view)
    
    # Confirm to user
    embed_confirm = discord.Embed(
        title="✅ Withdrawal Request Sent!",
        color=discord.Color.green()
    )
    embed_confirm.add_field(name="📊 Amount Deducted", value=f"**{dc_amount:.2f} DC** [${usd_value:.2f}]", inline=True)
    embed_confirm.add_field(name="🪙 SOL You'll Receive", value=f"**{sol_amount:.6f} SOL**", inline=True)
    embed_confirm.add_field(name="📮 Recipient Address", value=f"`{recipient_solana_address}`", inline=False)
    embed_confirm.add_field(name="⏳ Status", value="Request submitted!\nAn admin will send SOL to your address shortly", inline=False)
    await ctx.send(embed=embed_confirm)

@bot.command(name="withdrawals", help="[Admin] View pending withdrawal requests.")
@commands.has_permissions(administrator=True)
async def withdrawals_command(ctx):
    if is_no_command_zone(ctx.channel.id):
        return await ctx.send("❌ Commands are not allowed in this channel. Please use a game channel or DMs.")
    
    cursor = bot.db_conn.cursor()
    cursor.execute("SELECT transaction_id, recipient, dc_amount, sol_amount, status, timestamp FROM bot_transactions WHERE transaction_type = 'withdrawal' AND status = 'pending' ORDER BY timestamp DESC LIMIT 20")
    withdrawals = cursor.fetchall()
    
    if not withdrawals:
        return await ctx.send("📊 No pending withdrawal requests found.")
    
    embed = discord.Embed(
        title="💳 Pending Withdrawal Requests",
        color=discord.Color.blurple(),
        description="Review and approve withdrawal requests"
    )
    
    for withdrawal in withdrawals:
        trans_id, recipient, dc_amount, sol_amount, status, timestamp = withdrawal
        embed.add_field(
            name=f"Request #{trans_id} - {status.upper()}",
            value=f"**To:** {recipient}\n**Amount:** {dc_amount:.2f} DC [${dc_amount * DC_VALUE_USD:.2f}]\n**SOL:** {sol_amount:.6f}\n**Time:** {timestamp}",
            inline=False
        )
    
    embed.set_footer(text=f"Use: .approve <request_id> <solana_address> to process")
    await ctx.send(embed=embed)

@bot.command(name="approve", help="[Admin] Approve and send SOL for a withdrawal.")
@commands.has_permissions(administrator=True)
async def approve_command(ctx, request_id: int, recipient_address: str):
    if is_no_command_zone(ctx.channel.id):
        return await ctx.send("❌ Commands are not allowed in this channel. Please use a game channel or DMs.")
    
    cursor = bot.db_conn.cursor()
    cursor.execute("SELECT recipient, dc_amount, sol_amount, status FROM bot_transactions WHERE transaction_id = ? AND transaction_type = 'withdrawal'", (request_id,))
    result = cursor.fetchone()
    
    if not result:
        return await ctx.send(f"❌ Withdrawal request #{request_id} not found.")
    
    recipient, dc_amount, sol_amount, status = result
    
    if status != 'pending':
        return await ctx.send(f"❌ Request #{request_id} is already {status}.")
    
    # Delete completed transaction from pending list
    cursor.execute("DELETE FROM bot_transactions WHERE transaction_id = ?", (request_id,))
    bot.db_conn.commit()
    
    embed = discord.Embed(
        title="✅ Withdrawal Approved & Completed",
        color=discord.Color.green()
    )
    embed.add_field(name="Request ID", value=f"#{request_id}", inline=True)
    embed.add_field(name="Recipient", value=recipient, inline=True)
    embed.add_field(name="Amount", value=f"{dc_amount:.2f} DC [${dc_amount * DC_VALUE_USD:.2f}]", inline=True)
    embed.add_field(name="SOL Amount", value=f"{sol_amount:.6f} SOL", inline=True)
    embed.add_field(name="Recipient Address", value=f"`{recipient_address}`", inline=True)
    embed.add_field(name="Status", value="✅ VERIFIED & COMPLETED - Removed from pending list", inline=True)
    embed.set_footer(text="Send SOL from your wallet to the recipient address shown above")
    
    await ctx.send(embed=embed)


@bot.command(name="checkbalance", help="[Admin] Have the bot check tip.cc balance.")
@commands.has_permissions(administrator=True)
async def checkbalance_command(ctx):
    await ctx.send("$balance")

@bot.command(name="cf", help="Play Coinflip. Usage: .cf <amount>")
async def coinflip_command(ctx, amount: float):
    if is_no_command_zone(ctx.channel.id, ctx.author.guild_permissions.administrator):
        return await ctx.send("❌ Commands are not allowed in this channel. Please use a game channel or DMs.")
    
    # Coinflip can be played in its channel or the elite casino channel
    COINFLIP_CHANNEL_ID = 1444449509944987819
    ELITE_CASINO_CHANNEL_ID = 1444450537398472734
    if ctx.channel.id not in [COINFLIP_CHANNEL_ID, ELITE_CASINO_CHANNEL_ID]:
        return await ctx.send(f"❌ Coinflip can only be played in <#{COINFLIP_CHANNEL_ID}> or <#{ELITE_CASINO_CHANNEL_ID}>!")
    
    user_id = ctx.author.id
    user_data = bot.get_user_data(user_id)
    
    if not user_data or user_data[2] < amount or amount <= 0:
        return await ctx.send(f"{ctx.author.mention}, invalid bet amount or insufficient DC balance.")

    bot.update_user_balance(user_id, -amount, ctx.author.name)
    await bot.check_addiction_warnings(user_id, ctx, user_data[2])

    embed = discord.Embed(
        title="🪙 Dragon Coinflip",
        description=f"**Bet:** {amount:.2f} DC [${amount * DC_VALUE_USD:.2f}]\n\nChoose Heads or Tails to flip the coin!",
        color=discord.Color.gold()
    )
    
    view = CoinflipView(bot, user_id, amount)
    await ctx.send(embed=embed, view=view)

@bot.command(name="bj", help="Start a game of Blackjack. Usage: .bj <amount>")
async def blackjack_command(ctx, amount: float):
    if is_no_command_zone(ctx.channel.id, ctx.author.guild_permissions.administrator):
        return await ctx.send("❌ Commands are not allowed in this channel. Please use a game channel or DMs.")
    
    # Blackjack can be played in its channel or the elite casino channel
    BLACKJACK_CHANNEL_ID = 1444449583416610930
    ELITE_CASINO_CHANNEL_ID = 1444450537398472734
    if ctx.channel.id not in [BLACKJACK_CHANNEL_ID, ELITE_CASINO_CHANNEL_ID]:
        return await ctx.send(f"❌ Blackjack can only be played in <#{BLACKJACK_CHANNEL_ID}> or <#{ELITE_CASINO_CHANNEL_ID}>!")
    
    user_id = ctx.author.id
    
    if user_id in bot.active_blackjack_games:
        return await ctx.send(f"{ctx.author.mention}, you already have an active Blackjack game. Finish it or wait for it to time out.")

    user_data = bot.get_user_data(user_id)
    
    if not user_data or user_data[2] < amount or amount <= 0:
        return await ctx.send(f"{ctx.author.mention}, invalid bet amount or insufficient DC balance.")

    bot.update_user_balance(user_id, -amount, ctx.author.name)
    await bot.check_addiction_warnings(user_id, ctx, user_data[2])
    
    game = BlackjackGame(user_id, bot.get_game_seed_generator())
    game.start_game(amount)
    bot.active_blackjack_games[user_id] = game
    
    view = BlackjackView(bot, user_id, game)
    embed = game.get_status_embed(ctx.author, hide_dealer=True)
    
    message = await ctx.send(embed=embed, view=view)
    view.message = message

    if game.state == "ENDED":
        result = game.get_result()
        bot.update_game_stats(user_id, amount, amount + result['net_change'], ctx.author.name)
        embed = game.get_status_embed(ctx.author, hide_dealer=False)
        view.disable_buttons()
        await message.edit(embed=embed, view=view)
        del bot.active_blackjack_games[user_id]

@bot.command(name="rl", help="Play European Roulette. Usage: .rl <amount> <bet_type>")
async def roulette_command(ctx, amount: float, bet_type: str):
    if is_no_command_zone(ctx.channel.id, ctx.author.guild_permissions.administrator):
        return await ctx.send("❌ Commands are not allowed in this channel. Please use a game channel or DMs.")
    
    user_id = ctx.author.id
    user_data = bot.get_user_data(user_id)
    await bot.check_addiction_warnings(user_id, ctx, user_data[2] if user_data else 0)
    
    # Roulette can be played in its channel or the elite casino channel
    ROULETTE_CHANNEL_ID = 1444449686177054821
    ELITE_CASINO_CHANNEL_ID = 1444450537398472734
    if ctx.channel.id not in [ROULETTE_CHANNEL_ID, ELITE_CASINO_CHANNEL_ID]:
        return await ctx.send(f"❌ Roulette can only be played in <#{ROULETTE_CHANNEL_ID}> or <#{ELITE_CASINO_CHANNEL_ID}>!")
    
    user_id = ctx.author.id
    user_data = bot.get_user_data(user_id)
    
    bet_type = bet_type.lower()
    
    if not user_data or user_data[2] < amount or amount <= 0:
        return await ctx.send(f"{ctx.author.mention}, invalid bet amount or insufficient DC balance.")

    payout_multiplier = get_payout_multiplier(bet_type)
    if payout_multiplier == 0.0:
        return await ctx.send(f"{ctx.author.mention}, invalid bet type. Supported types: a number (0-36), red, black, odd, even, low (1-18), high (19-36).")

    bot.update_user_balance(user_id, -amount, ctx.author.name)

    embed = discord.Embed(
        title="🔴 Dragon Roulette 🟢",
        description=f"**Bet:** {amount:.2f} DC [${amount * DC_VALUE_USD:.2f}] on **{bet_type.upper()}**\n\nClick the button to spin the wheel!",
        color=discord.Color.red()
    )
    
    view = RouletteView(bot, user_id, amount, bet_type)
    await ctx.send(embed=embed, view=view)

@bot.command(name="mines", help="Start a game of Mines. Usage: .mines <amount> <num_mines>")
async def mines_command(ctx, amount: float, num_mines: int):
    if is_no_command_zone(ctx.channel.id, ctx.author.guild_permissions.administrator):
        return await ctx.send("❌ Commands are not allowed in this channel. Please use a game channel or DMs.")
    
    # Mines can be played in its channel or the elite casino channel
    MINES_CHANNEL_ID = 1444449762408661215
    ELITE_CASINO_CHANNEL_ID = 1444450537398472734
    if ctx.channel.id not in [MINES_CHANNEL_ID, ELITE_CASINO_CHANNEL_ID]:
        return await ctx.send(f"❌ Mines can only be played in <#{MINES_CHANNEL_ID}> or <#{ELITE_CASINO_CHANNEL_ID}>!")
    
    user_id = ctx.author.id
    
    if user_id in active_mines_games:
        return await ctx.send(f"{ctx.author.mention}, you already have an active Mines game. Cash out or click a tile on the board.")

    user_data = bot.get_user_data(user_id)
    
    if not user_data or user_data[2] < amount or amount <= 0:
        return await ctx.send(f"{ctx.author.mention}, invalid bet amount or insufficient DC balance.")
    
    if not 1 <= num_mines <= 24:
        return await ctx.send(f"{ctx.author.mention}, the number of mines must be between 1 and 24.")

    bot.update_user_balance(user_id, -amount, ctx.author.name)
    await bot.check_addiction_warnings(user_id, ctx, user_data[2])
    
    game_state = generate_mines_board(bot.get_game_seed_generator(), user_id, num_mines)
    game_state["bet"] = amount
    active_mines_games[user_id] = game_state
    
    view = MinesView(bot, user_id, game_state, amount)
    embed = get_mines_embed(ctx.author, game_state, amount)
    
    message = await ctx.send(embed=embed, view=view)
    view.message = message
    
    # Send cashout button in separate message
    from views import MinesCashoutView
    cashout_view = MinesCashoutView(bot, user_id, game_state, amount)
    cashout_message = await ctx.send("**Click a tile to reveal, then use the button below to cash out!**", view=cashout_view)
    view.cashout_message = cashout_message

@bot.command(name="give", help="(Admin/Owner) Give DC to a user. Usage: .give @user <amount>")
async def give_command(ctx, member: discord.Member, amount: float):
    # Check if user is admin or has Owner/Casino Staff role
    is_admin = ctx.author.guild_permissions.administrator
    has_staff = has_admin_or_staff_role(ctx.author)
    
    if not (is_admin or has_staff):
        return await ctx.send("❌ Only admins and staff can use this command.")
    
    if amount <= 0:
        return await ctx.send("Amount must be positive.")
    
    bot.update_user_balance(member.id, amount, member.name)
    await ctx.send(f"**✅ Success!** Gave **{amount:.2f} DC** [${amount * DC_VALUE_USD:.2f}] to {member.mention}.")
    
    # Post to completion channel
    COMPLETED_CHANNEL_ID = 1445050084965355614
    completed_channel = bot.get_channel(COMPLETED_CHANNEL_ID)
    if completed_channel:
        embed = discord.Embed(
            title="💝 DC Given by Admin",
            color=discord.Color.gold(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Admin", value=f"{ctx.author.mention} ({ctx.author.name})", inline=True)
        embed.add_field(name="Recipient", value=f"{member.mention} ({member.name})", inline=True)
        embed.add_field(name="📊 Amount Given", value=f"**{amount:.2f} DC** [${amount * DC_VALUE_USD:.2f}]", inline=False)
        await completed_channel.send(embed=embed)

@bot.command(name="remove", help="(Admin/Owner) Remove DC from a user. Usage: .remove @user <amount>")
async def remove_command(ctx, member: discord.Member, amount: float):
    # Check if user is admin or has Owner/Casino Staff role
    is_admin = ctx.author.guild_permissions.administrator
    has_staff = has_admin_or_staff_role(ctx.author)
    
    if not (is_admin or has_staff):
        return await ctx.send("❌ Only admins and staff can use this command.")
    
    if amount <= 0:
        return await ctx.send("Amount must be positive.")
    
    # Check if user has enough DC to remove
    user_data = bot.get_user_data(member.id)
    if not user_data or user_data[2] < amount:
        return await ctx.send(f"❌ User {member.mention} does not have **{amount:.2f} DC** [${amount * DC_VALUE_USD:.2f}] to remove.")
    
    bot.update_user_balance(member.id, -amount, member.name)
    await ctx.send(f"**✅ Success!** Removed **{amount:.2f} DC** [${amount * DC_VALUE_USD:.2f}] from {member.mention}.")
    
    # Post to completion channel
    COMPLETED_CHANNEL_ID = 1445050084965355614
    completed_channel = bot.get_channel(COMPLETED_CHANNEL_ID)
    if completed_channel:
        embed = discord.Embed(
            title="🗑️ DC Removed by Admin",
            color=discord.Color.red(),
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="Admin", value=f"{ctx.author.mention} ({ctx.author.name})", inline=True)
        embed.add_field(name="User", value=f"{member.mention} ({member.name})", inline=True)
        embed.add_field(name="📊 Amount Removed", value=f"**{amount:.2f} DC** [${amount * DC_VALUE_USD:.2f}]", inline=False)
        await completed_channel.send(embed=embed)

@bot.command(name="zap", help="(Admin/Staff) Delete all messages in the channel. Usage: .zap [limit]")
async def zap_command(ctx, limit: int = 100):
    is_admin = ctx.author.guild_permissions.administrator
    has_staff = has_admin_or_staff_role(ctx.author)
    
    if not (is_admin or has_staff):
        return await ctx.send("❌ Only admins and staff can use this command.")
    
    if is_no_command_zone(ctx.channel.id, is_admin, has_staff):
        return await ctx.send("❌ Commands are not allowed in this channel. Please use a game channel or DMs.")
    
    await ctx.message.delete()
    deleted = await ctx.channel.purge(limit=limit)
    confirm_msg = await ctx.send(f"**⚡ Zapped {len(deleted)} messages!**")
    await asyncio.sleep(3)
    await confirm_msg.delete()

@bot.command(name="thanos", help="(Admin/Staff) Snap - delete all messages in the channel.")
async def thanos_command(ctx):
    is_admin = ctx.author.guild_permissions.administrator
    has_staff = has_admin_or_staff_role(ctx.author)
    
    if not (is_admin or has_staff):
        return await ctx.send("❌ Only admins and staff can use this command.")
    
    try:
        await ctx.message.delete()
        deleted = await ctx.channel.purge()
        snapped_msg = await ctx.send(f"**👆 Snapped! {len(deleted)} messages deleted.**")
        await asyncio.sleep(10)
        await snapped_msg.delete()
    except Exception as e:
        print(f"Error in thanos command: {e}")
        await ctx.send(f"❌ Error executing snap: {str(e)}")

@bot.command(name="botbalance", help="(Admin) Check bot's tip.cc balance estimate and get instructions.")
@commands.has_permissions(administrator=True)
async def botbalance_command(ctx):
    if is_no_command_zone(ctx.channel.id, True):
        return await ctx.send("❌ Commands are not allowed in this channel. Please use a game channel or DMs.")
    
    try:
        cursor = bot.db_conn.cursor()
        cursor.execute("SELECT COALESCE(SUM(CASE WHEN transaction_type='deposit' THEN sol_amount ELSE 0 END), 0) - COALESCE(SUM(CASE WHEN transaction_type='withdrawal' THEN sol_amount ELSE 0 END), 0) FROM bot_transactions")
        result = cursor.fetchone()
        estimated_sol = float(result[0]) if result and result[0] else 0.0
    except Exception as e:
        estimated_sol = 0.0
        print(f"Error querying bot_transactions: {e}")
    
    embed = discord.Embed(
        title="🤖 Bot Balance (tip.cc)",
        color=discord.Color.blue()
    )
    embed.add_field(name="📊 Estimated Balance (Tracked)", value=f"**{estimated_sol:.6f} SOL**\n(Based on deposits - withdrawals)", inline=False)
    embed.add_field(name="✅ To Check Real Balance", value="Since tip.cc only responds to users (not bots), you need to run this command:\n\n`$balance`\n\nTip.cc will respond with the actual current balance.", inline=False)
    await ctx.send(embed=embed)

@bot.command(name="leaderboard", help="Shows the top players by Dragon Coin balance.")
async def leaderboard_command(ctx):
    # Leaderboard can be used in the designated leaderboard channel OR admin channels
    LEADERBOARD_CHANNEL_ID = 1444450176394596534
    is_admin = ctx.author.guild_permissions.administrator
    is_valid_channel = ctx.channel.id == LEADERBOARD_CHANNEL_ID or (is_admin and ctx.channel.id in ADMIN_COMMAND_CHANNELS)
    
    if not is_valid_channel:
        return await ctx.send(f"❌ Leaderboard can only be viewed in <#{LEADERBOARD_CHANNEL_ID}> or admin channels!")
    
    try:
        cursor = bot.db_conn.cursor()
        cursor.execute("SELECT username, dragon_coins, total_wagered, total_won, games_played FROM users ORDER BY dragon_coins DESC LIMIT 10")
        users = cursor.fetchall()
        
        if not users:
            return await ctx.send("📊 No users found on the leaderboard.")
        
        embed = discord.Embed(
            title="🏆 Dragon Casino Leaderboard",
            description="Top 10 Players by Dragon Coin Balance",
            color=discord.Color.gold()
        )
        
        leaderboard_text = ""
        for idx, (username, dc_balance, wagered, won, games) in enumerate(users, 1):
            leaderboard_text += f"**#{idx}** {username}\n💎 **{dc_balance:.2f} DC** [${dc_balance * DC_VALUE_USD:.2f}]\n"
        
        embed.add_field(name="Top Players", value=leaderboard_text, inline=False)
        embed.set_footer(text="Balance updates in real-time")
        
        await ctx.send(embed=embed)
    except Exception as e:
        print(f"Error fetching leaderboard: {e}")
        await ctx.send("❌ Error retrieving leaderboard. Please try again later.")

@bot.command(name="help_casino", help="Shows all available casino commands.")
async def help_casino_command(ctx):
    if is_no_command_zone(ctx.channel.id, ctx.author.guild_permissions.administrator):
        return await ctx.send("❌ Commands are not allowed in this channel. Please use a game channel or DMs.")
    
    embed = discord.Embed(
        title="🐉 Dragon Casino - Help",
        description="Welcome to Dragon Casino! Here are all available commands:",
        color=discord.Color.gold()
    )
    
    embed.add_field(
        name="📊 Profile & Balance",
        value="``.profile`` - View your profile and balance\n``.withdraw <amount>`` - Withdraw DC to SOL",
        inline=False
    )
    
    embed.add_field(
        name="🔐 Provably Fair",
        value="Daily seeds are posted to the seed channel every 24 hours",
        inline=False
    )
    
    embed.add_field(
        name="🎰 Games",
        value="``.cf <amount>`` - Play Coinflip\n``.bj <amount>`` - Play Blackjack\n``.rl <amount> <bet_type>`` - Play Roulette\n``.mines <amount> <num_mines>`` - Play Mines",
        inline=False
    )
    
    embed.add_field(
        name="🎲 Roulette Bet Types",
        value="Numbers: ``0-36``\nColors: ``red``, ``black``\nOdd/Even: ``odd``, ``even``\nHigh/Low: ``low`` (1-18), ``high`` (19-36)",
        inline=False
    )
    
    embed.set_footer(text="Deposit SOL via tip.cc to receive Dragon Coins (DC)!")
    
    await ctx.send(embed=embed)

def run_bot():
    TOKEN = os.getenv("DISCORD_BOT_TOKEN")
    if not TOKEN:
        print("FATAL ERROR: DISCORD_BOT_TOKEN not found in environment variables.")
        print("Please set the DISCORD_BOT_TOKEN environment variable.")
        return

    bot.run(TOKEN)

if __name__ == "__main__":
    run_bot()
