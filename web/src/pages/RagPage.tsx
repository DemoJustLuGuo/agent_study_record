import { BarChart3, RotateCcw, Settings, Save, AlertCircle } from "lucide-react";
import { useEffect, useState, useCallback } from "react";
import { api } from "../api/client";
import { Button } from "../components/Button";
import type { RagMetricsResponse } from "../types/api";

type RagPageProps = {
  adminToken: string;
  adminTokenSource: string;
  onAdminTokenChange: (value: string) => void;
};

const numericFields = [
  { label: "Top K", path: ["retrieval", "top_k"], integer: true, min: 1 },
  { label: "Final K", path: ["retrieval", "final_k"], integer: true, min: 1 },
  { label: "Vector K", path: ["retrieval", "vector_k"], integer: true, min: 1 },
  { label: "Keyword K", path: ["retrieval", "keyword_k"], integer: true, min: 1 },
  { label: "Candidate K", path: ["retrieval", "candidate_k"], integer: true, min: 1 },
  {
    label: "Target Chunk Length",
    path: ["retrieval", "rerank", "target_chunk_length"],
    integer: true,
    min: 1,
  },
  {
    label: "Weight: Coverage",
    path: ["retrieval", "rerank", "weights", "coverage"],
    integer: false,
    min: 0,
  },
  {
    label: "Weight: Phrase",
    path: ["retrieval", "rerank", "weights", "phrase"],
    integer: false,
    min: 0,
  },
  {
    label: "Weight: Position",
    path: ["retrieval", "rerank", "weights", "position"],
    integer: false,
    min: 0,
  },
  { label: "Default Size", path: ["chunk_size"], integer: true, min: 1 },
  { label: "Default Overlap", path: ["chunk_overlap"], integer: true, min: 0 },
  {
    label: "Web URL Size",
    path: ["chunking", "source_type", "web_url", "chunk_size"],
    integer: true,
    min: 1,
  },
  {
    label: "Web URL Overlap",
    path: ["chunking", "source_type", "web_url", "chunk_overlap"],
    integer: true,
    min: 0,
  },
];

