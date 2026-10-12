FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bot.py storage.py ./
COPY data ./data
RUN useradd --create-home bot && mkdir /app/runtime && chown bot:bot /app/runtime
USER bot
CMD ["python", "bot.py"]
