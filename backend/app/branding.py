"""
================================================================================
Name:           Phil Fischer
E-Mail:         p.fischer@phytech.de
Version:        30.01.2026.19.42.15
================================================================================

LogBot Branding API - Backend für Whitelabel-System
===================================================
================================================================================
"""

from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
import json
import os
import shutil
from datetime import datetime

# =============================================================================
# Router-Instanz
# =============================================================================
branding_router = APIRouter(prefix="/api/branding", tags=["Branding"])

# =============================================================================
# Pfade
# =============================================================================
BRANDING_CONFIG_PATH = "/app/data/branding_config.json"
ASSETS_DIR = "/app/data/assets"


# =============================================================================
# Pydantic-Modelle
# =============================================================================

class ColorScheme(BaseModel):
    """Farbschema für Dark oder Light Mode"""
    background: str = Field(description="Haupt-Hintergrund")
    surface: str = Field(description="Karten, Modals")
    surface_elevated: str = Field(description="Dropdowns, Tooltips")
    border: str = Field(description="Rahmenfarbe")
    text_primary: str = Field(description="Primärer Text")
    text_secondary: str = Field(description="Sekundärer Text")
    text_muted: str = Field(description="Gedämpfter Text")


class BrandingConfig(BaseModel):
    """Vollständige Branding-Konfiguration"""
    
    # Allgemein
    company_name: str = "LogBot"
    tagline: str = "Centralized Log Management"
    footer_text: str = "© 2026 LogBot. All rights reserved."
    support_email: str = "support@example.com"
    
    # Assets
    logo_path: Optional[str] = None
    favicon_path: Optional[str] = None
    
    # Theme
    default_theme: str = "dark"
    allow_theme_toggle: bool = True
    
    # Markenfarben
    primary_color: str = "#3b82f6"
    secondary_color: str = "#8b5cf6"
    accent_color: str = "#10b981"
    success_color: str = "#22c55e"
    warning_color: str = "#f59e0b"
    danger_color: str = "#ef4444"
    
    # Dark Mode Farben - CUSTOM
    dark_scheme: ColorScheme = ColorScheme(
        background="#444464",
        surface="#313146",
        surface_elevated="#3a3a54",
        border="#45455f",
        text_primary="#f8fafc",
        text_secondary="#e2e8f0",
        text_muted="#cbd5e1"
    )
    
    # Light Mode Farben
    light_scheme: ColorScheme = ColorScheme(
        background="#f1f5f9",
        surface="#ffffff",
        surface_elevated="#f8fafc",
        border="#e2e8f0",
        text_primary="#0f172a",
        text_secondary="#334155",
        text_muted="#64748b"
    )
    
    # Custom CSS
    custom_css: str = ""


# =============================================================================
# Hilfsfunktionen
# =============================================================================

def ensure_directories():
    """Erstellt benötigte Verzeichnisse"""
    config_dir = os.path.dirname(BRANDING_CONFIG_PATH)
    if config_dir:
        os.makedirs(config_dir, exist_ok=True)
    os.makedirs(ASSETS_DIR, exist_ok=True)


def load_config() -> BrandingConfig:
    """Lädt Konfiguration aus JSON oder gibt Default zurück"""
    ensure_directories()
    
    if os.path.exists(BRANDING_CONFIG_PATH):
        try:
            with open(BRANDING_CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return BrandingConfig(**data)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"[Branding] Config-Fehler: {e}")
            return BrandingConfig()
    
    return BrandingConfig()


def save_config(config: BrandingConfig) -> None:
    """Speichert Konfiguration als JSON"""
    ensure_directories()
    with open(BRANDING_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config.model_dump(), f, indent=2, ensure_ascii=False)


# =============================================================================
# API-Endpunkte
# =============================================================================

@branding_router.get("/config", response_model=BrandingConfig)
async def get_branding_config():
    """GET /api/branding/config - Lädt aktuelle Konfiguration"""
    return load_config()


@branding_router.put("/config", response_model=BrandingConfig)
async def update_branding_config(config: BrandingConfig):
    """PUT /api/branding/config - Speichert Konfiguration"""
    save_config(config)
    return config


@branding_router.post("/upload/logo")
async def upload_logo(file: UploadFile = File(...)):
    """POST /api/branding/upload/logo - Lädt Logo hoch"""
    ensure_directories()
    
    ext = os.path.splitext(file.filename)[1].lower()
    allowed = ['.png', '.jpg', '.jpeg', '.svg', '.webp']
    if ext not in allowed:
        raise HTTPException(400, f"Format nicht erlaubt. Erlaubt: {', '.join(allowed)}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"logo_{timestamp}{ext}"
    filepath = os.path.join(ASSETS_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    config = load_config()
    if config.logo_path:
        old_path = os.path.join(ASSETS_DIR, config.logo_path)
        if os.path.exists(old_path):
            os.remove(old_path)
    
    config.logo_path = filename
    save_config(config)
    
    return {"path": filename, "message": "Logo hochgeladen"}


@branding_router.post("/upload/favicon")
async def upload_favicon(file: UploadFile = File(...)):
    """POST /api/branding/upload/favicon - Lädt Favicon hoch"""
    ensure_directories()
    
    ext = os.path.splitext(file.filename)[1].lower()
    allowed = ['.ico', '.png', '.svg']
    if ext not in allowed:
        raise HTTPException(400, f"Format nicht erlaubt. Erlaubt: {', '.join(allowed)}")
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"favicon_{timestamp}{ext}"
    filepath = os.path.join(ASSETS_DIR, filename)
    
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    config = load_config()
    if config.favicon_path:
        old_path = os.path.join(ASSETS_DIR, config.favicon_path)
        if os.path.exists(old_path):
            os.remove(old_path)
    
    config.favicon_path = filename
    save_config(config)
    
    return {"path": filename, "message": "Favicon hochgeladen"}


@branding_router.get("/assets/{filename}")
async def get_asset(filename: str):
    """GET /api/branding/assets/{filename} - Liefert Asset aus"""
    filepath = os.path.join(ASSETS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(404, "Asset nicht gefunden")
    return FileResponse(filepath)


@branding_router.post("/reset")
async def reset_branding():
    """POST /api/branding/reset - Setzt auf Standardwerte zurück"""
    if os.path.exists(ASSETS_DIR):
        for filename in os.listdir(ASSETS_DIR):
            filepath = os.path.join(ASSETS_DIR, filename)
            if os.path.isfile(filepath):
                os.remove(filepath)
    
    if os.path.exists(BRANDING_CONFIG_PATH):
        os.remove(BRANDING_CONFIG_PATH)
    
    return BrandingConfig()