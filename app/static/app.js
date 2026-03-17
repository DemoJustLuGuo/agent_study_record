const chatEl = document.getElementById("chat");
const formEl = document.getElementById("chat-form");
const promptEl = document.getElementById("prompt");
const sendBtn = document.getElementById("send-btn");
const ragModeEl = document.getElementById("rag-mode");
const uploadFormEl = document.getElementById("upload-form");
const uploadFileEl = document.getElementById("upload-file");
const uploadBtn = document.getElementById("upload-btn");
const uploadResultEl = document.getElementById("upload-result");

function appendMessage(role, text) {
  const node = document.createElement("div");
  node.className = `msg ${role}`;
  node.textContent = text;
  chatEl.appendChild(node);
  chatEl.scrollTop = chatEl.scrollHeight;
  return node;
}

async function streamReply(prompt, targetNode) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ prompt }),
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || "请求失败");
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    buffer += decoder.decode(value, { stream: true });
    targetNode.textContent = buffer;
    chatEl.scrollTop = chatEl.scrollHeight;
  }

  buffer += decoder.decode();
  targetNode.textContent = buffer;
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

async function queryOnlineRag(prompt) {
  const response = await fetch("/api/rag/query", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ prompt }),
  });

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.error || "在线RAG请求失败");
  }

  return payload;
}

function setUploadResult(message, state) {
  uploadResultEl.textContent = message;
  uploadResultEl.classList.remove("error", "success");
  if (state) {
    uploadResultEl.classList.add(state);
  }
}

async function uploadKnowledgeFile(file) {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/knowledge/upload", {
    method: "POST",
    body: formData,
  });

  const payload = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(payload.error || "上传失败");
  }

  return payload.result || "上传成功";
}

formEl.addEventListener("submit", async (event) => {
  event.preventDefault();
  const prompt = promptEl.value.trim();
  if (!prompt) {
    return;
  }

  appendMessage("user", prompt);
  promptEl.value = "";
  sendBtn.disabled = true;

  const assistantNode = appendMessage("assistant", "正在思考...");
  const useOnlineRag = ragModeEl.checked;

  try {
    if (useOnlineRag) {
      assistantNode.textContent = "正在检索知识库并生成答案...";
      const result = await queryOnlineRag(prompt);
      const answer = (result.answer || "").trim() || "未生成有效回答";
      assistantNode.textContent = `${answer}${formatReferences(result.references)}`;
    } else {
      await streamReply(prompt, assistantNode);
    }
  } catch (error) {
    assistantNode.textContent = `请求失败: ${error.message}`;
  } finally {
    sendBtn.disabled = false;
    promptEl.focus();
  }
});

uploadFormEl.addEventListener("submit", async (event) => {
  event.preventDefault();

  const file = uploadFileEl.files[0];
  if (!file) {
    setUploadResult("请先选择要上传的txt文件", "error");
    return;
  }

  if (!file.name.toLowerCase().endsWith(".txt")) {
    setUploadResult("仅支持上传txt文件", "error");
    return;
  }

  uploadBtn.disabled = true;
  setUploadResult("正在上传并写入知识库，请稍候...", "");

  try {
    const result = await uploadKnowledgeFile(file);
    setUploadResult(result, "success");
    uploadFormEl.reset();
  } catch (error) {
    setUploadResult(`上传失败: ${error.message}`, "error");
  } finally {
    uploadBtn.disabled = false;
  }
});
