import { expect, test, type Page } from "@playwright/test";

const apiBase = "http://127.0.0.1:8000";
const storageKey = "agent-study-admin-token";

async function mockBaseApi(page: Page) {
  await page.route(`${apiBase}/health`, (route) =>
    route.fulfill({ json: { ok: true } })
  );
  await page.route(`${apiBase}/version`, (route) =>
    route.fulfill({ json: { version: "0.16.2" } })
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
  await page.route(`${apiBase}/api/v1/rag/config`, (route) =>
    route.fulfill({
      json: {
        config: {
          chunk_overlap: 20,
          chunk_size: 200,
          chunking: {
            source_type: {
              web_url: {
                chunk_overlap: 40,
                chunk_size: 300,
              },
            },
          },
          retrieval: {
            candidate_k: 12,
            final_k: 3,
            hybrid_enabled: true,
            keyword_enabled: true,
            keyword_k: 8,
            rerank: {
              enabled: true,
              target_chunk_length: 360,
              weights: {
                coverage: 1.8,
                phrase: 1.0,
                position: 0.6,
              },
            },
            top_k: 3,
            vector_k: 8,
          },
        },
        default_config: {},
        schema_info: {}
      },
    })
  );
  await page.route(`${apiBase}/api/v1/rag/metrics`, (route) =>
    route.fulfill({
      json: {
        recent_events: [],
        strategy_distribution: {},
        summary: {
          empty_reference_queries: 0,
          failed_queries: 0,
          success_queries: 0,
          total_queries: 0,
        },
      },
    })
  );
  await page.route(`${apiBase}/api/v1/knowledge/upload-policy`, (route) =>
    route.fulfill({
      json: {
        allowed_extensions: [".txt"],
        fully_supported_extensions: [".txt"],
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
  await page.getByPlaceholder("输入通信系统问题，例如 OFDM 参数、协议分析、知识库检索等").fill("测试 OFDM");
  await page.getByRole("button", { name: "发送" }).click();

  await expect(page.getByText("测试 OFDM")).toBeVisible();
  await expect(page.getByText("受控最终回答")).toBeVisible();
  await expect(page.getByText("rag_search")).toBeVisible();
  await expect(page.getByText("{\"query\":\"OFDM\"}")).toBeVisible();
  await expect(page.getByText("命中 1 条")).toBeVisible();
  await expect(page.getByText("raw result should stay hidden")).toHaveCount(0);
  await expect(page.getByRole("button", { name: "发送" })).toBeEnabled();
});

test("chat example prompt fills the input", async ({ page }) => {
  await mockBaseApi(page);

  await page.goto("/");
  await page
    .getByRole("button", { name: /循环前缀/ })
    .click();

  await expect(
    page.getByPlaceholder("输入通信系统问题，例如 OFDM 参数、协议分析、知识库检索等")
  ).toHaveValue(/循环前缀/);
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
  await page.getByPlaceholder("输入通信系统问题，例如 OFDM 参数、协议分析、知识库检索等").fill("触发错误");
  await page.getByRole("button", { name: "发送" }).click();

  await expect(page.getByText("受控 SSE 错误")).toBeVisible();
  await expect(page.getByRole("button", { name: "发送" })).toBeEnabled();
});

test("admin pages blocked by Token Gate", async ({ page }) => {
  await mockBaseApi(page);
  await page.goto("/admin");
  await expect(page.getByRole("heading", { name: "管理中心门禁" })).toBeVisible();
});

test("workbench uses localized product navigation", async ({ page }) => {
  await mockBaseApi(page);
  await page.goto("/", {
    waitUntil: "domcontentloaded",
  });

  await expect(page.getByRole("button", { name: "对话" })).toBeVisible();
  await expect(page.getByRole("button", { name: "智能体配置" })).toBeVisible();
  await expect(page.getByRole("button", { name: "知识库集合" })).toBeVisible();
  await expect(page.getByRole("button", { name: "工具与策略" })).toBeVisible();
  await expect(page.getByRole("button", { name: "运行追踪" })).toBeVisible();
  await expect(page.getByRole("button", { name: "系统设置" })).toBeVisible();

  await page.evaluate((key) => localStorage.setItem(key, "admin-token"), storageKey);
  await page.getByRole("button", { name: "智能体配置" }).click();
  await expect(page.getByRole("heading", { name: "智能体配置" })).toBeVisible();
  await page.getByRole("button", { name: "工具与策略" }).click();
  await expect(page.getByRole("heading", { name: "工具与策略" })).toBeVisible();
  await page.getByRole("button", { name: "系统设置" }).click();
  await expect(page.getByRole("heading", { name: "检索增强参数" })).toBeVisible();
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

  await page.goto("/admin/knowledge");
  // Fill the token to pass the gate but let's say the token is empty in the test request somehow?
  // Wait, if it passes the gate, it HAS an admin token. The test expects to fail if the token is not there.
  // Actually, without token we just see the Token Gate.
  await expect(page.getByRole("heading", { name: "管理中心门禁" })).toBeVisible();
  expect(syncRequests).toBe(0);
});

test("knowledge uploads a txt file through the API", async ({ page }) => {
  await mockBaseApi(page);
  let sawAuth = false;
  await page.route(`${apiBase}/api/v1/knowledge/upload`, (route) => {
    sawAuth = route.request().headers().authorization === "Bearer admin-token";
    return route.fulfill({
      json: {
        filename: "sample.txt",
        result: "✅ 已写入知识库。",
        source_type: ".txt",
      },
    });
  });

  await page.goto("/admin/knowledge", {
    waitUntil: "domcontentloaded",
  });
  await page.evaluate((key) => localStorage.setItem(key, "admin-token"), storageKey);
  await page.reload();
  await page.setInputFiles('input[type="file"]', {
    buffer: Buffer.from("通信知识"),
    mimeType: "text/plain",
    name: "sample.txt",
  });
  await page.getByRole("button", { name: "上传文件" }).click();

  await expect(page.getByText("已写入知识库")).toBeVisible();
  expect(sawAuth).toBe(true);
});

test("rag metrics can refresh and reset with admin token", async ({ page }) => {
  await mockBaseApi(page);
  let resetRequests = 0;
  await page.route(`${apiBase}/api/v1/rag/metrics/reset`, (route) => {
    resetRequests += 1;
    expect(route.request().headers().authorization).toBe("Bearer admin-token");
    return route.fulfill({ json: { message: "已重置 RAG 运行指标。" } });
  });

  await page.goto("/admin/rag", {
    waitUntil: "domcontentloaded",
  });
  await page.evaluate((key) => localStorage.setItem(key, "admin-token"), storageKey);
  await page.reload();
  await page.getByRole("button", { name: "刷新" }).click();
  await page.getByRole("button", { name: "重置" }).click();

  await expect(page.getByText("total_queries")).toBeVisible();
  expect(resetRequests).toBe(1);
});

test("rag config saves with admin token", async ({ page }) => {
  await mockBaseApi(page);
  let putRequests = 0;
  await page.route(`${apiBase}/api/v1/rag/config`, (route) => {
    if (route.request().method() === "PUT") {
      putRequests += 1;
      expect(route.request().headers().authorization).toBe("Bearer admin-token");
      return route.fulfill({ json: { updated: true, restart_required: true, warnings: [] } });
    }
    return route.fallback();
  });

  await page.goto("/admin/rag", {
    waitUntil: "domcontentloaded",
  });
  await page.evaluate((key) => localStorage.setItem(key, "admin-token"), storageKey);
  await page.reload();
  await page.getByRole("button", { name: "保存配置" }).click();

  await expect(page.getByText("已持久化")).toBeVisible();
  expect(putRequests).toBe(1);
});

test("admin token can be rotated from the admin shell", async ({ page }) => {
  await mockBaseApi(page);
  let sawAuth = false;
  let sawPayload = false;
  await page.route(`${apiBase}/api/v1/admin/token`, async (route) => {
    sawAuth = route.request().headers().authorization === "Bearer admin-token";
    sawPayload =
      (await route.request().postDataJSON()).new_token === "rotated-token-123";
    return route.fulfill({
      json: {
        message: "管理 Token 已写入 .env，并已对当前后端进程生效。",
        restart_required: false,
        updated: true,
      },
    });
  });

  await page.goto("/admin/rag", {
    waitUntil: "domcontentloaded",
  });
  await page.evaluate((key) => localStorage.setItem(key, "admin-token"), storageKey);
  await page.reload();
  await page.getByPlaceholder("新 APP_ADMIN_TOKEN").fill("rotated-token-123");
  await page.getByPlaceholder("再次输入新 Token").fill("rotated-token-123");
  await page.getByRole("button", { name: "写入 .env" }).click();

  await expect(page.getByText("当前后端进程生效")).toBeVisible();
  await expect
    .poll(() => page.evaluate((key) => localStorage.getItem(key), storageKey))
    .toBe("rotated-token-123");
  expect(sawAuth).toBe(true);
  expect(sawPayload).toBe(true);
});
