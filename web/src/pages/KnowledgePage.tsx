import { Archive, Database, RotateCcw, ShieldAlert, UploadCloud } from "lucide-react";
import { useState } from "react";
import { api } from "../api/client";
import { AdminTokenPanel } from "../components/AdminTokenPanel";
import { Button } from "../components/Button";
import type { KnowledgeActionResponse } from "../types/api";

type KnowledgePageProps = {
  adminToken: string;
  adminTokenSource: string;
  onAdminTokenChange: (value: string) => void;
};

function ResultPanel({ result }: { result: KnowledgeActionResponse | null }) {
  if (!result) {
    return <p className="text-sm text-console-subdued">等待执行管理操作。</p>;
  }

  return (
    <div className="space-y-3 text-sm">
      <pre className="max-h-72 overflow-auto rounded-md bg-black/30 p-3 text-xs">
        {JSON.stringify(result, null, 2)}
      </pre>
      {result.details?.length ? (
        <div className="space-y-2">
          {result.details.map((detail, index) => (
            <div className="rounded-md border border-console-border bg-console-bg p-3" key={index}>
              <div className="flex items-center justify-between gap-2">
                <span className="truncate">{detail.url || "-"}</span>
                <span className="status-pill">{detail.status || "unknown"}</span>
              </div>
              {detail.reason ? (
                <p className="mt-2 text-xs text-console-subdued">{detail.reason}</p>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function KnowledgePage({
  adminToken,
  adminTokenSource,
  onAdminTokenChange,
}: KnowledgePageProps) {
  const [urls, setUrls] = useState("");
  const [operator, setOperator] = useState("web-console");
  const [snapshotTag, setSnapshotTag] = useState("");
  const [snapshotName, setSnapshotName] = useState("");
  const [confirmName, setConfirmName] = useState("");
  const [result, setResult] = useState<KnowledgeActionResponse | null>(null);
  const [error, setError] = useState("");
  const [loadingAction, setLoadingAction] = useState("");

  async function runAction(
    actionName: string,
    action: () => Promise<KnowledgeActionResponse>
  ) {
    if (!adminToken) {
      setError("请先配置本地管理 Token。");
      return;
    }
    setError("");
    setLoadingAction(actionName);
    try {
      setResult(await action());
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : "操作失败。");
    } finally {
      setLoadingAction("");
    }
  }

  return (
    <section className="space-y-4">
      <AdminTokenPanel
        token={adminToken}
        source={adminTokenSource}
        onChange={onAdminTokenChange}
      />

      {error ? (
        <div className="rounded-md border border-console-danger/50 bg-console-danger/10 p-3 text-sm text-red-100">
          {error}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_26rem]">
        <div className="space-y-4">
          <section className="panel p-4">
            <div className="mb-3 flex items-center gap-2">
              <UploadCloud className="h-5 w-5 text-console-accent" aria-hidden="true" />
              <h1 className="text-base font-semibold">网页入库</h1>
            </div>
            <div className="grid gap-3">
              <textarea
                className="field min-h-36 resize-y"
                placeholder="每行一个 HTTP/HTTPS URL"
                value={urls}
                onChange={(event) => setUrls(event.target.value)}
              />
              <input
                className="field"
                placeholder="operator"
                value={operator}
                onChange={(event) => setOperator(event.target.value)}
              />
              <Button
                loading={loadingAction === "web"}
                onClick={() =>
                  runAction("web", () => api.webIngest(urls, operator, adminToken))
                }
                variant="primary"
              >
                抓取并入库
              </Button>
            </div>
          </section>

          <section className="grid gap-4 lg:grid-cols-2">
            <div className="panel p-4">
              <div className="mb-3 flex items-center gap-2">
                <Database className="h-5 w-5 text-console-accent" aria-hidden="true" />
                <h2 className="text-sm font-semibold">同步失效源</h2>
              </div>
              <p className="mb-4 text-xs leading-5 text-console-subdued">
                清理已删除源文件对应的向量索引，不会删除真实知识源文件。
              </p>
              <Button
                loading={loadingAction === "sync"}
                onClick={() =>
                  runAction("sync", () => api.syncKnowledge(adminToken))
                }
              >
                执行同步
              </Button>
            </div>

            <div className="panel p-4">
              <div className="mb-3 flex items-center gap-2">
                <Archive className="h-5 w-5 text-console-accent" aria-hidden="true" />
                <h2 className="text-sm font-semibold">创建快照</h2>
              </div>
              <input
                className="field mb-3 w-full"
                placeholder="快照标签，可选"
                value={snapshotTag}
                onChange={(event) => setSnapshotTag(event.target.value)}
              />
              <Button
                loading={loadingAction === "snapshot"}
                onClick={() =>
                  runAction("snapshot", () =>
                    api.createSnapshot(snapshotTag, adminToken)
                  )
                }
              >
                创建快照
              </Button>
            </div>
          </section>

          <section className="panel border-console-danger/60 p-4">
            <div className="mb-3 flex items-center gap-2">
              <ShieldAlert className="h-5 w-5 text-console-danger" aria-hidden="true" />
              <h2 className="text-sm font-semibold text-red-100">回滚快照</h2>
            </div>
            <p className="mb-4 text-xs leading-5 text-console-subdued">
              回滚会替换当前向量库状态。必须两次输入同一个快照名称。
            </p>
            <div className="grid gap-3 md:grid-cols-2">
              <input
                className="field"
                placeholder="snapshot_name"
                value={snapshotName}
                onChange={(event) => setSnapshotName(event.target.value)}
              />
              <input
                className="field"
                placeholder="confirm_name"
                value={confirmName}
                onChange={(event) => setConfirmName(event.target.value)}
              />
            </div>
            <Button
              className="mt-3"
              icon={<RotateCcw className="h-4 w-4" aria-hidden="true" />}
              loading={loadingAction === "rollback"}
              onClick={() =>
                runAction("rollback", () =>
                  api.rollbackSnapshot(snapshotName, confirmName, adminToken)
                )
              }
              variant="danger"
            >
              确认回滚
            </Button>
          </section>
        </div>

        <aside className="panel p-4">
          <h2 className="mb-3 text-sm font-semibold">操作结果</h2>
          <ResultPanel result={result} />
        </aside>
      </div>
    </section>
  );
}
