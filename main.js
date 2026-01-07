const { app, BrowserWindow, ipcMain, dialog } = require("electron");
const path = require("path");
const { execFile } = require("child_process");
const fs = require("fs");

function safeJson(obj) {
  try {
    return JSON.parse(obj);
  } catch {
    return null;
  }
}

const isDev = process.env.NODE_ENV !== "production";
let lastScanResult = null;

function createWindow() {
  const win = new BrowserWindow({
    width: 1024,
    height: 720,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, "preload.js"),
    },
  });

  win.loadFile(path.join(__dirname, "index.html"));

  if (isDev) {
    win.webContents.openDevTools({ mode: "detach" });
  }

  win.webContents.on("will-navigate", (event) => {
    event.preventDefault();
  });
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.session.setPermissionRequestHandler((_wc, _permission, callback) => {
    callback(false);
  });
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

ipcMain.handle("bootDoctor:scan", async (_event, ...args) => {
  if (args.length > 0) {
    console.warn("bootDoctor:scan invoked with unexpected arguments", args);
    throw new Error("bootDoctor:scan does not take arguments");
  }
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
        lastScanResult = parsed;
        resolve(parsed);
      }
    );
  });
});

ipcMain.handle("bootDoctor:getLastResult", (_event, ...args) => {
  if (args.length > 0) {
    console.warn("bootDoctor:getLastResult invoked with arguments", args);
    throw new Error("bootDoctor:getLastResult does not take arguments");
  }
  if (!lastScanResult) {
    return {
      status: "warning",
      checks: [],
      suggested_url: null,
      error: "No scan available yet",
    };
  }
  return lastScanResult;
});

ipcMain.handle("redaction:selectFile", async (_event, ...args) => {
  if (args.length > 0) {
    console.warn("redaction:selectFile invoked with unexpected arguments", args);
    throw new Error("redaction:selectFile does not take arguments");
  }
  const result = await dialog.showOpenDialog({
    title: "Select a text file for Boot Doctor redaction",
    properties: ["openFile"],
    filters: [
      { name: "Text and logs", extensions: ["txt", "md", "log", "json", "csv"] },
      { name: "All Files", extensions: ["*"] },
    ],
  });
  if (result.canceled || !result.filePaths.length) {
    return { ok: false, error: "File selection canceled." };
  }
  const filePath = result.filePaths[0];
  try {
    const stats = fs.statSync(filePath);
    return {
      ok: true,
      path: filePath,
      name: path.basename(filePath),
      size: stats.size,
    };
  } catch (err) {
    return { ok: false, error: "Unable to stat selected file." };
  }
});

ipcMain.handle("redaction:readFile", async (_event, filePath, ...args) => {
  if (args.length > 0) {
    console.warn("redaction:readFile invoked with extra arguments", args);
    throw new Error("redaction:readFile accepts only one path argument");
  }
  if (typeof filePath !== "string") {
    return { ok: false, error: "Invalid file path." };
  }
  if (!path.isAbsolute(filePath)) {
    return { ok: false, error: "Path must be absolute." };
  }
  try {
    const stats = fs.statSync(filePath);
    const MAX_SIZE = 2 * 1024 * 1024;
    if (stats.size > MAX_SIZE) {
      return { ok: false, error: "File too large for preview." };
    }
    const data = fs.readFileSync(filePath);
    if (data.includes(0)) {
      return { ok: false, error: "Binary file not supported." };
    }
    const text = data.toString("utf8");
    return { ok: true, text };
  } catch (err) {
    return { ok: false, error: "Unable to read file." };
  }
});
ipcMain.handle("bootDoctor:getLastResult", (_event, ...args) => {
  if (args.length > 0) {
    console.warn("bootDoctor:getLastResult invoked with arguments", args);
    throw new Error("bootDoctor:getLastResult does not take arguments");
  }
  if (!lastScanResult) {
    return {
      status: "warning",
      checks: [],
      suggested_url: null,
      error: "No scan available yet",
    };
  }
  return lastScanResult;
});

