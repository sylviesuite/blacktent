const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("bootDoctor", {
  scan: () => ipcRenderer.invoke("bootDoctor:scan"),
  getLastResult: () => ipcRenderer.invoke("bootDoctor:getLastResult"),
});

contextBridge.exposeInMainWorld("redaction", {
  selectFile: () => ipcRenderer.invoke("redaction:selectFile"),
  readFileText: (path) => ipcRenderer.invoke("redaction:readFileText", path),
  ...(process.env.NODE_ENV === "development"
    ? {
        __devTestReadFile: (type) => {
          switch (type) {
            case "smallText":
              return Promise.resolve({
                ok: true,
                text: "dev text preview\n".repeat(10),
              });
            case "tooLarge":
              return Promise.resolve({
                ok: false,
                error: "File too large for preview",
              });
            case "binary":
              return Promise.resolve({
                ok: false,
                error: "Binary file not supported",
              });
            default:
              return Promise.resolve({ ok: false, error: "Unknown test case" });
          }
        },
      }
    : {}),
});

