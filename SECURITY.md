# Security posture — Boot Doctor Electron shell

- `contextIsolation` = true, `nodeIntegration` = false on the BrowserWindow
- preload sandbox exposes only `window.bootDoctor.scan()` and `window.bootDoctor.getLastResult()`
- IPC allow-list: Electron only handles `bootDoctor:scan` and `bootDoctor:getLastResult` (both take no args)
- `will-navigate` is prevented, `window.open` calls are denied, permissions are rejected by default
- Renderer enforces a strict CSP (default-src 'self', script-src 'self', etc.) and loads logic from `renderer.js`
- UI does not execute arbitrary scripts and uses a single hand-off point into the preload bridge


