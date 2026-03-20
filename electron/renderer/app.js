const api = window.electronAPI;
const CONNECTION_STORAGE_KEY = "agent_studio_connection";

const backendStatusEl = document.getElementById("backend-status");
const backendUrlEl = document.getElementById("backend-url");
const apiUrlInputEl = document.getElementById("api-url-input");
const apiKeyInputEl = document.getElementById("api-key-input");
const showApiKeyEl = document.getElementById("show-api-key");
const saveConnBtnEl = document.getElementById("save-conn-btn");
const clearConnBtnEl = document.getElementById("clear-conn-btn");
const connHintEl = document.getElementById("conn-hint");

const chatEl = document.getElementById("chat");
const chatFormEl = document.getElementById("chat-form");
const promptEl = document.getElementById("prompt");
const sendBtn = document.getElementById("send-btn");
const stopBtn = document.getElementById("stop-btn");

let activeRequestId = null;
const streamStates = new Map();

function setBackendStatus(type, text) {
  backendStatusEl.className = `status-badge ${type}`;
  backendStatusEl.textContent = text;
}

function setConnectionHint(type, text) {
  connHintEl.className = type ? `conn-hint ${type}` : "conn-hint";
  connHintEl.textContent = text || "";
}

function normalizeBackendUrl(url) {
  const trimmed = String(url || "").trim();
  if (!trimmed) {
    return "http://127.0.0.1:7860";
  }

  const noTrailingSlash = trimmed.replace(/\/+$/, "");
  if (!/^https?:\/\//i.test(noTrailingSlash)) {
    return `http://${noTrailingSlash}`;
  }

  return noTrailingSlash;
}

function loadConnectionSettings() {
  try {
    const text = localStorage.getItem(CONNECTION_STORAGE_KEY);
    if (!text) {
      return null;
    }
    const data = JSON.parse(text);
    if (!data || typeof data !== "object") {
      return null;
    }
    return {
      backendUrl: normalizeBackendUrl(data.backendUrl),
      apiKey: String(data.apiKey || ""),
    };
  } catch (_error) {
    return null;
  }
}

function saveConnectionSettings(settings) {
  localStorage.setItem(
    CONNECTION_STORAGE_KEY,
    JSON.stringify({
      backendUrl: normalizeBackendUrl(settings.backendUrl),
      apiKey: String(settings.apiKey || ""),
    }),
  );
}

function collectConnectionSettings() {
  return {
    backendUrl: normalizeBackendUrl(apiUrlInputEl.value),
    apiKey: String(apiKeyInputEl.value || "").trim(),
  };
}

