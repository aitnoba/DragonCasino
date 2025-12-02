FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies FIRST
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy all bot source files
COPY main.py .
COPY views.py .
COPY blackjack.py .
COPY roulette.py .
COPY mines.py .

# Create directories for runtime data
RUN mkdir -p /app/qr_codes

# Set environment variables with defaults
ENV PYTHONUNBUFFERED=1
ENV DISCORD_BOT_TOKEN=""
ENV BOT_WALLET_ADDRESS=""
ENV SOLANA_RPC_URL="https://api.mainnet-beta.solana.com"

# Start the bot
CMD ["python", "-u", "main.py"]
