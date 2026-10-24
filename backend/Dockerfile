# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.10.23.12.00.00
# Beschreibung: LogBot - Backend API Dockerfile
#
# Gebaut aus dem Wurzelverzeichnis des Repositories (docker-compose.yml:
# context ".", dockerfile backend/Dockerfile): so kommen die Agent-Installer
# mit ins Image. Der Server liefert sie von dort aus und unterschreibt damit
# die Agent-Updates - auch im gehaerteten Betrieb ohne Zugriff auf den Host.
# ==============================================================================

FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y --no-install-recommends gcc busybox-static util-linux && \
    rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt
COPY backend/ .
COPY agents/ /app/agents/
ENV LOGBOT_AGENTS_DIR=/app/agents
EXPOSE 8000
# --proxy-headers aus: die echte Absender-IP ermittelt app/limiter.py selbst und
# nur von den eigenen Proxys. Zugriffsprotokoll bleibt, Parameter werden dort
# geschwaerzt (app/main.py).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-server-header"]
