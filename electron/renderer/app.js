const api = window.electronAPI;

const backendStatusEl = document.getElementById("backend-status");
const backendUrlEl = document.getElementById("backend-url");

const chatEl = document.getElementById("chat");
const chatFormEl = document.getElementById("chat-form");
const promptEl = document.getElementById("prompt");
const sendBtn = document.getElementById("send-btn");
const stopBtn = document.getElementById("stop-btn");
const ragModeEl = document.getElementById("rag-mode");

const pickFileBtn = document.getElementById("pick-file-btn");
const uploadFileNameEl = document.getElementById("upload-file-name");
const operatorEl = document.getElementById("operator");
const uploadBtn = document.getElementById("upload-btn");
const uploadResultEl = document.getElementById("upload-result");

const syncBtn = document.getElementById("sync-btn");
const snapshotTagEl = document.getElementById("snapshot-tag");
const snapshotBtn = document.getElementById("snapshot-btn");
const rollbackSnapshotEl = document.getElementById("rollback-snapshot");
const rollbackBtn = document.getElementById("rollback-btn");
const opsResultEl = document.getElementById("ops-result");

let selectedUploadFilePath = "";
let activeRequestId = null;
const streamNodes = new Map();

function setBackendStatus(type, text) {
  backendStatusEl.className = `status-badge ${type}`;
  backendStatusEl.textContent = text;
}

function appendMessage(role, text) {
  const node = document.createElement("div");
  node.className = `msg ${role}`;
  node.textContent = text;
  chatEl.appendChild(node);
  chatEl.scrollTop = chatEl.scrollHeight;
  return node;
}

