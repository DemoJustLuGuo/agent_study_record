import {
  CheckCircle2,
  Copy,
  Loader2,
  MessageSquarePlus,
  Pencil,
  Send,
  Trash2,
  Wrench,
  PanelRightClose,
  PanelRightOpen,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { streamChatReply } from "../api/sse";
import { Button } from "../components/Button";
import type { ChatMessage, ChatStreamEvent, ThreadSummary } from "../types/api";

type ToolLog = {
  id: string;
  phase: string;
  tool: string;
  text: string;
  args: string;
  result: string;
  error: string;
};

const PROMPT_EXAMPLES = [
  "请解释 OFDM 中循环前缀的作用，并说明过短会带来什么问题。",
  "给出一次无线链路预算的计算步骤，列出常见输入参数。",
  "分析 TCP 重传增多时应优先检查哪些网络指标。",
  "请基于知识库检索 5G NR 帧结构相关内容。",
];

function emptyAssistantMessage(history: ChatMessage[]) {
  const next = [...history];
  if (next[next.length - 1]?.role !== "assistant") {
    next.push({ role: "assistant", content: "" });
  }
  return next;
}

export function ChatPage() {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [threadId, setThreadId] = useState("");
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [message, setMessage] = useState("");
  const [renameTitle, setRenameTitle] = useState("");
  const [status, setStatus] = useState("准备就绪");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [tools, setTools] = useState<ToolLog[]>([]);
  const [copiedMessageId, setCopiedMessageId] = useState("");
  const [showTools, setShowTools] = useState(true);

  const activeThread = useMemo(
    () => threads.find((thread) => thread.thread_id === threadId),
    [threadId, threads]
  );

  async function loadThreads() {
    setError("");
    setIsLoading(true);
    try {
      const result = await api.listThreads();
      setThreads(result.items);
      setThreadId(result.current_thread_id);
      const state = await api.getThread(result.current_thread_id);
      setHistory(state.history);
      setStatus(state.status);
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "会话加载失败。");
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    loadThreads();
  }, []);

  async function switchThread(nextThreadId: string) {
    setThreadId(nextThreadId);
    setRenameTitle("");
    setTools([]);
    try {
      const state = await api.getThread(nextThreadId);
      setHistory(state.history);
      setStatus(state.status);
    } catch (switchError) {
      setError(switchError instanceof Error ? switchError.message : "会话切换失败。");
    }
  }

  async function createThread() {
    setError("");
    try {
      const result = await api.createThread();
      setThreads(result.threads);
      setThreadId(result.thread_id);
      setHistory(result.history);
      setTools([]);
      setStatus(result.status);
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : "会话创建失败。");
    }
  }

  async function renameThread() {
    if (!threadId || !renameTitle.trim()) {
      return;
    }
    setError("");
    try {
      const result = await api.renameThread(threadId, renameTitle);
      setThreads(result.threads);
      setRenameTitle("");
      setStatus(result.status);
    } catch (renameError) {
      setError(renameError instanceof Error ? renameError.message : "重命名失败。");
    }
  }

  async function closeThread() {
    if (!threadId) {
      return;
    }
    setError("");
    try {
      const result = await api.closeThread(threadId);
      setThreads(result.threads);
      setThreadId(result.thread_id);
      setHistory(result.history);
      setTools([]);
      setStatus(result.status);
    } catch (closeError) {
      setError(closeError instanceof Error ? closeError.message : "关闭会话失败。");
    }
  }

  function applyStreamEvent(event: ChatStreamEvent) {
    if (event.type === "status") {
      if (event.data.phase === "start") {
        setHistory((current) => [
          ...current,
          { role: "user", content: event.data.message || message },
          { role: "assistant", content: "" },
        ]);
      }
      setStatus(event.data.status || event.data.text || "处理中");
      return;
    }

    if (event.type === "token") {
      setHistory((current) => {
        const next = emptyAssistantMessage(current);
        const last = next[next.length - 1];
        next[next.length - 1] = {
          ...last,
          content: `${last.content}${event.data.text}`,
        };
        return next;
      });
      return;
    }

    if (event.type === "tool") {
      setTools((current) => [
        {
          id: `${Date.now()}-${current.length}`,
          phase: event.data.phase || "event",
          tool: event.data.tool || "unknown",
          text: event.data.text || "",
          args: event.data.args_preview || "",
          result: event.data.result_preview || "",
          error: event.data.error_preview || "",
        },
        ...current,
      ]);
      return;
    }

    if (event.type === "done") {
      setHistory((current) => {
        const next = emptyAssistantMessage(current);
        next[next.length - 1] = {
          role: "assistant",
          content: event.data.answer,
        };
        return next;
      });
      setStatus(event.data.status || "回复完成");
      if (event.data.title_changed) {
        loadThreads();
      }
      return;
    }

    if (event.type === "error") {
      setError(event.data.message || "聊天处理失败。");
      if (event.data.answer) {
        setHistory((current) => [
          ...current,
          { role: "assistant", content: event.data.answer || "" },
        ]);
      }
      setStatus(event.data.status || "处理失败");
    }
  }

  async function sendMessage() {
    const text = message.trim();
    if (!threadId || !text || isStreaming) {
      return;
    }
    setMessage("");
    setError("");
    setIsStreaming(true);
    setStatus("正在发送");
    await streamChatReply(threadId, text, {
      onEvent: applyStreamEvent,
      onError: (streamError) => setError(streamError),
    });
    setIsStreaming(false);
  }

  async function copyAssistantMessage(messageId: string, content: string) {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedMessageId(messageId);
      window.setTimeout(() => setCopiedMessageId(""), 1200);
    } catch {
      setError("复制失败，请检查浏览器剪贴板权限。");
    }
  }

  return (
    <section className="grid gap-4 xl:grid-cols-[18rem_minmax(0,1fr)_22rem]">
      <aside className="panel p-3">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold">会话线程</h2>
          <Button
            aria-label="新建会话"
            icon={<MessageSquarePlus className="h-4 w-4" aria-hidden="true" />}
            loading={isLoading}
            onClick={createThread}
            variant="ghost"
          >
            新建
          </Button>
        </div>
        <div className="space-y-2">
          {threads.map((thread) => (
            <button
              className={`min-h-11 w-full rounded-md border px-3 py-2 text-left text-sm transition ${
                thread.thread_id === threadId
                  ? "border-console-accent bg-console-accent/10 text-console-text"
                  : "border-console-border bg-console-bg text-console-subdued hover:bg-console-muted"
              }`}
              key={thread.thread_id}
              onClick={() => switchThread(thread.thread_id)}
              type="button"
            >
              <div className="truncate font-medium">{thread.title}</div>
              <div className="truncate text-xs opacity-70">{thread.thread_id}</div>
            </button>
          ))}
        </div>
      </aside>

      <div className="panel flex min-h-[38rem] flex-col">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-console-border p-4">
          <div>
            <h1 className="text-base font-semibold">
              {activeThread?.title || "智能体对话"}
            </h1>
            <p className="text-xs text-console-subdued">{status}</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <input
              className="field w-48"
              placeholder="新会话名"
              value={renameTitle}
              onChange={(event) => setRenameTitle(event.target.value)}
            />
            <Button
              icon={<Pencil className="h-4 w-4" aria-hidden="true" />}
              onClick={renameThread}
              variant="secondary"
            >
              保存名称
            </Button>
            <Button
              icon={<Trash2 className="h-4 w-4" aria-hidden="true" />}
              onClick={closeThread}
              variant="danger"
            >
              关闭
            </Button>
            <div className="w-px h-6 bg-console-border mx-1" />
            <Button
              icon={showTools ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
              onClick={() => setShowTools(!showTools)}
              variant="ghost"
              title={showTools ? "隐藏工具事件" : "显示工具事件"}
            >
              {showTools ? "收起" : "展开"}
            </Button>
          </div>
        </header>

        {error ? (
          <div className="border-b border-console-danger/40 bg-console-danger/10 px-4 py-3 text-sm text-red-100">
            {error}
          </div>
        ) : null}

        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {history.length ? (
            history.map((item, index) => {
              const messageId = `${item.role}-${index}`;
              return (
              <article
                className={`max-w-[85%] rounded-2xl border px-5 py-4 text-sm leading-relaxed shadow-sm ${
                  item.role === "user"
                    ? "ml-auto border-console-accent/30 bg-console-accent/10"
                    : "border-white/10 bg-white/5 backdrop-blur-md"
                }`}
                key={messageId}
              >
                <div className="mb-1 flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold uppercase tracking-wide text-console-subdued">
                    {item.role}
                  </span>
                  {item.role === "assistant" && item.content ? (
                    <button
                      aria-label="复制助手消息"
                      className="inline-flex min-h-8 items-center gap-1 rounded-md border border-console-border px-2 text-xs text-console-subdued transition hover:bg-console-muted focus:outline-none focus:ring-2 focus:ring-console-accent"
                      onClick={() => copyAssistantMessage(messageId, item.content)}
                      type="button"
                    >
                      <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                      {copiedMessageId === messageId ? "已复制" : "复制"}
                    </button>
                  ) : null}
                </div>
                <div className="whitespace-pre-wrap">{item.content}</div>
              </article>
              );
            })
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-console-subdued">
              选择或创建会话后开始提问。
            </div>
          )}
        </div>

        <footer className="border-t border-console-border p-4">
          <div className="mb-3 flex flex-wrap gap-2">
            {PROMPT_EXAMPLES.map((example) => (
              <button
                className="min-h-10 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-left text-xs text-console-subdued transition-all hover:border-console-accent/50 hover:bg-white/10 hover:text-console-text focus:outline-none focus:ring-2 focus:ring-console-accent active:scale-[0.98]"
                disabled={isStreaming}
                key={example}
                onClick={() => setMessage(example)}
                type="button"
              >
                {example}
              </button>
            ))}
          </div>
          <div className="flex flex-col gap-3 md:flex-row">
            <textarea
              className="field min-h-24 flex-1 resize-y"
              placeholder="输入通信系统问题，例如 OFDM 参数、协议分析、知识库检索等"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
                  sendMessage();
                }
              }}
            />
            <Button
              className="md:self-end"
              icon={
                isStreaming ? (
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                ) : (
                  <Send className="h-4 w-4" aria-hidden="true" />
                )
              }
              loading={isStreaming}
              onClick={sendMessage}
              variant="primary"
            >
              发送
            </Button>
          </div>
        </footer>
      </div>

      {showTools && (
        <aside className="panel p-4 h-full xl:max-h-[calc(100vh-8rem)] overflow-y-auto">
          <div className="mb-3 flex items-center justify-between gap-2 text-sm font-semibold sticky top-0 bg-console-surface/80 backdrop-blur pb-2">
            <div className="flex items-center gap-2">
              <Wrench className="h-4 w-4 text-console-accent" aria-hidden="true" />
              工具事件
            </div>
            <span className="text-xs font-normal text-console-subdued">{tools.length}</span>
          </div>
          <div className="space-y-3">
            {tools.length ? (
              tools.map((tool) => (
                <div className="rounded-md border border-console-border bg-console-bg p-3" key={tool.id}>
                  <div className="mb-2 flex items-center justify-between gap-2">
                    <span className="text-sm font-medium">{tool.tool}</span>
                    <span className="status-pill">{tool.phase}</span>
                  </div>
                  {tool.text ? <p className="text-xs text-console-subdued">{tool.text}</p> : null}
                  {tool.args ? <pre className="mt-2 overflow-auto rounded bg-black/30 p-2 text-xs">{tool.args}</pre> : null}
                  {tool.result ? <pre className="mt-2 overflow-auto rounded bg-black/30 p-2 text-xs">{tool.result}</pre> : null}
                  {tool.error ? <p className="mt-2 text-xs text-red-200">{tool.error}</p> : null}
                </div>
              ))
            ) : (
              <div className="flex items-center gap-2 text-sm text-console-subdued">
                <CheckCircle2 className="h-4 w-4" aria-hidden="true" />
                暂无工具事件。
              </div>
            )}
          </div>
        </aside>
      )}
    </section>
  );
}
