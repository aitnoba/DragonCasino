FROM python:3.11-slim

WORKDIR /app

# Install all system dependencies (build tools + image libraries)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    libjpeg-dev \
    libpng-dev \
    libfreetype6-dev \
    zlib1g-dev \
    libtiff-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip/setuptools/wheel
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy bot files
COPY main.py views.py blackjack.py roulette.py mines.py run_bot.py ./
RUN mkdir -p qr_codes

# Environment
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Run the bot
CMD ["python", "-u", "run_bot.py"]
