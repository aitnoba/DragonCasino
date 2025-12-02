import random
import discord

DC_VALUE_USD = 1.00

ROULETTE_NUMBERS = list(range(37))
ROULETTE_COLORS = {
    0: "green",
    **{i: "red" for i in range(1, 11) if i % 2 != 0},
    **{i: "black" for i in range(1, 11) if i % 2 == 0},
    **{i: "black" for i in range(11, 19) if i % 2 != 0},
    **{i: "red" for i in range(11, 19) if i % 2 == 0},
    **{i: "red" for i in range(19, 29) if i % 2 != 0},
    **{i: "black" for i in range(19, 29) if i % 2 == 0},
    **{i: "black" for i in range(29, 37) if i % 2 != 0},
    **{i: "red" for i in range(29, 37) if i % 2 == 0},
}

PAYOUTS = {
    "single": 34.0,
    "split": 16.5,
    "street": 11.0,
    "corner": 8.0,
    "six_line": 5.0,
    "column_dozen": 2.0,
    "even_money": 1.0,
}

def get_payout_multiplier(bet_type):
    """Returns the payout multiplier for a winning bet type."""
    if bet_type in ["red", "black", "odd", "even", "low", "high"]:
        return PAYOUTS["even_money"] + 1.0
    elif bet_type in ["col1", "col2", "col3", "doz1", "doz2", "doz3"]:
        return PAYOUTS["column_dozen"] + 1.0
    elif bet_type.isdigit() and 0 <= int(bet_type) <= 36:
        return PAYOUTS["single"] + 1.0
    else:
        return 0.0

def check_win(spin_result, bet_type):
    """Checks if a bet wins based on the spin result."""
    spin_number = spin_result["number"]
    spin_color = spin_result["color"]
    
    bet_type = bet_type.lower()
    
    if bet_type.isdigit():
        return int(bet_type) == spin_number
    
    if spin_number == 0:
        return False
        
    if bet_type == "red":
        return spin_color == "red"
    elif bet_type == "black":
        return spin_color == "black"
    elif bet_type == "odd":
        return spin_number % 2 != 0
    elif bet_type == "even":
        return spin_number % 2 == 0
    elif bet_type == "low":
        return 1 <= spin_number <= 18
    elif bet_type == "high":
        return 19 <= spin_number <= 36
        
    return False

def spin_wheel(seed_generator, user_id):
    """Spins the roulette wheel using the provably fair seed."""
    result_num, client_seed, nonce = seed_generator(user_id, 0, 36)
    
    number = result_num
    color = ROULETTE_COLORS[number]
    
    return {
        "number": number,
        "color": color,
        "client_seed": client_seed,
        "nonce": nonce
    }

def get_roulette_embed(ctx, spin_result, bet_amount, bet_type, net_change):
    """Generates the final roulette result embed."""
    
    result_number = spin_result["number"]
    result_color = spin_result["color"].upper()
    
    if net_change > 0:
        title = f"🎉 WINNER! The Dragon's Wheel Lands on {result_number} ({result_color})!"
        color = discord.Color.green()
    elif net_change < 0:
        title = f"💔 LOSER! The Dragon's Wheel Lands on {result_number} ({result_color})."
        color = discord.Color.red()
    else:
        title = f"🔄 PUSH! The Dragon's Wheel Lands on {result_number} ({result_color})."
        color = discord.Color.gold()

    embed = discord.Embed(
        title=title,
        description=f"**Your Bet:** {bet_amount:.2f} DC [${bet_amount * DC_VALUE_USD:.2f}] on **{bet_type.upper()}**",
        color=color
    )
    
    embed.add_field(name="Result", value=f"{result_number} ({result_color})", inline=True)
    embed.add_field(name="Net Change", value=f"{net_change:+.2f} DC [${net_change * DC_VALUE_USD:+.2f}]", inline=True)
    embed.add_field(name="Next Nonce", value=spin_result["nonce"] + 1, inline=True)
    embed.add_field(name="Provably Fair", value=f"Client Seed: `{spin_result['client_seed']}`\nNonce: `{spin_result['nonce']}`", inline=False)
    
    return embed