function trimForPreview(text, maxLength = 120) {
  if (!text) {
    return "";
  }
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength)}...`;
}

function formatReferences(references) {
  if (!Array.isArray(references) || references.length === 0) {
    return "";
  }

  const lines = references.slice(0, 3).map((item, index) => {
    const source = item?.metadata?.source || "unknown";
    const snippet = trimForPreview(item?.content || "");
    return `${index + 1}. [${source}] ${snippet}`;
  });

  return `\n\n参考片段:\n${lines.join("\n")}`;
}

function setUploadResult(message, state = "") {
  uploadResultEl.textContent = message;
  uploadResultEl.classList.remove("success", "error");
  if (state) {
    uploadResultEl.classList.add(state);
  }
}

function setOpsResult(value) {
  if (typeof value === "string") {
    opsResultEl.textContent = value;
    return;
  }
  opsResultEl.textContent = JSON.stringify(value, null, 2);
}

function getRequestId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function setChatFormPending(pending) {
  sendBtn.disabled = pending;
  stopBtn.disabled = !pending;
}

async function bootstrapBackend() {
  if (!api) {
    setBackendStatus("error", "后端状态: Electron API 不可用");
    appendMessage(
      "assistant",
      "初始化失败: preload API 未注入。请检查 Electron 配置。",
    );
    return;
  }

  setBackendStatus("pending", "后端状态: 启动中...");

  try {
    const info = await api.getAppInfo();
    backendUrlEl.textContent = `后端地址: ${info.backendUrl}`;

    const result = await api.ensureBackendStarted();
    if (!result?.ok) {
      throw new Error(result?.error || "后端启动失败");
    }

    const suffix = result.startedByElectron
      ? "（由Electron拉起）"
      : "（已运行）";
    setBackendStatus("ok", `后端状态: 运行中${suffix}`);
  } catch (error) {
    setBackendStatus("error", "后端状态: 启动失败");
    appendMessage("assistant", `后端初始化失败: ${error.message}`);
  }
}

api.onChatChunk(({ requestId, chunk }) => {
  const node = streamNodes.get(requestId);
  if (!node) {
    return;
  }
  node.textContent += chunk;
  chatEl.scrollTop = chatEl.scrollHeight;
});

api.onChatDone(({ requestId }) => {
  streamNodes.delete(requestId);
  if (activeRequestId === requestId) {
    activeRequestId = null;
    setChatFormPending(false);
    promptEl.focus();
  }
});

api.onChatError(({ requestId, error }) => {
  const node = streamNodes.get(requestId);
  if (node) {
    node.textContent += `\n\n请求失败: ${error}`;
    streamNodes.delete(requestId);
  }

  if (activeRequestId === requestId) {
    activeRequestId = null;
    setChatFormPending(false);
  }
});

chatFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();

  const prompt = (promptEl.value || "").trim();
  if (!prompt || activeRequestId) {
    return;
  }

  appendMessage("user", prompt);
  promptEl.value = "";
  const assistantNode = appendMessage("assistant", "正在处理中...");
  setChatFormPending(true);

  try {
    if (ragModeEl.checked) {
      const result = await api.queryRag(prompt);
      const answer = (result?.answer || "").trim() || "未生成有效回答";
      assistantNode.textContent = `${answer}${formatReferences(result?.references)}`;
      setChatFormPending(false);
      promptEl.focus();
      return;
    }

    const requestId = getRequestId();
    activeRequestId = requestId;
    assistantNode.textContent = "";
    streamNodes.set(requestId, assistantNode);
    api.startChatStream(requestId, prompt);
  } catch (error) {
    assistantNode.textContent = `请求失败: ${error.message}`;
    setChatFormPending(false);
    promptEl.focus();
  }
});

stopBtn.addEventListener("click", () => {
  if (!activeRequestId) {
    return;
  }
  api.cancelChatStream(activeRequestId);
});

pickFileBtn.addEventListener("click", async () => {
  try {
    const result = await api.selectUploadFile();
    if (result?.canceled) {
      return;
    }

    selectedUploadFilePath = result.filePath;
    uploadFileNameEl.textContent = result.fileName || selectedUploadFilePath;
    setUploadResult("", "");
  } catch (error) {
    setUploadResult(`选择文件失败: ${error.message}`, "error");
  }
});

uploadBtn.addEventListener("click", async () => {
  if (!selectedUploadFilePath) {
    setUploadResult("请先选择 txt 文件", "error");
    return;
  }

  uploadBtn.disabled = true;
  setUploadResult("正在上传并写入知识库，请稍候...");

  try {
    const operator = (operatorEl.value || "web").trim() || "web";
    const payload = await api.uploadKnowledge(selectedUploadFilePath, operator);
    setUploadResult(payload?.result || "上传成功", "success");
  } catch (error) {
    setUploadResult(`上传失败: ${error.message}`, "error");
  } finally {
    uploadBtn.disabled = false;
  }
});

syncBtn.addEventListener("click", async () => {
  syncBtn.disabled = true;
  setOpsResult("正在同步失效源文件...");

  try {
    const result = await api.syncKnowledge();
    setOpsResult(result);
  } catch (error) {
    setOpsResult(`同步失败: ${error.message}`);
  } finally {
    syncBtn.disabled = false;
  }
});

snapshotBtn.addEventListener("click", async () => {
  snapshotBtn.disabled = true;
  setOpsResult("正在创建快照...");

  try {
    const tag = (snapshotTagEl.value || "").trim();
    const result = await api.snapshotKnowledge(tag);
    setOpsResult(result);
  } catch (error) {
    setOpsResult(`创建快照失败: ${error.message}`);
  } finally {
    snapshotBtn.disabled = false;
  }
});

rollbackBtn.addEventListener("click", async () => {
  const snapshot = (rollbackSnapshotEl.value || "").trim();
  if (!snapshot) {
    setOpsResult("请输入快照目录名");
    return;
  }

  rollbackBtn.disabled = true;
  setOpsResult("正在回滚快照...");

  try {
    const result = await api.rollbackKnowledge(snapshot);
    setOpsResult(result);
  } catch (error) {
    setOpsResult(`回滚失败: ${error.message}`);
  } finally {
    rollbackBtn.disabled = false;
  }
});

appendMessage("assistant", "桌面端已启动。正在检查后端状态...");
bootstrapBackend();
