FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl git jq tree wget unzip \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

# Chromium + fonts for the Puppeteer-based browser tool.
# Installing the apt 'chromium' package pulls in all required shared libraries.
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install the Node browser helper deps (puppeteer-core). Done before COPY . .
# so it is cached unless package.json changes.
COPY browser/package.json ./browser/package.json
RUN cd browser && npm install --omit=dev

COPY . .

RUN mkdir -p /workspace

CMD ["python", "-u", "main.py"]
