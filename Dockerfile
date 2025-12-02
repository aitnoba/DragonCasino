FROM python:3.11-slim

WORKDIR /app

# Minimal system packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Fresh pip/setuptools install
RUN pip install --upgrade --no-cache-dir pip==24.0

# Install dependencies with compatible versions
COPY requirements.txt .
RUN pip install --no-cache-dir --no-build-isolation --no-deps \
    discord-py==2.3.2 \
    pillow==10.0.0 \
    qrcode==7.4.2 \
    python-dotenv==1.0.0 \
    requests==2.31.0

# Copy bot
COPY main.py views.py blackjack.py roulette.py mines.py run_bot.py ./
RUN mkdir -p qr_codes

ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "run_bot.py"]
