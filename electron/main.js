const { app, BrowserWindow, dialog, ipcMain } = require("electron");
const { spawn } = require("child_process");
const fs = require("fs");
const path = require("path");
const { pathToFileURL } = require("url");

const PROJECT_ROOT = path.resolve(__dirname, "..");
const RENDERER_ENTRY = path.join(__dirname, "renderer", "index.html");
const DEFAULT_BACKEND_URL = "http://127.0.0.1:7860";
const BACKEND_STARTUP_TIMEOUT_MS = Number(
  process.env.BACKEND_STARTUP_TIMEOUT_MS || 45000,
);

let mainWindow = null;
let backendProcess = null;
let backendManagedByElectron = false;
const chatAbortControllers = new Map();
let runtimeBackendUrl = "";
let runtimeApiKey = String(
  process.env.OPENAI_API_KEY || process.env.SILICONFLOW_API_KEY || "",
).trim();

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function normalizeError(error) {
  if (!error) {
    return "unknown error";
  }
  if (typeof error === "string") {
    return error;
  }
  if (error.message) {
    return String(error.message);
  }
  return String(error);
}

function normalizeBackendUrl(value) {
  const trimmed = String(value || "").trim();
  if (!trimmed) {
    return DEFAULT_BACKEND_URL;
  }

  const noTrailingSlash = trimmed.replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(noTrailingSlash)) {
    return `http://${noTrailingSlash}`;
  }
  return noTrailingSlash;
}

function getBackendUrl() {
  if (!runtimeBackendUrl) {
    runtimeBackendUrl = normalizeBackendUrl(
      process.env.BACKEND_URL || DEFAULT_BACKEND_URL,
    );
  }
  return runtimeBackendUrl;
}

function buildBackendEnv() {
  const env = { ...process.env, BACKEND_URL: getBackendUrl() };
  if (runtimeApiKey) {
    env.OPENAI_API_KEY = runtimeApiKey;
    if (!env.SILICONFLOW_API_KEY) {
      env.SILICONFLOW_API_KEY = runtimeApiKey;
    }
  }
  return env;
}

function stopManagedBackend() {
  return new Promise((resolve) => {
    if (!backendProcess || !backendManagedByElectron || backendProcess.killed) {
      resolve();
      return;
    }

    const processRef = backendProcess;
    let settled = false;
    const done = () => {
      if (settled) {
        return;
      }
      settled = true;
      backendProcess = null;
      backendManagedByElectron = false;
      resolve();
    };

    processRef.once("exit", done);
    processRef.kill();
    setTimeout(done, 3000);
  });
}

function loadDotEnv() {
  const envPath = path.join(PROJECT_ROOT, ".env");
  if (!fs.existsSync(envPath)) {
    return;
  }

  const text = fs.readFileSync(envPath, "utf-8");
  const lines = text.split(/\r?\n/);

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }

    const idx = trimmed.indexOf("=");
    if (idx <= 0) {
      continue;
    }

    const key = trimmed.slice(0, idx).trim();
    if (!key || process.env[key]) {
      continue;
    }

    let value = trimmed.slice(idx + 1).trim();
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    process.env[key] = value;
  }
}

function resolvePythonExecutable() {
  const candidates = [
    process.env.PYTHON_EXE,
    path.join(PROJECT_ROOT, ".venv", "Scripts", "python.exe"),
    path.join(PROJECT_ROOT, "venv", "Scripts", "python.exe"),
    "python",
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (candidate.toLowerCase() === "python") {
      return candidate;
    }
    if (fs.existsSync(candidate)) {
      return candidate;
    }
  }

  return "python";
}

async function checkBackendHealth() {
  try {
    const response = await fetch(`${getBackendUrl()}/api/health`);
    if (!response.ok) {
      return false;
    }
    const data = await response.json();
    return data && data.status === "ok";
  } catch (_error) {
    return false;
  }
}

async function waitBackendReady(timeoutMs) {
  const startedAt = Date.now();
  while (Date.now() - startedAt < timeoutMs) {
    if (await checkBackendHealth()) {
      return true;
    }
    await sleep(800);
  }
  return false;
}

