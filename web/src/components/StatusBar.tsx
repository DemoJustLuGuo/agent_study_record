import { Activity, AlertTriangle, Server, Shield } from "lucide-react";
import { useEffect, useState } from "react";
import { api, API_BASE_URL } from "../api/client";

type BackendStatus = {
  ok: boolean;
  version: string;
  message: string;
};

export function StatusBar() {
  const [status, setStatus] = useState<BackendStatus>({
    ok: false,
    version: "-",
    message: "检查后端连接中",
  });

  useEffect(() => {
    let cancelled = false;

    async function checkBackend() {
      try {
        const [health, version] = await Promise.all([api.health(), api.version()]);
        if (!cancelled) {
          setStatus({
            ok: health.ok,
            version: version.version,
            message: health.ok ? "后端在线" : "后端状态异常",
          });
        }
      } catch (error) {
        if (!cancelled) {
          setStatus({
            ok: false,
            version: "-",
            message: error instanceof Error ? error.message : "无法连接后端",
          });
        }
      }
    }

    checkBackend();
    const timer = window.setInterval(checkBackend, 15000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const handleAdminClick = () => {
    window.history.pushState({}, "", "/admin");
    window.dispatchEvent(new PopStateEvent("popstate"));
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-console-border bg-console-surface/80 px-4 py-3 backdrop-blur md:px-6">
      <div className="flex items-center gap-3">
        <Server className="h-5 w-5 text-console-accent" aria-hidden="true" />
        <div>
          <div className="text-sm font-semibold text-console-text">
            通信智能体工作台
          </div>
          <div className="text-xs text-console-subdued">{API_BASE_URL}</div>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={handleAdminClick}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md hover:bg-console-muted transition"
        >
          <Shield className="h-4 w-4" aria-hidden="true" />
          <span>管理中心</span>
        </button>
        <span className="status-pill">
          {status.ok ? (
            <Activity className="h-4 w-4 text-console-accent" aria-hidden="true" />
          ) : (
            <AlertTriangle className="h-4 w-4 text-console-warn" aria-hidden="true" />
          )}
          {status.message}
        </span>
        <span className="status-pill">API v{status.version}</span>
      </div>
    </div>
  );
}
