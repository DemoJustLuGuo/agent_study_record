import type {
  KnowledgeActionResponse,
  RagQueryResponse,
  ThreadListResponse,
  ThreadOperationResponse,
  ThreadStateResponse,
  TraceDetailResponse,
  TraceListResponse,
  ApiErrorPayload,
} from "../types/api";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

export const DEFAULT_ADMIN_TOKEN = import.meta.env.VITE_ADMIN_TOKEN || "";

type RequestOptions = RequestInit & {
  adminToken?: string;
};

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  const payload = text ? JSON.parse(text) : {};

  if (!response.ok) {
    const errorPayload = payload as ApiErrorPayload;
    const detail = errorPayload.detail;
    const message =
      detail?.error ||
      detail?.detail ||
      response.statusText ||
      "请求失败，请检查后端服务。";
    throw new Error(message);
  }

  return payload as T;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const headers = new Headers(options.headers);

  if (!headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  if (options.adminToken) {
    headers.set("Authorization", `Bearer ${options.adminToken}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  return parseResponse<T>(response);
}

export const api = {
  health: () => apiRequest<{ ok: boolean }>("/health"),
  version: () => apiRequest<{ version: string }>("/version"),

  listThreads: () => apiRequest<ThreadListResponse>("/api/v1/chat/threads"),
  createThread: () =>
    apiRequest<ThreadOperationResponse>("/api/v1/chat/threads", {
      method: "POST",
    }),
  getThread: (threadId: string) =>
    apiRequest<ThreadStateResponse>(`/api/v1/chat/threads/${threadId}`),
  renameThread: (threadId: string, title: string) =>
    apiRequest<ThreadOperationResponse>(
      `/api/v1/chat/threads/${threadId}/rename`,
      {
        method: "POST",
        body: JSON.stringify({ title }),
      }
    ),
  closeThread: (threadId: string) =>
    apiRequest<ThreadOperationResponse>(`/api/v1/chat/threads/${threadId}`, {
      method: "DELETE",
    }),

  queryRag: (query: string) =>
    apiRequest<RagQueryResponse>("/api/v1/rag/query", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),

  webIngest: (urls: string, operator: string, adminToken: string) =>
    apiRequest<KnowledgeActionResponse>("/api/v1/knowledge/web-ingest", {
      method: "POST",
      body: JSON.stringify({ urls, operator }),
      adminToken,
    }),
  syncKnowledge: (adminToken: string) =>
    apiRequest<KnowledgeActionResponse>("/api/v1/knowledge/sync", {
      method: "POST",
      adminToken,
    }),
  createSnapshot: (tag: string, adminToken: string) =>
    apiRequest<KnowledgeActionResponse>("/api/v1/knowledge/snapshot", {
      method: "POST",
      body: JSON.stringify({ tag }),
      adminToken,
    }),
  rollbackSnapshot: (
    snapshotName: string,
    confirmName: string,
    adminToken: string
  ) =>
    apiRequest<KnowledgeActionResponse>("/api/v1/knowledge/rollback", {
      method: "POST",
      body: JSON.stringify({
        snapshot_name: snapshotName,
        confirm_name: confirmName,
      }),
      adminToken,
    }),

  listTraces: (limit: number, adminToken: string) =>
    apiRequest<TraceListResponse>(`/api/v1/traces?limit=${limit}`, {
      adminToken,
    }),
  getTrace: (traceId: string, adminToken: string) =>
    apiRequest<TraceDetailResponse>(`/api/v1/traces/${traceId}`, {
      adminToken,
    }),
};
