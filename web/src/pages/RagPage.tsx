import { Search, ServerCrash } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import { Button } from "../components/Button";
import type { RagQueryResponse } from "../types/api";

export function RagPage() {
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<RagQueryResponse | null>(null);
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  async function runQuery() {
    const text = query.trim();
    if (!text) {
      setError("请输入需要检索的问题。");
      return;
    }
    setError("");
    setIsLoading(true);
    try {
      setResult(await api.queryRag(text));
    } catch (queryError) {
      setError(queryError instanceof Error ? queryError.message : "RAG 查询失败。");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_24rem]">
      <div className="panel p-4">
        <div className="mb-4 flex items-center gap-2">
          <Search className="h-5 w-5 text-console-accent" aria-hidden="true" />
          <div>
            <h1 className="text-base font-semibold">RAG 检索问答</h1>
            <p className="text-xs text-console-subdued">
              面向知识库的只读查询，引用片段会独立展示。
            </p>
          </div>
        </div>

        <div className="flex flex-col gap-3">
          <textarea
            className="field min-h-28 resize-y"
            placeholder="输入需要检索的问题"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <Button loading={isLoading} onClick={runQuery} variant="primary">
            检索并回答
          </Button>
        </div>

        {error ? (
          <div className="mt-4 rounded-md border border-console-danger/50 bg-console-danger/10 p-3 text-sm text-red-100">
            {error}
          </div>
        ) : null}

        <div className="mt-4 rounded-lg border border-console-border bg-console-bg p-4">
          {result ? (
            <>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-console-subdued">
                Answer
              </div>
              <div className="whitespace-pre-wrap text-sm leading-6">
                {result.answer || "未生成有效回答。"}
              </div>
            </>
          ) : (
            <div className="flex min-h-48 items-center justify-center gap-2 text-sm text-console-subdued">
              <ServerCrash className="h-4 w-4" aria-hidden="true" />
              等待查询。
            </div>
          )}
        </div>
      </div>

      <aside className="panel p-4">
        <h2 className="mb-3 text-sm font-semibold">命中参考</h2>
        <div className="space-y-3">
          {result?.references.length ? (
            result.references.map((reference, index) => (
              <article className="rounded-md border border-console-border bg-console-bg p-3" key={index}>
                <div className="mb-2 flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-console-subdued">
                    Reference {index + 1}
                  </span>
                  <span className="status-pill">
                    {String(reference.metadata.source_type || "unknown")}
                  </span>
                </div>
                <p className="line-clamp-6 whitespace-pre-wrap text-xs leading-5 text-console-text">
                  {reference.content || "空片段"}
                </p>
                <pre className="mt-3 max-h-40 overflow-auto rounded bg-black/30 p-2 text-xs text-console-subdued">
                  {JSON.stringify(reference.metadata, null, 2)}
                </pre>
              </article>
            ))
          ) : (
            <p className="text-sm text-console-subdued">暂无参考片段。</p>
          )}
        </div>
      </aside>
    </section>
  );
}
