const { contextBridge, ipcRenderer } = require("electron");

function bindEvent(channel, callback) {
  const wrapped = (_event, payload) => {
    callback(payload);
  };

  ipcRenderer.on(channel, wrapped);

  return () => {
    ipcRenderer.removeListener(channel, wrapped);
  };
}

contextBridge.exposeInMainWorld("electronAPI", {
  getAppInfo: () => ipcRenderer.invoke("app:get-info"),
  health: () => ipcRenderer.invoke("backend:health"),
  ensureBackendStarted: (options = {}) =>
    ipcRenderer.invoke("backend:ensure-started", options),
  updateConnection: (backendUrl, apiKey) =>
    ipcRenderer.invoke("backend:update-connection", { backendUrl, apiKey }),

  queryRag: (prompt) => ipcRenderer.invoke("backend:rag-query", prompt),
  startChatStream: (requestId, prompt) =>
    ipcRenderer.send("backend:chat-stream:start", { requestId, prompt }),
  cancelChatStream: (requestId) =>
    ipcRenderer.send("backend:chat-stream:cancel", requestId),

  selectUploadFile: () => ipcRenderer.invoke("dialog:select-upload-file"),
  uploadKnowledge: (filePath, operator) =>
    ipcRenderer.invoke("backend:knowledge-upload", { filePath, operator }),
  syncKnowledge: () => ipcRenderer.invoke("backend:knowledge-sync"),
  snapshotKnowledge: (tag) =>
    ipcRenderer.invoke("backend:knowledge-snapshot", tag),
  rollbackKnowledge: (snapshot) =>
    ipcRenderer.invoke("backend:knowledge-rollback", snapshot),

  onChatChunk: (callback) => bindEvent("backend:chat-stream:chunk", callback),
  onChatDone: (callback) => bindEvent("backend:chat-stream:done", callback),
  onChatError: (callback) => bindEvent("backend:chat-stream:error", callback),
});
