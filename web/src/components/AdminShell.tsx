import {
  Database,
  MessageSquare,
  Search,
  Shield,
  TerminalSquare,
  Settings2,
  LogOut,
  KeyRound,
} from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";
import { api } from "../api/client";
import { StatusBar } from "./StatusBar";
import { useAdminToken } from "../hooks/useAdminToken";
import { Button } from "./Button";

const navItems = [
  { path: "/chat", label: "对话", icon: <MessageSquare className="h-4 w-4" /> },
  { path: "/admin/profiles", label: "智能体配置", icon: <Settings2 className="h-4 w-4" /> },
  { path: "/admin/knowledge", label: "知识库集合", icon: <Database className="h-4 w-4" /> },
  { path: "/admin/tools", label: "工具与策略", icon: <Shield className="h-4 w-4" /> },
  { path: "/admin/traces", label: "运行追踪", icon: <TerminalSquare className="h-4 w-4" /> },
  { path: "/admin/settings", label: "系统设置", icon: <Search className="h-4 w-4" /> },
];

type AdminShellProps = {
  activePath: string;
  children: ReactNode;
  showAdminControls?: boolean;
};

export function AdminShell({
  activePath,
  children,
  showAdminControls = true,
}: AdminShellProps) {
  const { token, setToken } = useAdminToken();
  const [newToken, setNewToken] = useState("");
  const [confirmToken, setConfirmToken] = useState("");
  const [tokenMessage, setTokenMessage] = useState("");
  const [tokenError, setTokenError] = useState("");
  const [isUpdatingToken, setIsUpdatingToken] = useState(false);

  const handleNavigate = (path: string) => {
    window.history.pushState({}, "", path);
    const navEvent = new PopStateEvent("popstate");
    window.dispatchEvent(navEvent);
  };

  const handleExit = () => {
    handleNavigate("/");
  };

  async function handleRotateToken() {
    const nextToken = newToken.trim();
    setTokenMessage("");
    setTokenError("");
    if (nextToken.length < 12) {
      setTokenError("新 Token 至少需要 12 个字符。");
      return;
    }
    if (nextToken !== confirmToken.trim()) {
      setTokenError("两次输入的新 Token 不一致。");
      return;
    }
    setIsUpdatingToken(true);
    try {
      const result = await api.updateAdminToken(nextToken, token);
      if (!result.updated) {
        setTokenError(result.message || "Token 更新失败。");
        return;
      }
      setToken(nextToken);
      setNewToken("");
      setConfirmToken("");
      setTokenMessage(result.message || "管理 Token 已更新。");
    } catch (error) {
      setTokenError(error instanceof Error ? error.message : "Token 更新失败。");
    } finally {
      setIsUpdatingToken(false);
    }
  }

  return (
    <div className="min-h-screen bg-console-bg text-console-text">
      <StatusBar />
      <div className="grid min-h-[calc(100vh-4.5rem)] grid-cols-1 md:grid-cols-[17rem_minmax(0,1fr)]">
        <aside className="border-b border-console-border bg-console-surface/70 p-3 md:border-b-0 md:border-r flex flex-col">
          <div className="mb-4 flex items-center justify-between px-2 text-sm font-semibold text-console-text">
            <div className="flex items-center gap-2">
              <Settings2 className="h-5 w-5 text-console-accent" aria-hidden="true" />
              通信智能体工作台
            </div>
          </div>
          <nav
            className="mb-auto flex gap-2 overflow-x-auto pb-1 md:grid md:grid-cols-1 md:overflow-visible md:pb-0"
            aria-label="工作台导航"
          >
            {navItems.map((item) => (
              <button
                key={item.path}
                className={`nav-button ${
                  activePath === item.path ? "nav-button-active" : ""
                }`}
                onClick={() => handleNavigate(item.path)}
                type="button"
              >
                {item.icon}
                <span className="whitespace-nowrap">{item.label}</span>
              </button>
            ))}
          </nav>
          {showAdminControls ? (
            <div className="mt-4 border-t border-console-border pt-4">
              <div className="mb-4 space-y-2 rounded-xl border border-console-border bg-console-bg/70 p-3">
                <div className="flex items-center gap-2 text-xs font-semibold text-console-text">
                  <KeyRound
                    className="h-4 w-4 text-console-accent"
                    aria-hidden="true"
                  />
                  修改管理 Token
                </div>
                <input
                  className="field w-full"
                  placeholder="新 APP_ADMIN_TOKEN"
                  type="password"
                  value={newToken}
                  onChange={(event) => setNewToken(event.target.value)}
                />
                <input
                  className="field w-full"
                  placeholder="再次输入新 Token"
                  type="password"
                  value={confirmToken}
                  onChange={(event) => setConfirmToken(event.target.value)}
                />
                {tokenError ? (
                  <p className="text-xs text-red-200">{tokenError}</p>
                ) : null}
                {tokenMessage ? (
                  <p className="text-xs text-console-subdued">{tokenMessage}</p>
                ) : null}
                <Button
                  className="w-full justify-center"
                  loading={isUpdatingToken}
                  onClick={handleRotateToken}
                  variant="secondary"
                >
                  写入 .env
                </Button>
              </div>
              <button
                onClick={handleExit}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-console-subdued hover:bg-console-muted rounded-md transition"
              >
                <LogOut className="h-4 w-4" />
                返回用户对话
              </button>
              <button
                onClick={() => setToken("")}
                className="w-full flex items-center gap-2 px-3 py-2 text-sm text-console-subdued hover:text-red-400 hover:bg-red-400/10 rounded-md transition mt-1"
              >
                退出登录 (清除 Token)
              </button>
            </div>
          ) : null}
        </aside>
        <main className="min-w-0 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
