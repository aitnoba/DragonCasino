import random
import discord

DC_VALUE_USD = 1.00

CARD_VALUES = {
    '2': 2, '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, 
    '10': 10, 'J': 10, 'Q': 10, 'K': 10, 'A': 11
}
SUITS = ['♠️', '♥️', '♦️', '♣️']
RANKS = list(CARD_VALUES.keys())

def calculate_hand_value(hand):
    """Calculates the value of a Blackjack hand, handling Aces."""
    def get_card_rank(card):
        """Extract rank from card (handles 10 and single char ranks)."""
        if card.startswith('10'):
            return '10'
        return card[0]
    
    value = sum(CARD_VALUES[get_card_rank(card)] for card in hand)
    num_aces = sum(1 for card in hand if card.startswith('A'))
    
    while value > 21 and num_aces > 0:
        value -= 10
        num_aces -= 1
        
    return value

def create_deck(num_decks=6):
    """Creates a standard deck of cards."""
    deck = []
    for _ in range(num_decks):
        for suit in SUITS:
            for rank in RANKS:
                deck.append(rank + suit)
    random.shuffle(deck)
    return deck

class BlackjackGame:
    def __init__(self, user_id, seed_generator):
        self.user_id = user_id
        self.seed_generator = seed_generator
        self.deck = self._create_seeded_deck()
        self.player_hand = []
        self.dealer_hand = []
        self.state = "BETTING"
        self.bet = 0.0

    def _create_seeded_deck(self):
        """Creates a deck and shuffles it using the provably fair seed."""
        result_num, _, _ = self.seed_generator(self.user_id, 0, 1000000000)
        
        deck = create_deck(num_decks=6)
        
        temp_random = random.Random(result_num)
        temp_random.shuffle(deck)
        
        return deck

    def start_game(self, bet_amount):
        """Deals initial cards and starts the game."""
        self.bet = bet_amount
        
        self.player_hand.append(self.deck.pop(0))
        self.dealer_hand.append(self.deck.pop(0))
        self.player_hand.append(self.deck.pop(0))
        self.dealer_hand.append(self.deck.pop(0))
        
        player_value = calculate_hand_value(self.player_hand)
        dealer_value = calculate_hand_value(self.dealer_hand)
        
        if player_value == 21:
            self.state = "ENDED"
            return "BLACKJACK"
        
        self.state = "PLAYER_TURN"
        return "CONTINUE"

    def hit(self):
        """Player takes another card."""
        if self.state != "PLAYER_TURN":
            return "INVALID"
            
        self.player_hand.append(self.deck.pop(0))
        player_value = calculate_hand_value(self.player_hand)
        
        if player_value > 21:
            self.state = "ENDED"
            return "BUST"
        elif player_value == 21:
            self.state = "DEALER_TURN"
            return "STAND"
        
        return "CONTINUE"

    def stand(self):
        """Player ends their turn, dealer plays."""
        if self.state != "PLAYER_TURN":
            return "INVALID"
            
        self.state = "DEALER_TURN"
        return self._dealer_play()

    def _dealer_play(self):
        """Dealer plays their hand (hits on 16 or less, stands on 17 or more)."""
        while calculate_hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(self.deck.pop(0))
            
        self.state = "ENDED"
        dealer_value = calculate_hand_value(self.dealer_hand)
        
        if dealer_value > 21:
            return "DEALER_BUST"
        
        return "DEALER_STAND"

    def get_result(self):
        """Determines the final outcome and payout."""
        player_value = calculate_hand_value(self.player_hand)
        dealer_value = calculate_hand_value(self.dealer_hand)
        
        payout_multiplier = 0.0
        result_message = ""
        
        if player_value > 21:
            result_message = "Player BUSTS! Dealer wins."
            payout_multiplier = 0.0
        elif dealer_value > 21:
            result_message = "Dealer BUSTS! Player wins."
            payout_multiplier = 1.9
        elif player_value == 21 and len(self.player_hand) == 2:
            if dealer_value == 21 and len(self.dealer_hand) == 2:
                result_message = "Push! Both have Blackjack."
                payout_multiplier = 1.0
            else:
                result_message = "BLACKJACK! Player wins 3:2."
                payout_multiplier = 2.375
        elif player_value > dealer_value:
            result_message = "Player wins!"
            payout_multiplier = 1.9
        elif player_value < dealer_value:
            result_message = "Dealer wins."
            payout_multiplier = 0.0
        else:
            result_message = "Push! Bet returned."
            payout_multiplier = 1.0
            
        net_change = (payout_multiplier * self.bet) - self.bet
        
        return {
            "message": result_message,
            "payout": payout_multiplier * self.bet,
            "net_change": net_change,
            "player_hand": self.player_hand,
            "dealer_hand": self.dealer_hand,
            "player_value": player_value,
            "dealer_value": dealer_value
        }

    def get_status_embed(self, ctx, hide_dealer=True):
        """Generates a status embed for the current game state."""
        player_hand_str = " ".join(self.player_hand)
        player_value = calculate_hand_value(self.player_hand)
        
        def get_card_rank(card):
            """Extract rank from card (handles 10 and single char ranks)."""
            if card.startswith('10'):
                return '10'
            return card[0]
        
        if hide_dealer:
            dealer_hand_str = f"{self.dealer_hand[0]} [Hidden Card]"
            dealer_value_str = CARD_VALUES[get_card_rank(self.dealer_hand[0])]
        else:
            dealer_hand_str = " ".join(self.dealer_hand)
            dealer_value_str = calculate_hand_value(self.dealer_hand)

        embed = discord.Embed(
            title="♠️ Dragon Blackjack ♣️",
            description=f"**Bet:** {self.bet:.2f} DC [${self.bet * DC_VALUE_USD:.2f}]",
            color=discord.Color.blue()
        )
        embed.set_author(name=ctx.display_name, icon_url=ctx.display_avatar.url)
        
        embed.add_field(name="Your Hand", value=f"{player_hand_str}\n**Value:** {player_value}", inline=False)
        embed.add_field(name="Dealer's Hand", value=f"{dealer_hand_str}\n**Value:** {dealer_value_str}", inline=False)
        
        if self.state == "PLAYER_TURN":
            embed.set_footer(text="Type .hit or .stand to continue.")
        elif self.state == "ENDED":
            result = self.get_result()
            embed.description += f"\n\n**{result['message']}**\nNet Change: {result['net_change']:+.2f} DC [${result['net_change'] * DC_VALUE_USD:+.2f}]"
            embed.color = discord.Color.green() if result['net_change'] > 0 else discord.Color.red()
            
        return embed

active_blackjack_games = {}
