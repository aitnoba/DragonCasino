import discord
from discord.ui import View, Button
from mines import get_payout_multiplier as get_mines_multiplier, get_mines_embed, BOARD_SIZE, active_mines_games
from blackjack import BlackjackGame, active_blackjack_games
from roulette import spin_wheel, check_win, get_payout_multiplier as get_roulette_multiplier, get_roulette_embed

DC_VALUE_USD = 1.00

class DepositView(View):
    def __init__(self, user_id, dc_amount, sol_amount, usd_amount, wallet_address, callback, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.dc_amount = dc_amount
        self.sol_amount = sol_amount
        self.usd_amount = usd_amount
        self.wallet_address = wallet_address
        self.callback = callback
        self.result = None

    @discord.ui.button(label="✅ Done - I Sent SOL", style=discord.ButtonStyle.success)
    async def done_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your deposit!", ephemeral=True)
        
        self.result = "done"
        await interaction.response.defer()
        await self.callback(self.user_id, self.dc_amount, self.sol_amount, self.usd_amount, "done")
        self.stop()

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your deposit!", ephemeral=True)
        
        self.result = "cancel"
        await interaction.response.defer()
        await self.callback(self.user_id, self.dc_amount, self.sol_amount, self.usd_amount, "cancel")
        self.stop()

class WithdrawView(View):
    def __init__(self, user_id, dc_amount, sol_amount, usd_amount, solana_address, callback, timeout=300):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.dc_amount = dc_amount
        self.sol_amount = sol_amount
        self.usd_amount = usd_amount
        self.solana_address = solana_address
        self.callback = callback
        self.result = None

    @discord.ui.button(label="✅ Confirm Withdrawal", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your withdrawal!", ephemeral=True)
        
        self.result = "confirm"
        await interaction.response.defer()
        await self.callback(self.user_id, self.dc_amount, self.sol_amount, self.usd_amount, self.solana_address, "confirm")
        self.stop()

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your withdrawal!", ephemeral=True)
        
        self.result = "cancel"
        await interaction.response.defer()
        await self.callback(self.user_id, self.dc_amount, self.sol_amount, self.usd_amount, self.solana_address, "cancel")
        self.stop()

class ConfirmWithdrawalView(View):
    """View for admin to confirm withdrawal completion after manually sending SOL."""
    def __init__(self, bot, request_id, user_id, username, dc_amount, sol_amount, timeout=300):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.request_id = request_id
        self.user_id = user_id
        self.username = username
        self.dc_amount = dc_amount
        self.sol_amount = sol_amount

    @discord.ui.button(label="✅ SOL Sent - Confirm", style=discord.ButtonStyle.success)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Only admins can use this button!", ephemeral=True)
        
        await interaction.response.defer()
        
        # Mark as completed
        cursor = self.bot.db_conn.cursor()
        cursor.execute("UPDATE bot_transactions SET status = ? WHERE transaction_id = ?", ("completed", self.request_id))
        self.bot.db_conn.commit()
        
        # Send DM to user
        try:
            user = await self.bot.fetch_user(self.user_id)
            dm_embed = discord.Embed(
                title="✅ Withdrawal Completed!",
                color=discord.Color.green()
            )
            dm_embed.add_field(name="Request ID", value=f"#{self.request_id}", inline=True)
            dm_embed.add_field(name="📊 Amount Sent", value=f"**{self.sol_amount:.6f} SOL**", inline=True)
            dm_embed.add_field(name="💎 DC Withdrawn", value=f"**{self.dc_amount:.2f} DC** [${self.dc_amount * DC_VALUE_USD:.2f}]", inline=False)
            dm_embed.add_field(name="Status", value="Your withdrawal has been processed and SOL sent to your wallet!", inline=False)
            await user.send(embed=dm_embed)
        except Exception as e:
            print(f"Could not send DM to user {self.user_id}: {e}")
        
        # Post to completed channel
        COMPLETED_WITHDRAWALS_CHANNEL_ID = 1445050084965355614  # Completed withdrawals channel
        completed_channel = self.bot.get_channel(COMPLETED_WITHDRAWALS_CHANNEL_ID)
        if completed_channel:
            completed_embed = discord.Embed(
                title="✅ Withdrawal Completed",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow()
            )
            completed_embed.add_field(name="Request ID", value=f"#{self.request_id}", inline=True)
            completed_embed.add_field(name="User", value=f"<@{self.user_id}> ({self.username})", inline=True)
            completed_embed.add_field(name="📊 DC Withdrawn", value=f"**{self.dc_amount:.2f} DC** [${self.dc_amount * DC_VALUE_USD:.2f}]", inline=True)
            completed_embed.add_field(name="🪙 SOL Sent", value=f"**{self.sol_amount:.6f} SOL**", inline=True)
            await completed_channel.send(embed=completed_embed)
        
        await interaction.followup.send(f"✅ Withdrawal request #{self.request_id} marked as completed. User notified via DM.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.danger)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("Only admins can use this button!", ephemeral=True)
        
        await interaction.response.defer()
        await interaction.followup.send(f"❌ Cancelled. Withdrawal request #{self.request_id} remains pending.", ephemeral=True)
        self.stop()

class MinesCashoutView(View):
    """Separate view for cashout button."""
    def __init__(self, bot, user_id, game_state, bet_amount, timeout=180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user_id = user_id
        self.game_state = game_state
        self.bet_amount = bet_amount
        
        cashout_button = Button(label="💰 Cash Out", style=discord.ButtonStyle.success, custom_id="mines_cashout")
        cashout_button.callback = self.cashout_callback
        self.add_item(cashout_button)
    
    async def cashout_callback(self, interaction: discord.Interaction):
        """Handles the cashout button click."""
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        if self.game_state["safe_clicks"] == 0:
            return await interaction.response.send_message("You must click at least one tile before cashing out.", ephemeral=True)

        multiplier = get_mines_multiplier(self.game_state["mines_count"], self.game_state["safe_clicks"])
        win_amount = self.bet_amount * multiplier
        net_change = win_amount
        
        for mine_pos in self.game_state["mine_positions"]:
            if self.game_state["board_state"][mine_pos] == '❓':
                self.game_state["board_state"][mine_pos] = '💥'
        
        self.bot.update_game_stats(self.user_id, self.bet_amount, net_change, interaction.user.name)
        del active_mines_games[self.user_id]
        self.stop()
        
        for item in self.children:
            item.disabled = True
            
        embed = get_mines_embed(interaction.user, self.game_state, self.bet_amount, win_amount - self.bet_amount, final=True)
        await interaction.response.edit_message(embed=embed, view=self)

class MinesView(View):
    def __init__(self, bot, user_id, game_state, bet_amount, timeout=180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user_id = user_id
        self.game_state = game_state
        self.bet_amount = bet_amount
        self.cashout_message = None
        self.create_buttons()

    def create_buttons(self):
        """Creates the 5x5 grid of tile buttons only (25 items max)."""
        self.clear_items()
        
        for i in range(BOARD_SIZE):
            tile_number = i + 1
            tile_symbol = self.game_state["board_state"][i]
            
            is_disabled = (tile_symbol != '❓')
            
            button = Button(
                label=str(tile_number),
                style=discord.ButtonStyle.secondary if not is_disabled else discord.ButtonStyle.grey,
                custom_id=f"mines_tile_{tile_number}",
                disabled=is_disabled,
                row=i // 5
            )
            button.callback = self.tile_callback
            self.add_item(button)

    async def tile_callback(self, interaction: discord.Interaction):
        """Handles a tile click."""
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        tile_number = int(interaction.data["custom_id"].split("_")[-1])
        tile_index = tile_number - 1
        
        if self.game_state["board_state"][tile_index] != '❓':
            return await interaction.response.send_message("This tile has already been clicked.", ephemeral=True)

        if tile_index in self.game_state["mine_positions"]:
            self.game_state["board_state"][tile_index] = '💥'
            net_change = 0.0
            
            for mine_pos in self.game_state["mine_positions"]:
                self.game_state["board_state"][mine_pos] = '💥'
            
            self.bot.update_game_stats(self.user_id, self.bet_amount, net_change, interaction.user.name)
            del active_mines_games[self.user_id]
            self.stop()
            
            self.create_buttons()
            for item in self.children:
                item.disabled = True
            
            embed = get_mines_embed(interaction.user, self.game_state, self.bet_amount, self.bet_amount * -1, final=True)
            await interaction.response.edit_message(embed=embed, view=self)
            
            # Disable cashout button too
            if self.cashout_message:
                try:
                    await self.cashout_message.edit(view=MinesCashoutView(self.bot, self.user_id, self.game_state, self.bet_amount))
                    # Disable all items in the new view
                    for view_item in await self.cashout_message.channel.fetch_message(self.cashout_message.id):
                        view_item.disabled = True
                except:
                    pass
            
        else:
            self.game_state["board_state"][tile_index] = '💎'
            self.game_state["safe_clicks"] += 1
            
            self.create_buttons()
            
            embed = get_mines_embed(interaction.user, self.game_state, self.bet_amount)
            await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        """Handles game timeout."""
        if self.user_id in active_mines_games:
            del active_mines_games[self.user_id]
            
            self.create_buttons()
            for item in self.children:
                item.disabled = True
                
            channel = self.bot.get_channel(self.message.channel.id)
            if channel:
                await self.message.edit(content=f"**{self.message.author.mention}**, your Mines game timed out. Your bet of **{self.bet_amount:.2f} DC** [${self.bet_amount * DC_VALUE_USD:.2f}] has been lost.", view=self)

class BlackjackView(View):
    def __init__(self, bot, user_id, game: BlackjackGame, timeout=180):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user_id = user_id
        self.game = game
        
        self.hit_button = Button(label="Hit", style=discord.ButtonStyle.success, custom_id="bj_hit")
        self.stand_button = Button(label="Stand", style=discord.ButtonStyle.danger, custom_id="bj_stand")
        
        self.hit_button.callback = self.hit_callback
        self.stand_button.callback = self.stand_callback
        
        self.add_item(self.hit_button)
        self.add_item(self.stand_button)

    def disable_buttons(self):
        self.hit_button.disabled = True
        self.stand_button.disabled = True

    async def hit_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        status = self.game.hit()
        
        if status in ["BUST", "STAND"]:
            self.disable_buttons()
            self.stop()
            
            if status == "STAND":
                self.game.stand()
            
            result = self.game.get_result()
            self.bot.update_game_stats(self.user_id, self.game.bet, self.game.bet + result['net_change'], interaction.user.name)
            del active_blackjack_games[self.user_id]
            
            embed = self.game.get_status_embed(interaction.user, hide_dealer=False)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            embed = self.game.get_status_embed(interaction.user, hide_dealer=True)
            await interaction.response.edit_message(embed=embed, view=self)

    async def stand_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        self.disable_buttons()
        self.stop()
        
        self.game.stand()
        
        result = self.game.get_result()
        self.bot.update_game_stats(self.user_id, self.game.bet, self.game.bet + result['net_change'], interaction.user.name)
        del active_blackjack_games[self.user_id]
        
        embed = self.game.get_status_embed(interaction.user, hide_dealer=False)
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        if self.user_id in active_blackjack_games:
            del active_blackjack_games[self.user_id]
            self.disable_buttons()
            channel = self.bot.get_channel(self.message.channel.id)
            if channel:
                await self.message.edit(content=f"**{self.message.author.mention}**, your Blackjack game timed out. Your bet of **{self.game.bet:.2f} DC** has been lost.", view=self)

class CoinflipView(View):
    def __init__(self, bot, user_id, bet_amount, timeout=60):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user_id = user_id
        self.bet_amount = bet_amount
        
        self.heads_button = Button(label="Heads (H)", style=discord.ButtonStyle.primary, custom_id="cf_heads")
        self.tails_button = Button(label="Tails (T)", style=discord.ButtonStyle.primary, custom_id="cf_tails")
        
        self.heads_button.callback = self.flip_callback
        self.tails_button.callback = self.flip_callback
        
        self.add_item(self.heads_button)
        self.add_item(self.tails_button)

    def disable_buttons(self):
        self.heads_button.disabled = True
        self.tails_button.disabled = True

    async def flip_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        user_side = "heads" if interaction.data["custom_id"] == "cf_heads" else "tails"
        
        result_num, client_seed, nonce = self.bot.get_fair_result(self.user_id, 0, 9999)
        
        winning_side = "heads" if result_num < 5000 else "tails"
        
        win_amount = 0.0
        
        if user_side == winning_side:
            win_amount = self.bet_amount * 1.9
            net_change = win_amount
            result_text = f"**🎉 WINNER!** The coin landed on **{winning_side.upper()}**."
            color = discord.Color.green()
        else:
            net_change = 0.0
            result_text = f"**💔 LOSER!** The coin landed on **{winning_side.upper()}**."
            color = discord.Color.red()

        self.bot.update_game_stats(self.user_id, self.bet_amount, net_change, interaction.user.name)
        
        embed = discord.Embed(
            title="🪙 Coinflip Result",
            description=result_text,
            color=color
        )
        embed.add_field(name="Bet", value=f"{self.bet_amount:.2f} DC on {user_side.upper()}", inline=True)
        embed.add_field(name="Payout", value=f"{win_amount:.2f} DC", inline=True)
        embed.add_field(name="Net Change", value=f"{win_amount - self.bet_amount:+.2f} DC", inline=True)
        embed.add_field(name="Next Nonce", value=nonce + 1, inline=True)
        embed.add_field(name="Result Hash", value=f"Result: {result_num}", inline=True)
        
        self.disable_buttons()
        self.stop()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        self.disable_buttons()
        if hasattr(self, 'message') and self.message:
            channel = self.bot.get_channel(self.message.channel.id)
            if channel:
                try:
                    await self.message.edit(content=f"**Coinflip bet of {self.bet_amount:.2f} DC timed out and has been lost.**", view=self)
                except:
                    pass

class RouletteView(View):
    def __init__(self, bot, user_id, bet_amount, bet_type, timeout=60):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user_id = user_id
        self.bet_amount = bet_amount
        self.bet_type = bet_type
        
        self.spin_button = Button(label="Spin the Wheel 🐉", style=discord.ButtonStyle.primary, custom_id="rl_spin")
        self.spin_button.callback = self.spin_callback
        self.add_item(self.spin_button)

    def disable_buttons(self):
        self.spin_button.disabled = True

    async def spin_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your game!", ephemeral=True)

        payout_multiplier = get_roulette_multiplier(self.bet_type)
        
        spin_result = spin_wheel(self.bot.get_game_seed_generator(), self.user_id)
        
        if check_win(spin_result, self.bet_type):
            win_amount = self.bet_amount * payout_multiplier
            net_change = win_amount
        else:
            win_amount = 0.0
            net_change = 0.0

        self.bot.update_game_stats(self.user_id, self.bet_amount, net_change, interaction.user.name)
        
        embed = get_roulette_embed(interaction.user, spin_result, self.bet_amount, self.bet_type, win_amount - self.bet_amount)
        
        self.disable_buttons()
        self.stop()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        self.disable_buttons()
        channel = self.bot.get_channel(self.message.channel.id)
        if channel:
            await self.message.edit(content=f"**{self.message.author.mention}**, your Roulette bet of **{self.bet_amount:.2f} DC** timed out and has been lost.", view=self)