async function applyConnectionSettings({ forceRestart = false } = {}) {
  const settings = collectConnectionSettings();
  const updateResult = await api.updateConnection(
    settings.backendUrl,
    settings.apiKey,
  );
  backendUrlEl.textContent = `后端地址: ${updateResult.backendUrl}`;

  const startResult = await api.ensureBackendStarted({ forceRestart });
  if (!startResult?.ok) {
    throw new Error(startResult?.error || "后端启动失败");
  }

  const suffix = startResult.startedByElectron
    ? "（由Electron拉起）"
    : "（已运行）";
  setBackendStatus("ok", `后端状态: 运行中${suffix}`);
  return startResult;
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
  html = html.replace(
    /```([\s\S]*?)```/g,
    (_, code) => `<pre><code>${code}</code></pre>`,
  );
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

function renderAnswerLoading(answerEl, label = "模型思考中") {
  answerEl.classList.add("loading");
  answerEl.innerHTML = [
    `<span class="loading-label">${escapeHTML(label)}</span>`,
    '<span class="loading-dots" aria-hidden="true">',
    "<span></span><span></span><span></span>",
    "</span>",
  ].join("");
}

function stopAnswerLoading(state) {
  if (!state || !state.isLoading) {
    return;
  }

  state.isLoading = false;
  state.answerEl.classList.remove("loading");
  if (!state.hasConclusion) {
    state.answerEl.innerHTML = "";
  }
}

function createAssistantStreamMessage(placeholderText = "处理中...") {
  const node = document.createElement("div");
  node.className = "msg assistant rich-assistant";

  const answerEl = document.createElement("div");
  answerEl.className = "assistant-conclusion";
  renderAnswerLoading(answerEl, placeholderText || "模型思考中");

  const thoughtsEl = document.createElement("details");
  thoughtsEl.className = "assistant-thoughts";
  thoughtsEl.hidden = true;

  const summaryEl = document.createElement("summary");
  summaryEl.textContent = "查看思考过程";
  thoughtsEl.appendChild(summaryEl);

  const thoughtBodyEl = document.createElement("div");
  thoughtBodyEl.className = "assistant-thoughts-body";
  thoughtsEl.appendChild(thoughtBodyEl);

  node.appendChild(answerEl);
  node.appendChild(thoughtsEl);

  chatEl.appendChild(node);
  chatEl.scrollTop = chatEl.scrollHeight;

  return {
    node,
    answerEl,
    thoughtsEl,
    thoughtBodyEl,
    answerText: placeholderText,
    hasConclusion: false,
    thoughtLines: [],
    pendingBuffer: "",
    inToolResultBlock: false,
    isLoading: true,
  };
}

function parseToolNames(rawText) {
  const text = String(rawText || "");
  const names = [];
  const regex = /['\"]name['\"]\s*:\s*['\"]([^'\"]+)['\"]/g;
  let match;

  while ((match = regex.exec(text)) !== null) {
    const name = String(match[1] || "").trim();
    if (name && !names.includes(name)) {
      names.push(name);
    }
  }

  return names;
}

function normalizeThinkLine(state, line) {
  const trimmed = String(line || "").trim();
  if (!trimmed) {
    return "";
  }

  if (trimmed.startsWith("[THINK]")) {
    return trimmed.replace(/^\[THINK\]\s*/, "");
  }

  if (trimmed.startsWith("[tool_call]")) {
    const payload = trimmed.slice("[tool_call]".length).trim();
    const names = parseToolNames(payload);
    if (names.length) {
      return `正在调用工具：${names.join("、")}。`;
    }
    return "正在调用工具处理请求。";
  }

  if (trimmed.startsWith("[tool_error]")) {
    const detail = trimmed.slice("[tool_error]".length).trim();
    return detail ? `工具调用失败：${detail}` : "工具调用失败。";
  }

  const resultMatch = trimmed.match(/^\[([^\]]+)\s+result\]/i);
  if (resultMatch) {
    state.inToolResultBlock = true;
    return `已收到工具 ${resultMatch[1]} 的输出，正在整理结论。`;
  }

  if (/^(Q:|A:)/.test(trimmed)) {
    return trimmed;
  }

  if (/<invoke|<\/invoke>|<parameter|<\/parameter>/.test(trimmed)) {
    return "正在解析工具调用参数。";
  }

  if (state.inToolResultBlock) {
    if (/^(结论[:：]|最终答案[:：]|答案[:：]|建议[:：])/.test(trimmed)) {
      state.inToolResultBlock = false;
      return "";
    }
    return trimmed;
  }

  return "";
}

function appendThoughtLine(state, line) {
  const text = String(line || "").trim();
  if (!text) {
    return;
  }

  stopAnswerLoading(state);

  const lastLine = state.thoughtLines[state.thoughtLines.length - 1];
  if (lastLine === text) {
    return;
  }

  state.thoughtLines.push(text);
  state.thoughtsEl.hidden = false;
  state.thoughtBodyEl.innerHTML = state.thoughtLines
    .map(
      (item, index) =>
        `<div class="thought-line">${index + 1}. ${escapeHTML(item)}</div>`,
    )
    .join("");
}

function appendConclusionLine(state, line) {
  const text = String(line || "");
  if (!text.trim()) {
    return;
  }

  stopAnswerLoading(state);

  if (!state.hasConclusion) {
    state.answerText = "";
    state.hasConclusion = true;
  }

  state.answerText = state.answerText ? `${state.answerText}\n${text}` : text;
  state.answerEl.innerHTML = renderMarkdown(state.answerText);
}

function processStreamLine(state, line) {
  const thinkLine = normalizeThinkLine(state, line);
  if (thinkLine) {
    appendThoughtLine(state, thinkLine);
    return;
  }

  appendConclusionLine(state, line);
}

function consumeStreamChunk(state, chunk) {
  state.pendingBuffer += String(chunk || "");
  const lines = state.pendingBuffer.split(/\r?\n/);
  state.pendingBuffer = lines.pop() || "";

  for (const line of lines) {
    processStreamLine(state, line);
  }
}

function flushStreamState(state) {
  stopAnswerLoading(state);

  const tail = String(state.pendingBuffer || "").trim();
  if (tail) {
    processStreamLine(state, tail);
  }
  state.pendingBuffer = "";

  if (!state.hasConclusion) {
    const fallback = state.thoughtLines.length
      ? "结论：已完成推理，请展开思考过程查看详细步骤。"
      : "未生成有效结论，请重试或补充问题上下文。";
    state.answerText = fallback;
    state.hasConclusion = true;
    state.answerEl.innerHTML = renderMarkdown(fallback);
  }
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
    const saved = loadConnectionSettings();

    if (saved) {
      apiUrlInputEl.value = saved.backendUrl;
      apiKeyInputEl.value = saved.apiKey;
      setConnectionHint(
        "ok",
        "已加载本地保存的连接设置。可直接使用或修改后重新连接。",
      );
    } else {
      apiUrlInputEl.value = normalizeBackendUrl(info.backendUrl);
      setConnectionHint(
        "",
        "连接设置仅保存在当前桌面端本地。请填写后点击“保存并连接”。",
      );
    }

    await applyConnectionSettings({ forceRestart: false });
  } catch (error) {
    setBackendStatus("error", "后端状态: 启动失败");
    appendMessage("assistant", `后端初始化失败: ${error.message}`);
    setConnectionHint("error", `连接失败: ${error.message}`);
  }
}

