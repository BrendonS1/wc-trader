FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
curl netcat-openbsd \
&& rm -rf /var/lib/apt/lists/*
COPY pyproject.toml /app/
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir .

COPY src /app/src

CMD ["python", "-m", "wc_trader.main"]
