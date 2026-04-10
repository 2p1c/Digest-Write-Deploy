FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/root/.local/bin:${PATH}"

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates bash git gettext-base \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Install nanobot
RUN pip install nanobot-ai

COPY . /app

RUN pip install httpx

EXPOSE 8000

# Create nanobot config directory
RUN mkdir -p /root/.nanobot

CMD ["tail", "-f", "/dev/null"]
