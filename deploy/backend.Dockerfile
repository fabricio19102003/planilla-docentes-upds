FROM python:3.12.8-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install --no-install-recommends -y postgresql-client ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --gid 10001 sipad \
    && useradd --uid 10001 --gid 10001 --create-home --shell /usr/sbin/nologin sipad

WORKDIR /app/backend

COPY backend/requirements.txt ./requirements.txt
RUN python -m pip install --requirement requirements.txt

COPY --chown=sipad:sipad backend/ ./
COPY --chown=sipad:sipad normalizar_horarios.py /app/normalizar_horarios.py

RUN mkdir -p \
      /app/backend/data/uploads \
      /app/backend/data/billing-media \
      /app/backend/data/output \
      /app/backend/data/reports \
      /app/backend/data/contracts \
      /app/backend/data/schedules \
      /app/backend/data/retention_letters \
      /app/backend/data/backups \
    && chown -R sipad:sipad /app/backend/data

USER 10001:10001
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
