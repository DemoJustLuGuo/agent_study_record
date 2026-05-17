import { Filter, RefreshCw, TerminalSquare } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { api } from "../api/client";
import { AdminTokenPanel } from "../components/AdminTokenPanel";
import { Button } from "../components/Button";
import type { TraceDetailResponse, TraceListItem } from "../types/api";

type TracesPageProps = {
  adminToken: string;
  adminTokenSource: string;
  onAdminTokenChange: (value: string) => void;
};

function formatTime(timestamp: number) {
  return new Date(timestamp * 1000).toLocaleString();
}

export function TracesPage({
  adminToken,
  adminTokenSource,
  onAdminTokenChange,
}: TracesPageProps) {
  const [traces, setTraces] = useState<TraceListItem[]>([]);
  const [selectedTraceId, setSelectedTraceId] = useState("");
  const [detail, setDetail] = useState<TraceDetailResponse | null>(null);
  const [eventFilter, setEventFilter] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const filteredEvents = useMemo(() => {
    if (!detail) {
      return [];
    }
    const filter = eventFilter.trim().toLowerCase();
    if (!filter) {
      return detail.events;
    }
    return detail.events.filter((event) =>
      String(event.event || "").toLowerCase().includes(filter)
    );
  }, [detail, eventFilter]);

  const loadTraces = useCallback(async () => {
    if (!adminToken) {
      return;
    }
    setError("");
    setIsLoading(true);
    try {
      const result = await api.listTraces(100, adminToken);
      setTraces(result.items);
      setSelectedTraceId((current) => current || result.items[0]?.trace_id || "");
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "追踪列表加载失败。");
    } finally {
      setIsLoading(false);
    }
  }, [adminToken]);

  const loadTrace = useCallback(async (traceId: string) => {
    if (!adminToken || !traceId) {
      return;
    }
    setSelectedTraceId(traceId);
    setError("");
    setIsLoading(true);
    try {
      setDetail(await api.getTrace(traceId, adminToken));
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : "追踪详情加载失败。");
    } finally {
      setIsLoading(false);
    }
  }, [adminToken]);

  useEffect(() => {
    loadTraces();
  }, [loadTraces]);

  useEffect(() => {
    if (selectedTraceId) {
      loadTrace(selectedTraceId);
    }
  }, [selectedTraceId, loadTrace]);

  return (
    <section className="space-y-4">
      <AdminTokenPanel
        token={adminToken}
        source={adminTokenSource}
        onChange={onAdminTokenChange}
      />

      <div className="panel p-5">
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-console-accent">
          运行追踪
        </p>
        <h1 className="mt-2 text-2xl font-semibold text-console-text">运行追踪</h1>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-console-subdued">
          查看后端写入的脱敏事件流，用于定位模型调用、工具调用、错误和耗时。
        </p>
      </div>

      {error ? (
        <div className="rounded-md border border-console-danger/50 bg-console-danger/10 p-3 text-sm text-red-100">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[22rem_minmax(0,1fr)]">
        <aside className="panel p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <TerminalSquare className="h-4 w-4 text-console-accent" aria-hidden="true" />
              追踪列表
            </div>
            <Button
              icon={<RefreshCw className="h-4 w-4" aria-hidden="true" />}
              loading={isLoading}
              onClick={loadTraces}
              variant="ghost"
            >
              刷新
            </Button>
          </div>
          <div className="space-y-2">
            {traces.map((trace) => (
              <button
                className={`min-h-11 w-full rounded-2xl border px-4 py-3 text-left text-sm transition-all duration-200 ${
                  selectedTraceId === trace.trace_id
                    ? "border-console-accent bg-console-accent/10 shadow-sm"
                    : "border-white/5 bg-transparent hover:bg-white/5 hover:border-white/10"
                }`}
                key={trace.trace_id}
                onClick={() => loadTrace(trace.trace_id)}
                type="button"
              >
                <div className="truncate font-medium">{trace.trace_id}</div>
                <div className="text-xs text-console-subdued">
                  {formatTime(trace.updated_at)} · {trace.size} bytes
                </div>
              </button>
            ))}
            {!traces.length ? (
              <p className="text-sm text-console-subdued">暂无追踪记录。</p>
            ) : null}
          </div>
        </aside>

        <div className="panel p-4">
          <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="text-base font-semibold">
                {detail?.trace_id || "追踪详情"}
              </h1>
              <p className="text-xs text-console-subdued">
                仅展示后端脱敏后的预览字段。
              </p>
            </div>
            <label className="flex items-center gap-2 text-sm text-console-subdued">
              <Filter className="h-4 w-4" aria-hidden="true" />
              <input
                className="field"
                placeholder="事件过滤"
                value={eventFilter}
                onChange={(event) => setEventFilter(event.target.value)}
              />
            </label>
          </div>

          <div className="space-y-3">
            {filteredEvents.map((event, index) => (
              <details className="rounded-2xl border border-white/10 bg-black/20 p-4 shadow-inner group transition-all" key={index}>
                <summary className="cursor-pointer text-sm font-medium">
                  {String(event.event || "事件")} · {String(event.tool || event.model || "-")}
                </summary>
                <pre className="mt-3 max-h-96 overflow-auto rounded bg-black/30 p-3 text-xs">
                  {JSON.stringify(event, null, 2)}
                </pre>
              </details>
            ))}
            {!filteredEvents.length ? (
              <p className="text-sm text-console-subdued">暂无匹配事件。</p>
            ) : null}
          </div>
        </div>
      </div>
    </section>
  );
}
