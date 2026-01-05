const { app, BrowserWindow, ipcMain } = require("electron");
const path = require("path");
const { execFile } = require("child_process");

function safeJson(obj) {
  try {
    return JSON.parse(obj);
  } catch {
    return null;
  }
}

const isDev = process.env.NODE_ENV !== "production";

function createWindow() {
  const win = new BrowserWindow({
    width: 1024,
    height: 720,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  win.loadFile(path.join(__dirname, "index.html"));

  if (isDev) {
    win.webContents.openDevTools({ mode: "detach" });
  }
}

app.on("ready", createWindow);

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

ipcMain.handle("bootDoctor:scan", async () => {
  return new Promise((resolve) => {
    execFile(
      "python",
      ["-m", "blacktent", "doctor", "boot", "--json"],
      { cwd: process.cwd(), windowsHide: true },
      (err, stdout, stderr) => {
        if (err) {
          resolve({
            status: "warning",
            checks: [],
            suggested_url: null,
            error: err.message || stderr || "Boot Doctor command failed",
          });
          return;
        }
        const parsed = safeJson(stdout);
        if (!parsed) {
          resolve({
            status: "warning",
            checks: [],
            suggested_url: null,
            error: "Failed to parse Boot Doctor JSON output",
          });
          return;
        }
        resolve(parsed);
      }
    );
  });
});