if (api) {
  api.onChatChunk(({ requestId, chunk }) => {
    const state = streamStates.get(requestId);
    if (!state) {
      return;
    }

    consumeStreamChunk(state, chunk);
    chatEl.scrollTop = chatEl.scrollHeight;
  });

  api.onChatDone(({ requestId }) => {
    const state = streamStates.get(requestId);
    if (state) {
      flushStreamState(state);
      streamStates.delete(requestId);
    }

    if (activeRequestId === requestId) {
      activeRequestId = null;
      setChatFormPending(false);
      promptEl.focus();
    }
  });

  api.onChatError(({ requestId, error }) => {
    const state = streamStates.get(requestId);
    if (state) {
      appendConclusionLine(state, `请求失败: ${error}`);
      flushStreamState(state);
      streamStates.delete(requestId);
    }

    if (activeRequestId === requestId) {
      activeRequestId = null;
      setChatFormPending(false);
    }
  });
}

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
  const streamState = createAssistantStreamMessage("处理中...");
  setChatFormPending(true);

  try {
    const requestId = getRequestId();
    activeRequestId = requestId;
    streamStates.set(requestId, streamState);
    api.startChatStream(requestId, prompt);
  } catch (error) {
    appendConclusionLine(streamState, `请求失败: ${error.message}`);
    flushStreamState(streamState);
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

showApiKeyEl.addEventListener("change", () => {
  apiKeyInputEl.type = showApiKeyEl.checked ? "text" : "password";
});

saveConnBtnEl.addEventListener("click", async () => {
  if (!api) {
    setConnectionHint(
      "error",
      "Electron API 不可用，无法保存连接设置。请检查 preload 注入。",
    );
    return;
  }

  const settings = collectConnectionSettings();
  apiUrlInputEl.value = settings.backendUrl;
  saveConnectionSettings(settings);

  setConnectionHint("", "设置已保存，正在连接...");
  setBackendStatus("pending", "后端状态: 连接中...");
  try {
    await applyConnectionSettings({ forceRestart: true });
    setConnectionHint("ok", "连接成功，后续重启窗口可自动复用当前设置。");
  } catch (error) {
    setBackendStatus("error", "后端状态: 连接失败");
    setConnectionHint("error", `连接失败: ${error.message}`);
    appendMessage("assistant", `连接设置应用失败: ${error.message}`);
  }
});

clearConnBtnEl.addEventListener("click", async () => {
  localStorage.removeItem(CONNECTION_STORAGE_KEY);
  apiKeyInputEl.value = "";
  showApiKeyEl.checked = false;
  apiKeyInputEl.type = "password";

  try {
    const info = await api.getAppInfo();
    const fallbackUrl = normalizeBackendUrl(info.backendUrl);
    apiUrlInputEl.value = fallbackUrl;
    await api.updateConnection(fallbackUrl, "");
    backendUrlEl.textContent = `后端地址: ${fallbackUrl}`;
    setConnectionHint("ok", "已清空本地保存设置。当前会话将使用默认地址。");
  } catch (error) {
    setConnectionHint("error", `清空后初始化默认地址失败: ${error.message}`);
  }
});

appendMessage("assistant", "桌面端已启动。正在检查后端状态...");
bootstrapBackend();
