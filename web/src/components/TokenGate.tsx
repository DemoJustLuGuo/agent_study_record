import { KeyRound, ShieldAlert } from "lucide-react";
import { type ReactNode, useState } from "react";
import { useAdminToken } from "../hooks/useAdminToken";
import { Button } from "./Button";

type TokenGateProps = {
  children: ReactNode;
};

export function TokenGate({ children }: TokenGateProps) {
  const { token, source, setToken } = useAdminToken();
  const [inputToken, setInputToken] = useState(token);

  if (token) {
    return <>{children}</>;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-console-bg p-4 text-console-text">
      <div className="w-full max-w-md space-y-6 rounded-lg border border-console-border bg-console-surface/80 p-6 shadow-xl">
        <div className="flex flex-col items-center gap-4 text-center">
          <div className="rounded-full bg-console-accent/20 p-3">
            <ShieldAlert className="h-8 w-8 text-console-accent" />
          </div>
          <h1 className="text-xl font-semibold">管理中心门禁</h1>
          <p className="text-sm text-console-subdued">
            访问智能体配置、知识库集合、工具策略、运行追踪和系统设置需要管理员身份验证。
          </p>
        </div>

        <div className="space-y-4">
          <div className="space-y-2">
            <label htmlFor="token-input" className="text-sm font-medium">
              管理 Token
            </label>
            <div className="relative">
              <KeyRound className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-console-subdued" />
              <input
                id="token-input"
                className="field w-full pl-9"
                placeholder="输入 APP_ADMIN_TOKEN"
                type="password"
                value={inputToken}
                onChange={(e) => setInputToken(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    setToken(inputToken);
                  }
                }}
              />
            </div>
            <p className="text-xs text-console-subdued">当前来源: {source}</p>
          </div>
          <Button
            className="w-full justify-center"
            onClick={() => setToken(inputToken)}
            disabled={!inputToken}
          >
            进入管理中心
          </Button>
        </div>
      </div>
    </div>
  );
}
