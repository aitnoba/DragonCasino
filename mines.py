import random
import discord
import math

DC_VALUE_USD = 1.00

BOARD_SIZE = 25

def get_payout_multiplier(mines_count, clicks_safe):
    """
    Calculates the payout multiplier for the Mines game.
    The house edge is baked into the multiplier calculation.
    """
    
    if clicks_safe == 0:
        return 0.0
        
    theoretical_multiplier = 1.0
    for i in range(clicks_safe):
        prob_safe = (BOARD_SIZE - mines_count - i) / (BOARD_SIZE - i)
        multiplier_step = 1.0 / prob_safe
        theoretical_multiplier *= multiplier_step
        
    house_edge_multiplier = theoretical_multiplier * 0.95
    
    return round(house_edge_multiplier, 2)

def generate_mines_board(seed_generator, user_id, mines_count):
    """Generates a provably fair board with mines."""
    
    if not 1 <= mines_count <= 24:
        raise ValueError("Mines count must be between 1 and 24.")
        
    result_num, client_seed, nonce = seed_generator(user_id, 0, 1000000000)
    
    temp_random = random.Random(result_num)
    
    all_tiles = list(range(BOARD_SIZE))
    
    mine_positions = temp_random.sample(all_tiles, mines_count)
    
    return {
        "mine_positions": set(mine_positions),
        "client_seed": client_seed,
        "nonce": nonce,
        "mines_count": mines_count,
        "safe_clicks": 0,
        "board_state": ['❓'] * BOARD_SIZE
    }

def get_mines_embed(user, game_state, bet_amount, net_change=None, final=False):
    """Generates the Mines game embed."""
    
    board_display = ""
    for i in range(BOARD_SIZE):
        board_display += game_state["board_state"][i]
        if (i + 1) % 5 == 0:
            board_display += "\n"
        else:
            board_display += " "
            
    if final:
        if net_change > 0:
            title = "🎉 WINNER! You cashed out!"
            color = discord.Color.green()
        else:
            title = "💥 BOOM! You hit a mine!"
            color = discord.Color.red()
    else:
        title = "⛏️ Dragon Mines - Your Turn"
        color = discord.Color.gold()
        
    embed = discord.Embed(
        title=title,
        description=f"**Mines:** {game_state['mines_count']} | **Bet:** {bet_amount:.2f} DC [${bet_amount * DC_VALUE_USD:.2f}]",
        color=color
    )
    
    embed.add_field(name="Board (Click a tile 1-25)", value=f"```\n{board_display}```", inline=False)
    embed.add_field(name="Safe Clicks", value=game_state["safe_clicks"], inline=True)
    
    if game_state["safe_clicks"] > 0:
        current_multiplier = get_payout_multiplier(game_state["mines_count"], game_state["safe_clicks"])
        payout = bet_amount * current_multiplier
        embed.add_field(name="Current Payout", value=f"{payout:.2f} DC [${payout * DC_VALUE_USD:.2f}] ({current_multiplier:.2f}x)", inline=True)
        
    if final:
        embed.add_field(name="Net Change", value=f"{net_change:+.2f} DC [${net_change * DC_VALUE_USD:+.2f}]", inline=True)
        embed.add_field(name="Next Nonce", value=game_state["nonce"] + 1, inline=True)
        embed.add_field(name="Provably Fair", value=f"Client Seed: `{game_state['client_seed']}`\nNonce: `{game_state['nonce']}`", inline=False)
        
    return embed

active_mines_games = {}
