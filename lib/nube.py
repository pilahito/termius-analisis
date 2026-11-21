#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Motor alternativo: Cloudflare Workers AI (IA en la nube del usuario)."""
import json
import os
import urllib.request
from pathlib import Path

CUENTA = os.environ.get("CF_ACCOUNT_ID", "")
MODELO = os.environ.get("CF_MODELO", "@cf/qwen/qwen2.5-coder-32b-instruct")
CREDENCIALES = Path.home() / ".dsh" / ".credentials.yaml"
CONFIG = Path.home() / ".config" / "termius-ia.json"


def configuracion():
    """Lee ~/.config/termius-ia.json (token y cuenta de Cloudflare)."""
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception:
        return {}


def token():
    """Token de Cloudflare: entorno, configuración o credenciales de DSH."""
    if os.environ.get("CLOUDFLARE_API_KEY"):
        return os.environ["CLOUDFLARE_API_KEY"].strip()
    valor = (configuracion().get("token") or "").strip()
    if valor:
        return valor
    try:
        import yaml
        datos = yaml.safe_load(CREDENCIALES.read_text(encoding="utf-8"))
        return (datos.get("refs", {}).get("CLOUDFLARE_API_KEY") or "").strip()
    except Exception:
        return ""


def cuenta():
    if CUENTA:
        return CUENTA
    return (configuracion().get("cuenta") or "").strip()


def consultar(prompt, max_tokens=800):
    clave = token()
    if not clave:
        raise SystemExit("falta el token de Cloudflare (CLOUDFLARE_API_KEY o ~/.dsh/.credentials.yaml)")
    if not cuenta():
        raise SystemExit("falta la cuenta de Cloudflare (CF_ACCOUNT_ID o ~/.config/termius-ia.json)")
    url = f"https://api.cloudflare.com/client/v4/accounts/{cuenta()}/ai/run/{MODELO}"
    cuerpo = json.dumps({
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.2,
    }).encode()
    peticion = urllib.request.Request(url, data=cuerpo, headers={
        "Authorization": f"Bearer {clave}", "Content-Type": "application/json"})
    with urllib.request.urlopen(peticion, timeout=180) as r:
        datos = json.loads(r.read().decode())
    if not datos.get("success"):
        raise SystemExit(f"Cloudflare AI falló: {datos.get('errors')}")
    return (datos.get("result", {}).get("response") or "").strip()


if __name__ == "__main__":
    import sys
    print(consultar(sys.argv[1] if len(sys.argv) > 1 else "Di hola"))
