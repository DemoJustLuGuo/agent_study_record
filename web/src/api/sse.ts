import { API_BASE_URL } from "./client";
import type { ChatStreamEvent } from "../types/api";

type StreamHandlers = {
  onEvent: (event: ChatStreamEvent) => void;
  onError: (message: string) => void;
};

function parseEventBlock(block: string): ChatStreamEvent | null {
  const lines = block.split("\n");
  let eventType = "message";
  const dataLines: string[] = [];

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (line.startsWith("event:")) {
      eventType = line.slice("event:".length).trim();
      continue;
    }
    if (line.startsWith("data:")) {
      dataLines.push(line.slice("data:".length).trimStart());
    }
  }

  if (!dataLines.length) {
    return null;
  }

  try {
    return {
      type: eventType as ChatStreamEvent["type"],
      data: JSON.parse(dataLines.join("\n")),
    } as ChatStreamEvent;
  } catch {
    return null;
  }
}

function emitBlocks(buffer: string, onEvent: (event: ChatStreamEvent) => void) {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const blocks = normalized.split("\n\n");
  const remainder = blocks.pop() || "";

  for (const block of blocks) {
    const event = parseEventBlock(block);
    if (event) {
      onEvent(event);
    }
  }

  return remainder;
}

export async function streamChatReply(
  threadId: string,
  message: string,
  handlers: StreamHandlers
) {
  const response = await fetch(`${API_BASE_URL}/api/v1/chat/${threadId}/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok || !response.body) {
    handlers.onError(response.statusText || "聊天流启动失败。");
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      buffer += decoder.decode(value, { stream: true });
      buffer = emitBlocks(buffer, handlers.onEvent);
    }

    buffer += decoder.decode();
    const event = parseEventBlock(buffer);
    if (event) {
      handlers.onEvent(event);
    }
  } catch (error) {
    handlers.onError(error instanceof Error ? error.message : "聊天流读取失败。");
  }
}
