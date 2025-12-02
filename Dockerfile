FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install build tools
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Copy and install requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all bot source files
COPY main.py .
COPY views.py .
COPY blackjack.py .
COPY roulette.py .
COPY mines.py .
COPY start.py .

# Create directories for runtime data
RUN mkdir -p /app/qr_codes

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Start the bot
CMD ["python", "-u", "start.py"]
