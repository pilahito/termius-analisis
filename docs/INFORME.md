# Termius 10.4.1 — informe de ingeniería inversa

Análisis estático de la aplicación de escritorio **Termius 10.4.1** a partir del
paquete `Termius.deb` (Linux x64). Solo lectura: no se ejecutó la aplicación.

- Fecha: 2026-11-21
- Paquete original: `Termius.deb` (149 MB)
- Contenido: `app.asar` de 159 MB → 8.869 ficheros, 221 MB descomprimidos
- Método: extracción del `.deb`, desempaquetado del `app.asar`, embellecido con
  Prettier de los 8 bundles principales y análisis por partes (búsquedas de texto
  y lectura de fragmentos).
- Este informe **no incluye código** de Termius; solo observaciones con
  referencias `fichero:línea` sobre la copia local.

---

## 1. Qué es y qué trae

| Dato | Valor |
|---|---|
| Nombre / versión | Termius **10.4.1** |
| Runtime | Electron **43.8.1**, Chromium 150, Node 24 |
| Entry | `main-process/main-process.js` |
| Empaquetado | Electron + `app.asar`; renderer construido con **Vite/Rollup** |
| `package.json` | sin campo `scripts`; `engines.node 24.22.0` |
| Paquetes propios | 11 `@termius/*` (libtermius, mosh, node-pty, libfido2, keytar, serialport-bindings, registry-js, minidump-parser…) |

**No hay código fuente original**: los bundles están minificados y **no hay
source maps con `sourcesContent`** (los 1.627 `.map` son `.d.ts.map` de
`node_modules`). Lo máximo obtenible es JavaScript embellecido.

---

## 2. Arquitectura

```
┌─────────────┐   Redux (electron-redux)   ┌──────────────┐
│ ui-process  │ ◄────────────────────────► │ main-process │
│ (React 18)  │   ipcRenderer + remote     │  (Electron)  │
└─────┬───────┘                            └──────┬───────┘
      │ @electron/remote + módulos Node en window  │
      │                                            │ utilityProcess
      └─────────────► service-process (PTY, ssh) ◄─┘
```

- **Multi-ventana** con un store Redux por ventana, sincronizado por
  `electron-redux` (`forwardToMain` / `replayActionRenderer`). El main process es
  la fuente de verdad; el estado inicial llega por **IPC síncrono**
  (`ipcRenderer.sendSync("init-redux")`).
- **~50 slices** de Redux Toolkit (`entities, user, sync, terminal, workspace,
  navigation, layout, dialogs, vault, sshid, windows, appUpdate…`).
- **Router propio** sobre Redux (no react-router): `currentPathSelector` +
  rutas que se ocultan con `display:none` ("keep-alive"), para conservar
  terminales y formularios.
- **UI**: React 18.2, MUI v5 + emotion/tss-react, react-hook-form + zod,
  @dnd-kit, xstate, lottie, Fuse.js.
- **SSH/SFTP/mosh/serial**: **binarios nativos** (`@termius/libtermius`,
  `node-pty`, `@termius/mosh`, `libfido2`), ejecutados en un `utilityProcess`
  (`service-process`). El JS solo gestiona estado y UI.

### Ventanas y rutas

- Pestañas base: **Hosts, Keychain, SFTP, Port Forwarding, Snippets,
  Known Hosts, Logs**.
- Rutas: `/hosts`, `/keychain`, `/sftp`, `/pf`, `/snippets`, `/knownhosts`,
  `/logs/`, `/tabs/terminals/<id>`, `/tabs/new/`.
- Ajustes en **ventana aparte**: `/account`, `/manage-team`, `/vaults`,
  `/sshid`, `/invite-people`, `/terminal`, `/sftp`, `/logs`, `/shortcuts`.

---

## 3. Conexiones y reconexión

- Protocolos: **ssh, mosh, telnet, local, serial, stream** (`LiveTerminal`).
- Reintento: cola `terminalReconnectQueue` + temporizador con **espera fija de
  30 s y tope de 60 s** (`Math.min(timer + 3e4, 6e4)`) — no es backoff
  exponencial.
- Máquina de conexión por pasos: `protocol → identity → authInteractive →
  fingerprint → requestPassphrase/PIN → keyboardInteractive → requestSignature →
  discoverableKeys/chooseKey → requestSKPresence → setupShellIntegration →
  chooseSSHid*Passkeys → hostChainConnection`.
- Identidades: password, ssh key y **hardware key (FIDO2/Secure Enclave)**;
  passkeys con `sshid.io`.
