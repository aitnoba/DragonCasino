FROM python:3.11-slim

WORKDIR /app

# Install all build and system dependencies required for Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    zlib1g-dev \
    libtiff-dev \
    libharfbuzz0b \
    libwebp6 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install wheel/setuptools with specific versions
RUN pip install --no-cache-dir --upgrade pip==23.3.1 setuptools==68.0.0 wheel==0.41.0

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --no-build-isolation -r requirements.txt 2>&1 || pip install --no-cache-dir -r requirements.txt

# Copy bot source files
COPY main.py views.py blackjack.py roulette.py mines.py ./
RUN mkdir -p qr_codes

# Python configuration
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Start bot
CMD ["python", "-u", "-c", "import os; os.environ.setdefault('BOT_WALLET_ADDRESS', '2wV9M71BjEUcuDmQBLYwbxveyhap7KLRyVRBPDstPgo2'); os.environ.setdefault('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com'); from main import bot; bot.run(os.getenv('DISCORD_BOT_TOKEN'))"]
