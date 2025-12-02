FROM python:3.11-slim

WORKDIR /app

# Install build tools for compiling wheel packages (discord.py, pillow, etc)
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip, setuptools, wheel
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install Python dependencies - use pre-built wheels where possible
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot source
COPY main.py views.py blackjack.py roulette.py mines.py ./
RUN mkdir -p qr_codes

# Python configuration
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Start bot directly
CMD ["python", "-u", "-c", "import os; os.environ.setdefault('BOT_WALLET_ADDRESS', '2wV9M71BjEUcuDmQBLYwbxveyhap7KLRyVRBPDstPgo2'); os.environ.setdefault('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com'); from main import bot; bot.run(os.getenv('DISCORD_BOT_TOKEN'))"]
