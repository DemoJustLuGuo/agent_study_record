import { expect, test, type Page } from "@playwright/test";

const apiBase = "http://127.0.0.1:8000";
const storageKey = "agent-study-admin-token";

async function mockBaseApi(page: Page) {
  await page.route(`${apiBase}/health`, (route) =>
    route.fulfill({ json: { ok: true } })
  );
  await page.route(`${apiBase}/version`, (route) =>
    route.fulfill({ json: { version: "0.15.0" } })
  );
  await page.route(`${apiBase}/api/v1/chat/threads`, (route) => {
    if (route.request().method() === "GET") {
      return route.fulfill({
        json: {
          current_thread_id: "thread_e2e",
          items: [
            {
              auto_named: false,
              renamed: false,
              thread_id: "thread_e2e",
              title: "E2E 会话",
              updated_at: "2026-05-15T00:00:00Z",
            },
          ],
        },
      });
    }
    return route.fulfill({ status: 405, json: { detail: "unsupported" } });
  });
  await page.route(`${apiBase}/api/v1/chat/threads/thread_e2e`, (route) =>
    route.fulfill({
      json: {
        history: [],
        status: "准备就绪",
        thread_id: "thread_e2e",
      },
    })
  );
  await page.route(`${apiBase}/api/v1/rag/query`, (route) =>
    route.fulfill({
      json: {
        answer: "",
        metrics: {},
        query: "",
        references: [],
        rerank_debug: [],
        retrieval_debug: {},
      },
    })
  );
  await page.route(`${apiBase}/api/v1/traces?limit=100`, (route) =>
    route.fulfill({ json: { items: [] } })
  );
}

function sseBody(events: Array<{ event: string; data: Record<string, unknown> }>) {
  return events
    .map((item) => `event: ${item.event}\ndata: ${JSON.stringify(item.data)}\n\n`)
    .join("");
}

test("chat renders controlled SSE events without exposing raw tool data", async ({
  page,
}) => {
  await mockBaseApi(page);
  await page.route(`${apiBase}/api/v1/chat/thread_e2e/stream`, (route) =>
    route.fulfill({
      body: sseBody([
        {
          event: "status",
          data: {
            message: "测试 OFDM",
            phase: "start",
            status: "思考中",
            thread_id: "thread_e2e",
          },
        },
        {
          event: "token",
          data: { text: "增量片段", thread_id: "thread_e2e" },
        },
        {
          event: "tool",
          data: {
            args: { query: "raw secret query" },
            args_preview: "{\"query\":\"OFDM\"}",
            phase: "end",
            result: "raw result should stay hidden",
            result_preview: "命中 1 条",
            text: "检索完成",
            thread_id: "thread_e2e",
            tool: "rag_search",
          },
        },
        {
          event: "done",
          data: {
            answer: "受控最终回答",
            status: "回复完成",
            thread_id: "thread_e2e",
          },
        },
      ]),
      contentType: "text/event-stream",
    })
  );

  await page.goto("/");
  await expect(page.getByRole("button", { name: "Settings" })).toHaveCount(0);
  await page.getByPlaceholder("输入通信系统问题，例如 OFDM 参数、协议分析、RAG 检索等").fill("测试 OFDM");
  await page.getByRole("button", { name: "发送" }).click();

  await expect(page.getByText("测试 OFDM")).toBeVisible();
  await expect(page.getByText("受控最终回答")).toBeVisible();
  await expect(page.getByText("rag_search")).toBeVisible();
  await expect(page.getByText("{\"query\":\"OFDM\"}")).toBeVisible();
  await expect(page.getByText("命中 1 条")).toBeVisible();
  await expect(page.getByText("raw result should stay hidden")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "发送" })).toBeEnabled();
});

test("chat renders controlled SSE errors and stops loading", async ({ page }) => {
  await mockBaseApi(page);
  await page.route(`${apiBase}/api/v1/chat/thread_e2e/stream`, (route) =>
    route.fulfill({
      body: sseBody([
        {
          event: "status",
          data: {
            message: "触发错误",
            phase: "start",
            status: "思考中",
            thread_id: "thread_e2e",
          },
        },
        {
          event: "error",
          data: {
            message: "受控 SSE 错误",
            status: "处理失败",
            thread_id: "thread_e2e",
          },
        },
      ]),
      contentType: "text/event-stream",
    })
  );

  await page.goto("/");
  await page.getByPlaceholder("输入通信系统问题，例如 OFDM 参数、协议分析、RAG 检索等").fill("触发错误");
  await page.getByRole("button", { name: "发送" }).click();

  await expect(page.getByText("受控 SSE 错误")).toBeVisible();
  await expect(page.getByRole("button", { name: "发送" })).toBeEnabled();
});

test("knowledge blocks management requests without an admin token", async ({
  page,
}) => {
  await mockBaseApi(page);
  let syncRequests = 0;
  await page.route(`${apiBase}/api/v1/knowledge/sync`, (route) => {
    syncRequests += 1;
    return route.fulfill({ json: { result: "should not happen" } });
  });

  await page.goto("/");
  await page.getByRole("button", { name: "Knowledge" }).click();
  await page.getByRole("button", { name: "执行同步" }).click();

  await expect(page.getByText("请先配置本地管理 Token。")).toBeVisible();
  expect(syncRequests).toBe(0);
});

test("knowledge requires rollback confirmation before sending requests", async ({
  page,
}) => {
  await mockBaseApi(page);
  let rollbackRequests = 0;
  await page.route(`${apiBase}/api/v1/knowledge/rollback`, (route) => {
    rollbackRequests += 1;
    return route.fulfill({ json: { result: "should not happen" } });
  });

  await page.goto("/", {
    waitUntil: "domcontentloaded",
  });
  await page.evaluate((key) => localStorage.setItem(key, "admin-token"), storageKey);
  await page.reload();
  await page.getByRole("button", { name: "Knowledge" }).click();
  await page.getByPlaceholder("snapshot_name").fill("snapshot-a");
  await page.getByPlaceholder("confirm_name").fill("snapshot-b");

  await expect(page.getByRole("button", { name: "确认回滚" })).toBeDisabled();
  expect(rollbackRequests).toBe(0);
});
