export type ChatMessage = {
  role: "user" | "assistant" | string;
  content: string;
};

export type ThreadSummary = {
  thread_id: string;
  title: string;
  renamed: boolean;
  auto_named: boolean;
  updated_at: string;
};

export type ThreadListResponse = {
  items: ThreadSummary[];
  current_thread_id: string;
};

export type ThreadStateResponse = {
  thread_id: string;
  history: ChatMessage[];
  status: string;
};

export type ThreadOperationResponse = {
  thread_id: string;
  threads: ThreadSummary[];
  history: ChatMessage[];
  status: string;
  ok?: boolean | null;
};

export type ChatStreamEvent =
  | {
      type: "status";
      data: {
        thread_id: string;
        phase?: string;
        message?: string;
        status?: string;
        text?: string;
      };
    }
  | {
      type: "token";
      data: {
        thread_id: string;
        text: string;
      };
    }
  | {
      type: "tool";
      data: {
        thread_id: string;
        phase?: string;
        tool?: string;
        text?: string;
        args_preview?: string;
        result_preview?: string;
        error_preview?: string;
        elapsed_ms?: number | null;
      };
    }
  | {
      type: "done";
      data: {
        thread_id: string;
        answer: string;
        status?: string;
        trace_id?: string;
        title_changed?: boolean;
      };
    }
  | {
      type: "error";
      data: {
        thread_id: string;
        message?: string;
        answer?: string;
        status?: string;
      };
    }
  | {
      type: "references";
      data: Record<string, unknown>;
    };

export type RagReference = {
  content: string;
  metadata: Record<string, unknown>;
};

export type RagQueryResponse = {
  query: string;
  answer: string;
  references: RagReference[];
  retrieval_debug: Record<string, unknown>;
  rerank_debug: Record<string, unknown>[];
  metrics: Record<string, unknown>;
};

export type RagMetricsResponse = {
  summary: Record<string, number>;
  strategy_distribution: Record<string, number>;
  recent_events: Record<string, unknown>[];
};

export type RagMetricsResetResponse = {
  message: string;
};

export type KnowledgeActionDetail = {
  url?: string;
  status?: string;
  reason?: string;
  cleaning?: Record<string, unknown>;
};

export type KnowledgeActionResponse = {
  result?: string | null;
  snapshot?: string | null;
  error?: string | null;
  filename?: string | null;
  source_type?: string | null;
  total?: number | null;
  added?: number | null;
  updated?: number | null;
  skipped?: number | null;
  failed?: number | null;
  details?: KnowledgeActionDetail[];
  removed_source_count?: number | null;
  removed_sources?: string[];
};

export type KnowledgeUploadPolicyResponse = {
  allowed_extensions: string[];
  fully_supported_extensions: string[];
};

export type TraceListItem = {
  trace_id: string;
  updated_at: number;
  size: number;
};

export type TraceListResponse = {
  items: TraceListItem[];
};

export type TraceDetailResponse = {
  trace_id: string;
  events: Record<string, unknown>[];
};

export type ApiErrorPayload = {
  detail?: {
    error?: string;
    detail?: string;
    code?: string;
  };
};