async function ensureBackendStarted(options = {}) {
  const forceRestart = Boolean(options?.forceRestart);

  if (forceRestart) {
    await stopManagedBackend();
  }

  if (!forceRestart && (await checkBackendHealth())) {
    return { ok: true, startedByElectron: false, backendUrl: getBackendUrl() };
  }

  if (backendProcess && !backendProcess.killed) {
    const ready = await waitBackendReady(BACKEND_STARTUP_TIMEOUT_MS);
    if (ready) {
      return {
        ok: true,
        startedByElectron: backendManagedByElectron,
        backendUrl: getBackendUrl(),
      };
    }
    return {
      ok: false,
      error: "后端启动超时，请检查 Python 环境与 OPENAI_API_KEY 配置。",
    };
  }

  loadDotEnv();
  const pythonExe = resolvePythonExecutable();

  try {
    backendProcess = spawn(pythonExe, ["-m", "app.main"], {
      cwd: PROJECT_ROOT,
      env: buildBackendEnv(),
      windowsHide: true,
      shell: false,
      stdio: ["ignore", "pipe", "pipe"],
    });
    backendManagedByElectron = true;

    backendProcess.stdout.on("data", (buf) => {
      const text = String(buf || "").trim();
      if (text) {
        console.log(`[backend] ${text}`);
      }
    });

    backendProcess.stderr.on("data", (buf) => {
      const text = String(buf || "").trim();
      if (text) {
        console.error(`[backend] ${text}`);
      }
    });

    backendProcess.on("exit", (code, signal) => {
      console.log(`[backend] process exited code=${code} signal=${signal}`);
      backendProcess = null;
      backendManagedByElectron = false;
    });
  } catch (error) {
    return { ok: false, error: `无法启动后端服务: ${normalizeError(error)}` };
  }

  const ready = await waitBackendReady(BACKEND_STARTUP_TIMEOUT_MS);
  if (!ready) {
    return { ok: false, error: "后端启动超时，请检查 Python 环境与配置。" };
  }

  return { ok: true, startedByElectron: true, backendUrl: getBackendUrl() };
}

async function parseResponse(response) {
  const contentType = (
    response.headers.get("content-type") || ""
  ).toLowerCase();
  if (contentType.includes("application/json")) {
    return response.json();
  }
  const text = await response.text();
  return { text };
}

