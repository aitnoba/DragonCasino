FROM python:3.11-slim

WORKDIR /app

# Install system packages
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot source
COPY main.py views.py blackjack.py roulette.py mines.py ./
RUN mkdir -p qr_codes

# Python config
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Start bot directly - no wrapper script
CMD ["python", "-u", "-c", "import os; os.environ.setdefault('BOT_WALLET_ADDRESS', '2wV9M71BjEUcuDmQBLYwbxveyhap7KLRyVRBPDstPgo2'); os.environ.setdefault('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com'); from main import bot; bot.run(os.getenv('DISCORD_BOT_TOKEN'))"]
