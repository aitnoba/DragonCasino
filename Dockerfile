FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot files
COPY main.py .
COPY views.py .
COPY blackjack.py .
COPY roulette.py .
COPY mines.py .
COPY start_bot.sh .

# Make script executable
RUN chmod +x start_bot.sh

# Run the bot
CMD ["bash", "start_bot.sh"]
