import { KeyRound } from "lucide-react";
import { Button } from "./Button";

type AdminTokenPanelProps = {
  token: string;
  source: string;
  onChange: (value: string) => void;
};

export function AdminTokenPanel({ token, source, onChange }: AdminTokenPanelProps) {
  return (
    <div className="panel flex flex-col gap-3 p-4 md:flex-row md:items-end md:justify-between">
      <div className="space-y-1">
        <div className="flex items-center gap-2 text-sm font-semibold text-console-text">
          <KeyRound className="h-4 w-4 text-console-accent" aria-hidden="true" />
          本地管理 Token
        </div>
        <p className="max-w-3xl text-xs leading-5 text-console-subdued">
          管理接口由后端 APP_ADMIN_TOKEN 鉴权。前端只保存你输入的本机 token，
          不读取后端 .env，也不会把真实 token 打包进浏览器代码。
        </p>
      </div>
      <div className="flex w-full flex-col gap-2 md:w-[28rem] md:flex-row">
        <input
          className="field flex-1"
          placeholder="输入 APP_ADMIN_TOKEN"
          type="password"
          value={token}
          onChange={(event) => onChange(event.target.value)}
        />
        <Button variant="ghost" onClick={() => onChange("")}>
          清除
        </Button>
      </div>
      <span className="status-pill self-start md:self-center">来源：{source}</span>
    </div>
  );
}
