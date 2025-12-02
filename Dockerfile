FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy all bot source files
COPY main.py .
COPY views.py .
COPY blackjack.py .
COPY roulette.py .
COPY mines.py .
COPY start.py .

# Create directories for runtime data
RUN mkdir -p /app/qr_codes

# Set environment to ensure proper Python output
ENV PYTHONUNBUFFERED=1

# Health check - optional but good for Render
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000', timeout=5)" || exit 1

# Start the bot using our startup script
CMD ["python", "-u", "start.py"]
