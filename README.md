# termius-analisis

Cómo está hecha **Termius 10.4.1** por dentro, a partir de su `.deb` de Linux,
sin ejecutar la app y **sin distribuir su código**.

El objetivo no es copiar el producto, sino entender su arquitectura (Electron
multi-ventana, motor SSH nativo, estado Redux, cifrado, seguridad) y dejar un
método reproducible para estudiarlo.

## Qué hay aquí

| Ruta | Contenido |
|---|---|
| [`docs/INFORME.md`](docs/INFORME.md) | informe completo: arquitectura, conexiones, cifrado, seguridad y límites |
| [`docs/RECUPERACION.md`](docs/RECUPERACION.md) | qué código se puede recuperar de verdad (y qué no) |
| [`docs/ESTRUCTURA-MODULOS.md`](docs/ESTRUCTURA-MODULOS.md) | los 743 módulos originales de Termius |
| [`bin/termius-recuperar`](bin/termius-recuperar) | recupera fuentes de librerías + estructura de módulos |
| [`bin/termius-repack`](bin/termius-repack) | reconstruye un `.deb` instalable |
| [`bin/termius-ia`](bin/termius-ia) | extrae el `.deb`, embellece el JavaScript y responde preguntas sobre el código |
| [`lib/consulta.py`](lib/consulta.py) | recuperación de fragmentos relevantes + pregunta al modelo |
| [`lib/nube.py`](lib/nube.py) | motor opcional en la nube (Cloudflare Workers AI) |

**No se incluye** el `.deb`, el `app.asar` ni código de Termius: solo
observaciones y herramientas.

## El método (en corto)

1. **Extraer el paquete**: `ar x Termius.deb data.tar.xz` y del `app.asar`
   sacar los ficheros con su cabecera de índice.
2. **Leer el JavaScript**: los bundles son de Vite, minificados y **sin source
   maps con contenido** → se embellecen con Prettier para poder leerlos.
3. **Buscar con evidencia**: cada afirmación se ancla a `fichero:línea`.
4. **Preguntar a una IA local**: `termius-ia` recupera los trozos relevantes y
   los pasa a Ollama (o a Cloudflare Workers AI con `--cf`), sin salir de tu
   equipo en el modo local.

## Uso rápido

```bash
# 1. instalar la utilidad
install -m755 bin/termius-ia ~/.local/bin/termius-ia
sudo install -d /usr/local/lib/termius-ia
sudo install -m644 lib/consulta.py lib/nube.py /usr/local/lib/termius-ia/

# 2. extraer y embellecer (una vez)
termius-ia preparar Termius.deb        # deja todo en ~/Termius-analisis

# 3. preguntar
termius-ia buscar "SshClient"
termius-ia preguntar "cómo funciona la reconexión"          # Ollama local
termius-ia preguntar "cómo funciona la reconexión" --cf     # Cloudflare
termius-ia archivo                                          # lista bundles
termius-ia motores                                          # motores disponibles
```

Por defecto usa `qwen2.5-coder:14b` en Ollama. Para el motor de nube:

```json
// ~/.config/termius-ia.json
{ "token": "tu-token-cloudflare", "cuenta": "id-de-cuenta" }
```

(o las variables `CLOUDFLARE_API_KEY` y `CF_ACCOUNT_ID`).

## ¿Se puede recrear la copia?

**Sí, el paquete.** No el código fuente original (no está en el `.deb`), pero sí
un `.deb` instalable con la app tal cual o con los cambios que hagas:

```bash
termius-repack Termius.deb Termius-nuevo.deb            # app como directorio
termius-repack Termius.deb Termius-nuevo.deb --asar     # reempaquetar app.asar
```

Cómo funciona: abre el `.deb`, sustituye `resources/app.asar` por la aplicación
extraída (o un `app.asar` nuevo), conserva el `control` original (versión 10.4.1,
dependencias) y vuelve a montar `data.tar.xz` + `ar`. Comprobado: el paquete
resultante mantiene la estructura y los metadatos; la app va como
`resources/app/`, que Electron carga igual y donde los módulos nativos `.node`
funcionan sin trucos.

Sirve sobre todo para **probar cambios** (temas, textos, parches) en tu equipo.
Ojo: es una copia modificada de software propietario; para uso personal, sin
redistribuir.

## Qué se puede y qué no

**Sí**: estructura de módulos, frameworks, canales IPC, rutas, máquina de
estados de conexión, librerías nativas, configuración de seguridad, endpoints,
datos curiosos (zxcvbn, HIBP, autocompletado de CLIs).

**No**: el código fuente original no está en el paquete; los nombres de
funciones y variables son opacos; el análisis es estático (no hay evidencia de
ejecución); algunos chunks del renderer quedan fuera.

## Aviso legal

Termius es software **propietario**. Este repositorio contiene únicamente
documentación técnica y herramientas propias, fruto del análisis del paquete en
un equipo personal, con fines de estudio e interoperabilidad. No incluye ni
redistribuye código de Termius. Úsalo bajo tu responsabilidad y respeta la
licencia del producto original.

## Licencia

MIT para el texto y las herramientas de este repositorio.
