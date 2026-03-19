const api = window.electronAPI;

const backendStatusEl = document.getElementById("backend-status");
const backendUrlEl = document.getElementById("backend-url");

const chatEl = document.getElementById("chat");
const chatFormEl = document.getElementById("chat-form");
const promptEl = document.getElementById("prompt");
const sendBtn = document.getElementById("send-btn");
const stopBtn = document.getElementById("stop-btn");

let activeRequestId = null;
const streamNodes = new Map();

function setBackendStatus(type, text) {
  backendStatusEl.className = `status-badge ${type}`;
  backendStatusEl.textContent = text;
}

function escapeHTML(text) {
  return text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function renderMarkdown(text) {
  if (!text) return "";
  let html = escapeHTML(text);
  // code blocks ```
  html = html.replace(/```([\s\S]*?)```/g, (_, code) => `<pre><code>${code}</code></pre>`);
  // inline code
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  // bold and italic
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  // bullet lines
  html = html.replace(/^\s*-\s+(.*)$/gm, "<li>$1</li>");
  html = html.replace(/(<li>.*<\/li>)/gs, "<ul>$1</ul>");
  // line breaks
  html = html.replace(/\n/g, "<br>");
  return html;
}

function appendMessage(role, text) {
  const node = document.createElement("div");
  node.className = `msg ${role}`;
  node.innerHTML = renderMarkdown(text);
  chatEl.appendChild(node);
  chatEl.scrollTop = chatEl.scrollHeight;
  return node;
}

function setChatFormPending(pending) {
  sendBtn.disabled = pending;
  stopBtn.disabled = !pending;
}

async function bootstrapBackend() {
  if (!api) {
    setBackendStatus("error", "后端状态: Electron API 不可用");
    appendMessage("assistant", "初始化失败: preload API 未注入。请检查 Electron 配置。");
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

    const suffix = result.startedByElectron ? "（由Electron拉起）" : "（已运行）";
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
  node.innerHTML += renderMarkdown(chunk);
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
    node.innerHTML += renderMarkdown(`\n\n请求失败: ${error}`);
    streamNodes.delete(requestId);
  }

  if (activeRequestId === requestId) {
    activeRequestId = null;
    setChatFormPending(false);
  }
});

function getRequestId() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

chatFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();

  const prompt = (promptEl.value || "").trim();
  if (!prompt || activeRequestId) {
    return;
  }

  appendMessage("user", prompt);
  promptEl.value = "";
  const assistantNode = appendMessage("assistant", "处理中...");
  setChatFormPending(true);

  try {
    const requestId = getRequestId();
    activeRequestId = requestId;
    assistantNode.innerHTML = "";
    streamNodes.set(requestId, assistantNode);
    api.startChatStream(requestId, prompt);
  } catch (error) {
    assistantNode.innerHTML = renderMarkdown(`请求失败: ${error.message}`);
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

appendMessage("assistant", "桌面端已启动。正在检查后端状态...");
bootstrapBackend();