- Verificación de host key delegada a la UI (`delegate.hostVerifier`);
  `known_hosts` en `~/.ssh/known_hosts`.
- Soporta **cadenas de salto** (`host_chain`), proxy HTTP (3128) y SOCKS (1080),
  agent forwarding, keep-alive y mosh.

---

## 4. Cifrado, cuentas y sincronización

- Bóvedas con `encryptionKeyId` / `encrypted_with`; el **KDF no está en JS**
  (vive en nativo). No se observan argon2/pbkdf2 en el renderer.
- Almacén de secretos: **`@termius/keytar`** (libsecret en Linux) desde el
  proceso background; no usa `safeStorage` de Electron.
- Backend: `api.termius.com`, `account.termius.com`, `sshid.io`; tiempo real vía
  **Centrifuge**; sync con acciones `CLOUD_SYNC_*`.
- **HIBP** (k-anonimato SHA-1) para comprobar contraseñas filtradas y
  **zxcvbn** para medir su fortaleza.

---

## 5. Seguridad: lo observado (importante)

1. `nodeIntegration: true` y `contextIsolation: false` en **sus propias
   ventanas**; solo la ventana de contenido web externo va endurecida.
2. Inyección deliberada de `require` con `fs` y `child_process` en `window`
   (`Symbol.for("preloadedModulesKey")`).
3. **`@electron/remote` habilitado** (desaconsejado por Electron): `app`,
   `BrowserWindow` y `require` al alcance del renderer.
4. Pinning SHA-256 **solo** para `api.termius.com` y gateado por un toggle
   ("SSL Pinning") **apagado por defecto**.
5. Auto-update contra **S3 privado** (`termius.desktop.autoupdate`,
   `publishAutoUpdate: false`); instalación con `mv`/`execFileSync`.
6. AppArmor instalado por el `.deb` en modo **complain** (no enforcing).
7. Socket IPC (node-ipc) bajo `userDataPath` sin verificación de peer visible.
8. Deeplinks `termius://` y `open-external` sin validación estricta de esquema
   en lo leído.

> Un XSS/inyección en el renderer equivaldría a ejecución local, dada la
> configuración anterior.

---

## 6. Extras del producto

- Autocompletado de shell estilo Fig con specs de `git`, `vault`, `mongocli` y
  `github` (cargados desde `@termius/autocomplete/specs/*.json`).
- Terminal propio sobre **xterm.js** (núcleo, sin addons de Fit/WebLinks/Search/
  WebGL visibles).
- Integraciones de nube: paquetes de **Azure** (`@azure/arm-*`, `identity`) para
  hosts cloud; `vault-b0b69edd.js` es el spec de autocompletado de la CLI de
  HashiCorp Vault, **no** un cliente Vault.
- `main-5a6e40ee.js` es **zxcvbn**, no el proceso principal.

---

## 7. Límites de este análisis

- **Sin código fuente**: solo JS minificado; los nombres originales son opacos.
- Bundle **incompleto por partes**: 611 `import()` a chunks que no se
  embellecieron; la lógica de bóvedas/cifrado puede estar en ellos.
- No se ejecutó la app: no hay evidencia de comportamiento en runtime, ni
  validación real de cada canal IPC, ni contenido del keyring.
- Versiones exactas de MUI/xterm y del cliente Centrifuge no legibles.
- No se determinó si el updater valida firma además de sha512.

---

## 8. ¿Se puede reconstruir la app?

**Sí, a partir de lo extraído** (no hay que "reinventarla"): el `app.asar`
contiene el JavaScript real que se ejecuta. Reempaquetarlo produce un `.deb`
funcional:

- el árbol extraído se coloca como `resources/app/` (Electron lo carga igual) o
  se vuelve a empaquetar como `resources/app.asar`;
- se conserva el `control` original (`Package: termius-app`, `Version: 10.4.1`,
  `Depends: libgtk-3-0, libnotify4, …`);
- se remonta `data.tar.xz` y el archivo `ar`.

Verificado: el `.deb` reconstruido (191 MB con compresión rápida) mantiene la
estructura y los metadatos. Lo que **no** se puede recuperar son los nombres
originales ni el TypeScript: sigue siendo el mismo JavaScript minificado.

## 9. Aviso legal

Termius es software **propietario**. Este informe documenta observaciones
técnicas para estudio e interoperabilidad en el equipo del autor. **No se
distribuye código de Termius** ni el paquete original.
