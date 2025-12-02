FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --only-binary=:all: -r requirements.txt || pip install -r requirements.txt

COPY main.py views.py blackjack.py roulette.py mines.py run_bot.py ./
RUN mkdir -p qr_codes

ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "run_bot.py"]
