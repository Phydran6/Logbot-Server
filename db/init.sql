-- ==============================================================================
-- Name:        Phydran6
-- Kontakt:     Phydran6
-- Version:     2026.04.11.13.38.42
-- Beschreibung: LogBot v2026.04.11.13.38.42 - PostgreSQL Datenbankschema
-- ==============================================================================

-- Performance-Extensions
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Benutzer-Tabelle
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100),
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) DEFAULT 'user',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agents-Tabelle (erkannte Geräte)
CREATE TABLE IF NOT EXISTS agents (
    id SERIAL PRIMARY KEY,
    hostname VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    mac_address VARCHAR(17),
    device_type VARCHAR(50) DEFAULT 'unknown',
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    extra_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_agents_hostname_ip ON agents(hostname, ip_address);
CREATE INDEX IF NOT EXISTS idx_agents_mac ON agents(mac_address);

-- Logs-Tabelle
CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    agent_id INTEGER REFERENCES agents(id) ON DELETE SET NULL,
    hostname VARCHAR(255),
    ip_address VARCHAR(45),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    facility INTEGER,
    level VARCHAR(20),
    source VARCHAR(100),
    message TEXT,
    raw_message TEXT,
    extra_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    -- Duplikat-Erkennung beim HTTPS-Ingest, NULL = keine Pruefung (z.B. Syslog)
    dedup_key VARCHAR(64)
);

CREATE INDEX IF NOT EXISTS idx_logs_agent_id ON logs(agent_id);
CREATE INDEX IF NOT EXISTS idx_logs_timestamp ON logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_logs_hostname ON logs(hostname);
CREATE INDEX IF NOT EXISTS idx_logs_level ON logs(level);
CREATE INDEX IF NOT EXISTS idx_logs_source ON logs(source);
CREATE INDEX IF NOT EXISTS idx_logs_hostname_trgm ON logs USING gin (hostname gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_logs_source_trgm ON logs USING gin (source gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_logs_message_trgm ON logs USING gin (message gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_logs_level_lower ON logs ((lower(level)));
-- Fuer den Logtyp-Filter nach Syslog-Facility
CREATE INDEX IF NOT EXISTS idx_logs_facility ON logs(facility);
-- Duplikat-Erkennung beim HTTPS-Ingest (nur Zeilen mit Schluessel)
ALTER TABLE logs ADD COLUMN IF NOT EXISTS dedup_key VARCHAR(64);
CREATE UNIQUE INDEX IF NOT EXISTS idx_logs_dedup_key ON logs(dedup_key) WHERE dedup_key IS NOT NULL;

-- Passkeys / WebAuthn (Anmeldung ohne Passwort)
CREATE TABLE IF NOT EXISTS webauthn_credentials (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    credential_id VARCHAR(512) UNIQUE NOT NULL,
    public_key TEXT NOT NULL,
    sign_count INTEGER NOT NULL DEFAULT 0,
    name VARCHAR(100),
    transports VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used_at TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_webauthn_user ON webauthn_credentials(user_id);

-- Herkunft eines Kontos: 'local' oder 'ldap'
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_source VARCHAR(20) NOT NULL DEFAULT 'local';

-- Webhooks-Tabelle
CREATE TABLE IF NOT EXISTS webhooks (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    token VARCHAR(64) UNIQUE NOT NULL,
    description TEXT,
    filters JSONB DEFAULT '{}',
    max_results INTEGER DEFAULT 100,
    include_raw BOOLEAN DEFAULT false,
    is_active BOOLEAN DEFAULT true,
    call_count INTEGER DEFAULT 0,
    last_called_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Settings-Tabelle
CREATE TABLE IF NOT EXISTS settings (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) UNIQUE NOT NULL,
    value JSONB NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Standard Admin: admin / admin
INSERT INTO users (username, email, password_hash, role) 
VALUES ('admin', 'admin@localhost', '$2b$12$XOE63DtzGEyiaLLBY05W0ulT6EVFIC243bkg7UivW1kfx0.bmmSj2', 'admin')
ON CONFLICT (username) DO NOTHING;

-- Retention-Policy Spalten (werden per Startup-Migration auch auf bestehende DBs angewendet)
ALTER TABLE agents ADD COLUMN IF NOT EXISTS retention_max_logs INTEGER;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS retention_days INTEGER;

-- Agent-Tokens für authentifizierten HTTPS-Modus
CREATE TABLE IF NOT EXISTS agent_tokens (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    token VARCHAR(64) UNIQUE NOT NULL,
    device_type VARCHAR(50),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- App-Login-Tokens (für QR-Code-Authentifizierung der Android-App)
CREATE TABLE IF NOT EXISTS app_login_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(64) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_app_login_tokens_token ON app_login_tokens(token);
CREATE INDEX IF NOT EXISTS idx_app_login_tokens_user_id ON app_login_tokens(user_id);

-- Standard-Einstellungen
INSERT INTO settings (key, value, description) VALUES
    ('log_retention_days', '90', 'Logs älter als X Tage löschen'),
    ('agent_offline_timeout', '300', 'Sekunden bis Agent offline')
ON CONFLICT (key) DO NOTHING;
