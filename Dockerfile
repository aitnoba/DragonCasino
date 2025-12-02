FROM python:3.11

WORKDIR /app

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefer-binary -r requirements.txt

COPY main.py views.py blackjack.py roulette.py mines.py run_bot.py ./
RUN mkdir -p qr_codes

ENV PYTHONUNBUFFERED=1

CMD ["python", "-u", "run_bot.py"]