function getConfigValue(config: Record<string, unknown>, path: string[]) {
  let current: unknown = config;
  for (const key of path) {
    if (!current || typeof current !== "object") {
      return undefined;
    }
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}

function validateConfig(config: Record<string, unknown>) {
  for (const field of numericFields) {
    const value = getConfigValue(config, field.path);
    if (typeof value !== "number" || !Number.isFinite(value)) {
      return `${field.label} 必须填写有效数字。`;
    }
    if (field.integer && !Number.isInteger(value)) {
      return `${field.label} 必须是整数。`;
    }
    if (value < field.min) {
      return `${field.label} 不能小于 ${field.min}。`;
    }
  }
  return "";
}

export function RagPage({
  adminToken,
}: RagPageProps) {
  const [metrics, setMetrics] = useState<RagMetricsResponse | null>(null);
  const [config, setConfig] = useState<Record<string, unknown>>({});
  const [error, setError] = useState("");
  const [successMsg, setSuccessMsg] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const loadData = useCallback(async () => {
    setError("");
    setIsLoading(true);
    try {
      const [metricsRes, configRes] = await Promise.all([
        api.getRagMetrics(),
        api.getRagConfig(adminToken)
      ]);
      setMetrics(metricsRes);
      setConfig(configRes.config);
    } catch (err) {
      setError(err instanceof Error ? err.message : "数据加载失败。");
    } finally {
      setIsLoading(false);
    }
  }, [adminToken]);

  useEffect(() => {
    if (adminToken) {
      loadData();
    }
  }, [adminToken, loadData]);

  async function handleSaveConfig() {
    if (!adminToken) return;
    const validationError = validateConfig(config);
    if (validationError) {
      setError(validationError);
      setSuccessMsg("");
      return;
    }
    setIsSaving(true);
    setError("");
    setSuccessMsg("");
    try {
      const res = await api.updateRagConfig(config, adminToken);
      if (!res.updated) {
        setError(res.warnings?.join(" ") || "没有保存任何配置变更。");
        return;
      }
      setSuccessMsg(
        res.restart_required
          ? "已持久化，部分参数需重启或重新初始化检索增强服务生效。"
          : "已持久化，当前后端进程已生效。"
      );
      if (res.warnings?.length) {
        setError("保存成功，但有警告: " + res.warnings.join(", "));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "配置保存失败。");
    } finally {
      setIsSaving(false);
    }
  }

  async function resetMetrics() {
    if (!adminToken) return;
    setIsLoading(true);
    try {
      await api.resetRagMetrics(adminToken);
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "指标重置失败。");
    } finally {
      setIsLoading(false);
    }
  }

  const handleConfigChange = (path: string[], value: unknown) => {
    setConfig(prev => {
      const next = structuredClone(prev);
      let current: Record<string, unknown> = next;
      for (let i = 0; i < path.length - 1; i++) {
        const key = path[i];
        if (!current[key] || typeof current[key] !== "object") {
          current[key] = {};
        } else {
          current[key] = { ...(current[key] as Record<string, unknown>) };
        }
        current = current[key] as Record<string, unknown>;
      }
      current[path[path.length - 1]] = value;
      return next;
    });
  };

  const renderField = (label: string, path: string[], type: "number" | "boolean" | "float") => {
    let current: unknown = config;
    for (const p of path) {
      if (current === undefined || current === null) break;
      current = (current as Record<string, unknown>)[p];
    }
    const value = current ?? "";

    if (type === "boolean") {
      return (
        <div className="flex items-center justify-between py-2 border-b border-console-border">
          <span className="text-sm font-medium">{label}</span>
          <input
            type="checkbox"
            checked={!!value}
            onChange={(e) => handleConfigChange(path, e.target.checked)}
            className="w-4 h-4 accent-console-accent bg-console-bg border-console-border"
          />
        </div>
      );
    }

    return (
      <div className="flex items-center justify-between py-2 border-b border-console-border">
        <span className="text-sm font-medium">{label}</span>
        <input
          type="number"
          step={type === "float" ? "0.1" : "1"}
          min={type === "float" ? "0" : "0"}
          value={value as unknown as string | number}
          onChange={(e) => {
            const rawValue = e.target.value;
            handleConfigChange(
              path,
              rawValue === ""
                ? ""
                : type === "float"
                  ? parseFloat(rawValue)
                  : parseInt(rawValue, 10)
            );
          }}
          className="field w-24 text-right"
        />
      </div>
    );
  };

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section className="panel p-5 space-y-4">
        <div className="flex items-center gap-2 mb-2">
          <Settings className="h-5 w-5 text-console-accent" aria-hidden="true" />
          <h2 className="text-lg font-semibold text-console-text">检索增强参数</h2>
        </div>

        {error && (
          <div className="rounded-md border border-console-danger/50 bg-console-danger/10 p-3 text-sm text-red-100 flex items-start gap-2">
            <AlertCircle className="h-4 w-4 mt-0.5" />
            <div>{error}</div>
          </div>
        )}
        {successMsg && (
          <div className="rounded-2xl border border-console-accent/30 bg-console-accent/10 p-4 text-sm text-console-text flex items-start gap-3 shadow-inner">
            <RotateCcw className="h-4 w-4 mt-0.5" />
            <div>{successMsg}</div>
          </div>
        )}

        <div className="space-y-6">
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-console-subdued mb-2">检索配置</h3>
            <div className="bg-black/20 rounded-2xl border border-white/10 px-4 py-1 shadow-inner">
              {renderField("Top K", ["retrieval", "top_k"], "number")}
              {renderField("Final K", ["retrieval", "final_k"], "number")}
              {renderField("Vector K", ["retrieval", "vector_k"], "number")}
              {renderField("Keyword K", ["retrieval", "keyword_k"], "number")}
              {renderField("Candidate K", ["retrieval", "candidate_k"], "number")}
              {renderField("Hybrid Enabled", ["retrieval", "hybrid_enabled"], "boolean")}
              {renderField("Keyword Enabled", ["retrieval", "keyword_enabled"], "boolean")}
            </div>
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-console-subdued mb-2">重排配置</h3>
            <div className="bg-black/20 rounded-2xl border border-white/10 px-4 py-1 shadow-inner">
              {renderField("Enabled", ["retrieval", "rerank", "enabled"], "boolean")}
              {renderField("Target Chunk Length", ["retrieval", "rerank", "target_chunk_length"], "number")}
              {renderField("Weight: Coverage", ["retrieval", "rerank", "weights", "coverage"], "float")}
              {renderField("Weight: Phrase", ["retrieval", "rerank", "weights", "phrase"], "float")}
              {renderField("Weight: Position", ["retrieval", "rerank", "weights", "position"], "float")}
            </div>
          </div>

          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider text-console-subdued mb-2">分块配置</h3>
            <div className="bg-black/20 rounded-2xl border border-white/10 px-4 py-1 shadow-inner">
              {renderField("Default Size", ["chunk_size"], "number")}
              {renderField("Default Overlap", ["chunk_overlap"], "number")}
              {renderField("Web URL Size", ["chunking", "source_type", "web_url", "chunk_size"], "number")}
              {renderField("Web URL Overlap", ["chunking", "source_type", "web_url", "chunk_overlap"], "number")}
            </div>
          </div>
        </div>

        <div className="flex justify-end mt-4 pt-4 border-t border-console-border">
          <Button
            loading={isSaving}
            onClick={handleSaveConfig}
            variant="primary"
            icon={<Save className="h-4 w-4" />}
          >
            保存配置
          </Button>
        </div>
      </section>

      <section className="panel p-5 space-y-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-5 w-5 text-console-accent" aria-hidden="true" />
            <h2 className="text-lg font-semibold text-console-text">运行指标</h2>
          </div>
          <div className="flex gap-2">
            <Button loading={isLoading} onClick={loadData} variant="secondary">刷新</Button>
            <Button
              icon={<RotateCcw className="h-4 w-4" aria-hidden="true" />}
              loading={isLoading}
              onClick={resetMetrics}
              variant="danger"
            >
              重置
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3 text-xs">
          {Object.entries(metrics?.summary || {}).map(([key, value]) => (
            <div className="rounded-md border border-console-border bg-console-bg p-3" key={key}>
              <div className="text-console-subdued font-medium">{key}</div>
              <div className="mt-1 text-xl font-bold">{value as React.ReactNode}</div>
            </div>
          ))}
        </div>

        <div className="mt-4 text-sm">
          <div className="mb-2 font-semibold text-console-text">策略分布</div>
          <div className="bg-console-bg rounded-md border border-console-border p-3 space-y-2">
            {Object.entries(metrics?.strategy_distribution || {}).length ? (
              Object.entries(metrics?.strategy_distribution || {}).map(([key, value]) => (
                <div className="flex justify-between items-center" key={key}>
                  <span className="text-console-subdued">{key}</span>
                  <span className="font-medium">{value as React.ReactNode}</span>
                </div>
              ))
            ) : (
              <p className="text-console-subdued text-xs">暂无策略数据。</p>
            )}
          </div>
        </div>

        <div className="mt-4 text-sm">
          <div className="mb-2 font-semibold text-console-text">最近请求事件</div>
          <div className="max-h-80 space-y-2 overflow-auto bg-black/20 rounded-2xl border border-white/10 p-4 shadow-inner">
            {metrics?.recent_events.length ? (
              metrics.recent_events.slice().reverse().map((event, index) => (
                <pre className="rounded-xl bg-black/40 p-3 text-xs text-console-subdued border border-white/5" key={index}>
                  {JSON.stringify(event, null, 2)}
                </pre>
              ))
            ) : (
              <p className="text-console-subdued text-xs">暂无运行数据。</p>
            )}
          </div>
        </div>
      </section>
    </div>
  );
}
