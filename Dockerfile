FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    CLOUD_CUA_DASHBOARD_PORT=3000 \
    CLOUD_CUA_CONTAINER=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl ca-certificates gnupg unzip nodejs npm docker-cli \
    && arch="$(uname -m)" \
    && case "$arch" in x86_64) aws_arch="x86_64" ;; aarch64) aws_arch="aarch64" ;; *) echo "Unsupported AWS CLI arch: $arch" && exit 1 ;; esac \
    && curl -fsSL "https://awscli.amazonaws.com/awscli-exe-linux-${aws_arch}.zip" -o /tmp/awscliv2.zip \
    && unzip -q /tmp/awscliv2.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscliv2.zip /var/lib/apt/lists/*

COPY pyproject.toml package.json package-lock.json README.md ./
COPY cloud_cua ./cloud_cua

RUN python -m pip install --upgrade pip \
    && python -m pip install -e ".[h,dev]" \
    && npm ci

EXPOSE 3000

CMD ["python", "-m", "cloud_cua.cli", "start", "--host", "0.0.0.0", "--port", "3000"]
