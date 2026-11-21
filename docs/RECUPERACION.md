# ¿Se puede recuperar el código fuente de Termius?

**Código fuente original de Termius: no.** El `.deb` no lo incluye: el
JavaScript va compilado con Vite, minificado y **sin `sourcesContent`** para el
código propio. No es cuestión de herramientas: la información no está ahí.

Lo que **sí** se ha recuperado, ejecutando `termius-recuperar`:

| Qué | Cuánto | Valor |
|---|---|---|
| Fuentes reales de librerías incluidas (desde sus `.map` con `sourcesContent`) | **277 ficheros** de 8 paquetes (Azure MSAL, identity, core-rest-pipeline…) | Código fuente auténtico, legible |
| Nombres de los módulos originales de Termius (los chunks de Vite conservan el nombre del módulo) | **743 módulos** | Permite reconstruir el árbol de módulos y orientarse |
| JavaScript de la app embellecido | 8 bundles principales (~10 MB) | Legible pero con nombres minificados |

## Lo que se recupera de verdad

### 1. Librerías (código fuente real)

Los paquetes de terceros publican `.map` con el fuente incrustado:

```
recuperado/fuentes-librerias/
  @azure/msal-browser/…   146 ficheros
  @azure/msal-node/…       66
  @typespec/ts-http-runtime/… 30
  @azure/identity/…        20
  …
```

Esos ficheros son TypeScript/JS **original**, no minificado.

### 2. Estructura de módulos de Termius

Los *chunks* de Vite se llaman `Nombre-<hash>.js`, así que el nombre original
del módulo sobrevive:

```
ui-process (733 módulos): Hosts, Keychain, SFTP, vault, reconnectSaga,
  SnackbarController, settings, terminal, portForwarding …
main-process (1): main-process
background-process (5): main, Sha256WebCrypto …
```

Ver [`ESTRUCTURA-MODULOS.md`](ESTRUCTURA-MODULOS.md).

### 3. Lo que NO se recupera

- Código propio de Termius como fuente original (no hay maps).
- Nombres de funciones y variables (minificados; algunos se pueden inferir por
  contexto, no recuperar).
- Ficheros que no están en el paquete (builds de servidor, tests, historial).

## Herramientas probadas

| Herramienta | Resultado |
|---|---|
| `prettier` | embellece (lo que se usa en `legible/`) |
| `webcrack` | embellece y aplica transforms, pero **no** des-empaqueta chunks ESM de Vite ni recupera nombres |
| `termius-ia` | IA local/nube para leer el código embellecido y responder preguntas |

Un `.map` sin `sourcesContent` solo da nombres de fichero y mapeo de líneas, no
código. Los 1.627 `.map` del paquete son en su mayoría `.d.ts.map` de tipos.

## Reproducirlo

```bash
termius-ia preparar Termius.deb     # extrae y embellece
termius-recuperar                   # fuentes de librerías + estructura
termius-ia preguntar "…"            # pregunta al código recuperado
```

## Detalle importante al reempaquetar

El `app.asar` original tiene **77 entradas "unpacked"** (módulos nativos como
`libtermius`, `keytar`, `libfido2`): su contenido **no está dentro del asar**,
vive en `app.asar.unpacked/`. Si se extrae solo el asar, esos ficheros quedan
truncados (por ejemplo, `package.json` inválidos) y la app reconstruida **no
arranca**: falla con *"Invalid package config …/node_modules/@termius/libtermius/package.json"*.

Solución ya incluida en `termius-ia preparar`: copia `app.asar.unpacked/` sobre
el árbol extraído. Con eso, reempaquetar con `@electron/asar --unpack-dir
node_modules` produce un asar que **arranca correctamente** (comprobado: se ve
la pantalla de bienvenida de Termius).

## Conclusión honesta

Si buscas "el código fuente de Termius", no existe en el paquete y ninguna
herramienta lo va a inventar. Lo que tienes es:

1. **su JavaScript ejecutable**, embellecido y modificable (y reempaquetable con
   `termius-repack`);
2. **el mapa de 743 módulos** para saber qué hace cada parte;
3. **el fuente real de las librerías** que usa.

Con eso se puede estudiar la app, parchearla para uso personal y entender su
arquitectura — pero no reconstruir su repositorio original.
