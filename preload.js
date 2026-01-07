const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("bootDoctor", {
  scan: () => ipcRenderer.invoke("bootDoctor:scan"),
  getLastResult: () => ipcRenderer.invoke("bootDoctor:getLastResult"),
});

contextBridge.exposeInMainWorld("redaction", {
  selectFile: () => ipcRenderer.invoke("redaction:selectFile"),
  readFileText: (path) => ipcRenderer.invoke("redaction:readFileText", path),
});