async function requestJson(pathname, init) {
  const response = await fetch(`${getBackendUrl()}${pathname}`, init);
  const payload = await parseResponse(response);

  if (!response.ok) {
    const message =
      payload && payload.error ? payload.error : `HTTP ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

function buildRequestId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1220,
    height: 880,
    minWidth: 1000,
    minHeight: 720,
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: true,
    },
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });

  mainWindow.loadURL(pathToFileURL(RENDERER_ENTRY).toString());
}

ipcMain.handle("app:get-info", () => {
  return {
    name: app.getName(),
    version: app.getVersion(),
    platform: process.platform,
    backendUrl: getBackendUrl(),
  };
});

ipcMain.handle("backend:update-connection", async (_event, payload) => {
  const hasBackendUrl =
    payload && Object.prototype.hasOwnProperty.call(payload, "backendUrl");
  const hasApiKey =
    payload && Object.prototype.hasOwnProperty.call(payload, "apiKey");

  if (hasBackendUrl) {
    runtimeBackendUrl = normalizeBackendUrl(payload.backendUrl);
  }
  if (hasApiKey) {
    runtimeApiKey = String(payload.apiKey || "").trim();
  }

  return {
    ok: true,
    backendUrl: getBackendUrl(),
    hasApiKey: Boolean(runtimeApiKey),
  };
});

ipcMain.handle("backend:health", async () => {
  const healthy = await checkBackendHealth();
  return { healthy };
});

ipcMain.handle("backend:ensure-started", async (_event, options) => {
  return ensureBackendStarted(options || {});
});

ipcMain.handle("backend:rag-query", async (_event, prompt) => {
  const normalizedPrompt = String(prompt || "").trim();
  if (!normalizedPrompt) {
    throw new Error("prompt is required");
  }

  return requestJson("/api/rag/query", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt: normalizedPrompt }),
  });
});

ipcMain.handle("backend:knowledge-upload", async (_event, payload) => {
  const filePath = String(payload?.filePath || "").trim();
  const operator = String(payload?.operator || "web").trim() || "web";

  if (!filePath) {
    throw new Error("filePath is required");
  }
  if (!fs.existsSync(filePath)) {
    throw new Error("file not found");
  }
  if (!filePath.toLowerCase().endsWith(".txt")) {
    throw new Error("only .txt file is supported");
  }

  const fileName = path.basename(filePath);
  const fileBuffer = await fs.promises.readFile(filePath);

  const form = new FormData();
  form.append(
    "file",
    new Blob([fileBuffer], { type: "text/plain;charset=utf-8" }),
    fileName,
  );
  form.append("operator", operator);

  return requestJson("/api/knowledge/upload", {
    method: "POST",
    body: form,
  });
});

ipcMain.handle("backend:knowledge-sync", async () => {
  return requestJson("/api/knowledge/sync", {
    method: "POST",
  });
});

ipcMain.handle("backend:knowledge-snapshot", async (_event, tag) => {
  return requestJson("/api/knowledge/snapshot", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ tag: String(tag || "").trim() }),
  });
});

ipcMain.handle("backend:knowledge-rollback", async (_event, snapshot) => {
  const snapshotName = String(snapshot || "").trim();
  if (!snapshotName) {
    throw new Error("snapshot is required");
  }

  return requestJson("/api/knowledge/rollback", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ snapshot: snapshotName }),
  });
});

ipcMain.handle("dialog:select-upload-file", async () => {
  if (!mainWindow) {
    throw new Error("main window is not ready");
  }

  const result = await dialog.showOpenDialog(mainWindow, {
    title: "选择知识库文本文件",
    properties: ["openFile"],
    filters: [{ name: "Text", extensions: ["txt"] }],
  });

  if (result.canceled || !result.filePaths.length) {
    return { canceled: true };
  }

  const filePath = result.filePaths[0];
  return {
    canceled: false,
    filePath,
    fileName: path.basename(filePath),
  };
});

ipcMain.on("backend:chat-stream:start", async (event, payload) => {
  const requestId = String(payload?.requestId || "").trim() || buildRequestId();
  const prompt = String(payload?.prompt || "").trim();

  if (!prompt) {
    event.sender.send("backend:chat-stream:error", {
      requestId,
      error: "prompt is required",
    });
    return;
  }

  const controller = new AbortController();
  chatAbortControllers.set(requestId, controller);

  try {
    const response = await fetch(`${getBackendUrl()}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
      signal: controller.signal,
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || `HTTP ${response.status}`);
    }

    const reader =
      response.body && response.body.getReader
        ? response.body.getReader()
        : null;
    if (!reader) {
      throw new Error("chat stream is unavailable");
    }

    const decoder = new TextDecoder("utf-8");
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      const chunk = decoder.decode(value, { stream: true });
      if (chunk) {
        event.sender.send("backend:chat-stream:chunk", { requestId, chunk });
      }
    }

    const tail = decoder.decode();
    if (tail) {
      event.sender.send("backend:chat-stream:chunk", {
        requestId,
        chunk: tail,
      });
    }

    event.sender.send("backend:chat-stream:done", { requestId });
  } catch (error) {
    const errorMessage = controller.signal.aborted
      ? "请求已取消"
      : normalizeError(error);
    event.sender.send("backend:chat-stream:error", {
      requestId,
      error: errorMessage,
    });
  } finally {
    chatAbortControllers.delete(requestId);
  }
});

ipcMain.on("backend:chat-stream:cancel", (_event, requestId) => {
  const key = String(requestId || "").trim();
  const controller = chatAbortControllers.get(key);
  if (!controller) {
    return;
  }

  controller.abort();
  chatAbortControllers.delete(key);
});

app.whenReady().then(() => {
  createMainWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

app.on("before-quit", () => {
  for (const controller of chatAbortControllers.values()) {
    controller.abort();
  }
  chatAbortControllers.clear();

  if (backendProcess && backendManagedByElectron && !backendProcess.killed) {
    backendProcess.kill();
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
