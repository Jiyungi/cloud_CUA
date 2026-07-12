FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CLOUD_CUA_DASHBOARD_PORT=3000

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg unzip nodejs npm \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml package.json package-lock.json README.md ./
COPY cloud_cua ./cloud_cua

RUN python -m pip install --upgrade pip \
    && python -m pip install -e ".[h,dev]" \
    && npm ci \
    && npx playwright install chromium

EXPOSE 3000

CMD ["python", "-m", "cloud_cua.cli", "start", "--host", "0.0.0.0", "--port", "3000"]
