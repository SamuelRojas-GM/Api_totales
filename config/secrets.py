"""
Carga de variables desde Secret Manager (MS_MOV_PT_SECS_JSON).
En Cloud Run: --set-secrets=MS_MOV_PT_SECS_JSON=ms-mov-pt-secs-json:latest
En local: usar .env con variables individuales (fallback).
"""
import os
import json

SECRETS_RAW = os.getenv("MS_MOV_PT_SECS_JSON")
if not SECRETS_RAW:
    SECRETS = {}  # Local: fallback a os.getenv por variable
else:
    SECRETS = json.loads(SECRETS_RAW)


def get(key: str, default=None):
    """Obtiene valor de SECRETS; fallback a os.getenv para desarrollo local."""
    return SECRETS.get(key, os.getenv(key, default))
