import { Save, Settings } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api } from "../api/client";
import { AdminTokenPanel } from "../components/AdminTokenPanel";
import { Button } from "../components/Button";

type SettingsPageProps = {
  adminToken: string;
  adminTokenSource: string;
  onAdminTokenChange: (value: string) => void;
};

export function SettingsPage({
  adminToken,
  adminTokenSource,
  onAdminTokenChange,
}: SettingsPageProps) {
  const [baseUrl, setBaseUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [status, setStatus] = useState("");
  const [note, setNote] = useState("");
  const [error, setError] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const loadSettings = useCallback(async () => {
    if (!adminToken) {
      return;
    }
    setError("");
    setIsLoading(true);
    try {
      const result = await api.getConnectionSettings(adminToken);
      setBaseUrl(result.openai_base_url);
      setStatus(result.status);
      setNote(result.note);
      setApiKey("");
    } catch (settingsError) {
      setError(
        settingsError instanceof Error ? settingsError.message : "连接设置加载失败。"
      );
    } finally {
      setIsLoading(false);
    }
  }, [adminToken]);

  useEffect(() => {
    loadSettings();
  }, [loadSettings]);

  async function saveSettings() {
    if (!adminToken) {
      setError("请先配置本地管理 Token。");
      return;
    }
    setError("");
    setIsLoading(true);
    try {
      const result = await api.saveConnectionSettings(baseUrl, apiKey, adminToken);
      setStatus(result.message);
      setNote(result.note);
      setApiKey("");
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "连接设置保存失败。");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section className="space-y-4">
      <AdminTokenPanel
        token={adminToken}
        source={adminTokenSource}
        onChange={onAdminTokenChange}
      />

      <div className="panel p-4">
        <div className="mb-4 flex items-center gap-2">
          <Settings className="h-5 w-5 text-console-accent" aria-hidden="true" />
          <div>
            <h1 className="text-base font-semibold">模型连接设置</h1>
            <p className="text-xs text-console-subdued">
              真实 API Key 保存后不会回显；建议使用环境变量名。
            </p>
          </div>
        </div>

        {error ? (
          <div className="mb-4 rounded-md border border-console-danger/50 bg-console-danger/10 p-3 text-sm text-red-100">
            {error}
          </div>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-2">
          <label className="grid gap-2 text-sm">
            <span className="text-console-subdued">OpenAI Compatible Base URL</span>
            <input
              className="field"
              placeholder="https://api.example.com/v1"
              type="url"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
            />
          </label>
          <label className="grid gap-2 text-sm">
            <span className="text-console-subdued">API Key 或环境变量名</span>
            <input
              className="field"
              placeholder="SILICONFLOW_API_KEY"
              type="password"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
            />
          </label>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button
            icon={<Save className="h-4 w-4" aria-hidden="true" />}
            loading={isLoading}
            onClick={saveSettings}
            variant="primary"
          >
            保存连接设置
          </Button>
          <Button loading={isLoading} onClick={loadSettings}>
            刷新
          </Button>
        </div>

        <div className="mt-4 grid gap-3 text-sm">
          {status ? (
            <div className="rounded-md border border-console-border bg-console-bg p-3">
              {status}
            </div>
          ) : null}
          {note ? (
            <div className="rounded-md border border-console-border bg-console-bg p-3 text-console-subdued">
              {note}
            </div>
          ) : null}
        </div>
      </div>
    </section>
  );
}
