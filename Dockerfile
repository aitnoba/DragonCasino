FROM python:3.11

WORKDIR /app

# Install all build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install dependencies with binary-only preference
RUN pip install --upgrade --no-cache-dir pip setuptools wheel

# Install from requirements using binary wheels only
COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy bot files
COPY main.py views.py blackjack.py roulette.py mines.py run_bot.py ./
RUN mkdir -p qr_codes

# Environment
ENV PYTHONUNBUFFERED=1

# Run bot
CMD ["python", "-u", "run_bot.py"]
