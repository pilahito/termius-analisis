#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Busca trozos relevantes en el código legible de Termius y pregunta al modelo local."""
import json
import re
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, "/usr/local/lib/termius-ia")
try:
    import nube  # motor Cloudflare Workers AI
except Exception:
    nube = None

LEGIBLE = Path.home() / "Termius-analisis" / "legible"
SERVIDOR = "http://127.0.0.1:11434"
MODELO = "qwen2.5-coder:14b"
MAX_CONTEXTO = 26000

VACIAS = {"como", "donde", "para", "quien", "cuando", "explica", "funciona", "hace",
          "esta", "este", "sobre", "codigo", "terminus", "puede", "sirve", "utiliza",
          "dime", "conecta", "usa", "son", "las", "los", "por", "que"}


def claves(pregunta):
    palabras = re.findall(r"[a-z0-9_-]{3,}", pregunta.lower())
    return [p for p in dict.fromkeys(palabras) if p not in VACIAS][:6]


CACHE = {}


def leer(fichero):
    if fichero not in CACHE:
        try:
            CACHE[fichero] = fichero.read_text(encoding="utf-8", errors="replace").splitlines()
        except Exception:
            CACHE[fichero] = []
    return CACHE[fichero]


def puntuar(palabras):
    """Cuenta, por fichero, cuántas palabras distintas aparecen (y cuántas veces)."""
    puntuacion = {}
    for fichero in sorted(LEGIBLE.glob("*.js"), key=lambda f: -f.stat().st_size):
        lineas = leer(fichero)
        if not lineas:
            continue
        bajo = "\n".join(lineas).lower()
        distintas = sum(1 for p in palabras if p in bajo)
        if distintas:
            total = sum(bajo.count(p) for p in palabras)
            # se premia cubrir varias palabras y se penaliza el tamaño (un
            # diccionario gigante no es buen contexto para una pregunta)
            puntuacion[fichero] = (distintas, total / max(1, len(lineas) / 1000))
    return sorted(puntuacion.items(), key=lambda x: (-x[1][0], -x[1][1]))


def trozos(palabras, max_ficheros=2, max_trozos=5):
    """Trocea los ficheros más relevantes alrededor de las palabras buscadas."""
    salida, vistos = [], set()
    for fichero, _ in puntuar(palabras)[:max_ficheros]:
        lineas = leer(fichero)
        encontrados = 0
        for i, linea in enumerate(lineas):
            bajo = linea.lower()
            if any(p in bajo for p in palabras):
                if (fichero, i) in vistos:
                    continue
                vistos.add((fichero, i))
                desde, hasta = max(0, i - 12), min(len(lineas), i + 28)
                salida.append((fichero.name, i + 1, "\n".join(lineas[desde:hasta])))
                encontrados += 1
                if encontrados >= max_trozos:
                    break
    return salida


def main():
    pregunta = sys.argv[1]
    modelo = sys.argv[2] if len(sys.argv) > 2 else MODELO
    motor = sys.argv[3] if len(sys.argv) > 3 else "local"
    palabras = claves(pregunta)

    contexto = [f"// {f}:{l}\n{txt}" for f, l, txt in trozos(palabras)]
    total = 0
    seleccion = []
    for trozo in contexto:
        if total + len(trozo) > MAX_CONTEXTO:
            break
        seleccion.append(trozo)
        total += len(trozo)
    contexto = seleccion

    if len("".join(contexto)) < 3000:
        grande = max(LEGIBLE.glob("*.js"), key=lambda f: f.stat().st_size)
        contexto = [f"// {grande.name} (inicio)\n" + grande.read_text(errors="replace")[:MAX_CONTEXTO]]

    codigo = "\n\n".join(contexto)[:MAX_CONTEXTO]
    print(f"(contexto: {len(codigo)} caracteres · palabras: {', '.join(palabras)})", file=sys.stderr)

    prompt = (
        "Eres experto en ingeniería inversa de apps Electron. Te doy trozos de "
        "JavaScript minificado embellecido de Termius. Responde en español, breve "
        "y técnico, separando OBSERVACIÓN (lo que dice el código) de SUPOSICIÓN. "
        "Cita fichero:línea.\n\n"
        f"PREGUNTA: {pregunta}\n\nCÓDIGO:\n{codigo}"
    )
    if motor == "cf" and nube is not None:
        print("[motor: Cloudflare Workers AI]", file=sys.stderr)
        print(nube.consultar(prompt), flush=True)
        return

    print(f"[motor: local {modelo}]", file=sys.stderr)
    peticion = urllib.request.Request(
        SERVIDOR + "/api/generate",
        data=json.dumps({"model": modelo, "prompt": prompt, "stream": False,
                         "options": {"temperature": 0.2, "num_predict": 800}}).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(peticion, timeout=900) as r:
        print((json.loads(r.read().decode()).get("response") or "").strip())


if __name__ == "__main__":
    main()
