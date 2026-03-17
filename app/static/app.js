const chatEl = document.getElementById("chat");
const formEl = document.getElementById("chat-form");
const promptEl = document.getElementById("prompt");
const sendBtn = document.getElementById("send-btn");

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

  try {
    await streamReply(prompt, assistantNode);
  } catch (error) {
    assistantNode.textContent = `请求失败: ${error.message}`;
  } finally {
    sendBtn.disabled = false;
    promptEl.focus();
  }
});
