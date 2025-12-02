FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all bot files
COPY main.py .
COPY views.py .
COPY blackjack.py .
COPY roulette.py .
COPY mines.py .

# Create data directory for database
RUN mkdir -p /app/data /app/qr_codes

# Run the bot directly (no shell wrapper needed on Render)
CMD ["python", "main.py"]
