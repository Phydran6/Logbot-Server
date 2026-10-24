# ==============================================================================
# Name:        Phydran6
# Kontakt:     Phydran6
# Version:     2026.03.31.17.26.46
# Beschreibung: LogBot v2026.03.31.17.26.46 - Syslog Server Dockerfile
# ==============================================================================

FROM python:3.12-slim
WORKDIR /app
# Sicherheitsupdates des Grundsystems beim Bauen mitnehmen.
RUN apt-get update && apt-get upgrade -y && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 514/udp
EXPOSE 514/tcp
CMD ["python", "-u", "syslog_server.py"]
