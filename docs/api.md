# 后端 API 契约说明

本文档记录当前 FastAPI 后端响应契约。`api.main` 是正式后端控制面，React 控制台通过该 API 完成 Chat、RAG、Knowledge 和 Trace 工作流：

```powershell
venv\Scripts\python.exe -m api.main
```

`api.main` 默认监听 `127.0.0.1:8000`。React 控制台默认通过 `VITE_API_BASE_URL=http://127.0.0.1:8000` 访问后端：

```powershell
cd web
npm run dev
```

对外集成、管理操作和前端对接均使用 FastAPI。管理类接口需要在运行环境设置 `APP_ADMIN_TOKEN`，请求时使用：

```text
Authorization: Bearer <APP_ADMIN_TOKEN>
```

真实 API Key 不通过后端 API 返回，也不提供 settings API 写入入口。后端启动时会只读加载项目根目录 `.env`，但不会覆盖已存在的系统环境变量。React 前端不读取 `APP_ADMIN_TOKEN`，只保存用户输入的本地 token。管理页可通过受保护接口轮换 `APP_ADMIN_TOKEN`，后端会写回 `.env` 并更新当前进程环境变量；手工修改 `.env` 后仍需要重启后端。

## 公共响应

### GET `/health`

```json
{
  "ok": true
}
```

### GET `/version`

```json
{
  "version": "0.16.2"
}
```

### 错误响应

FastAPI `HTTPException.detail` 使用统一对象：

```json
{
  "error": "错误摘要",
  "detail": "可选详细信息",
  "code": "bad_request"
}
```

常用 `code`：

- `bad_request`
- `unauthorized`
- `forbidden`
- `not_found`

## Admin API

以下接口均需要当前 Admin Token。

### GET `/api/v1/admin/session`

验证当前管理凭证是否有效。

```json
{
  "ok": true,
  "role": "admin"
}
```

### PUT `/api/v1/admin/token`

使用当前有效 token 轮换新的 `APP_ADMIN_TOKEN`。后端会写入项目根目录 `.env`，并同步更新当前进程环境变量；响应不会返回新 token。

请求体：

```json
{
  "new_token": "new-local-admin-token"
}
```

响应：

```json
{
  "updated": true,
  "restart_required": false,
  "message": "管理 Token 已写入 .env，并已对当前后端进程生效。"
}
```

## Chat API

### GET `/api/v1/chat/threads`

返回会话列表与当前默认会话。

```json
{
  "items": [
    {
      "thread_id": "thread_1",
      "title": "会话 1",
      "renamed": false,
      "auto_named": false,
      "updated_at": "2026-05-15T00:00:00Z"
    }
  ],
  "current_thread_id": "thread_1"
}
```

### POST `/api/v1/chat/threads`

创建新会话。响应包含 `thread_id`、`threads`、`history`、`status`，不再返回旧 UI 选择器兼容字段。

```json
{
  "thread_id": "thread_2",
  "threads": [],
  "history": [],
  "status": "当前会话：..."
}
```

### GET `/api/v1/chat/threads/{thread_id}`

返回指定会话历史。

```json
{
  "thread_id": "thread_1",
  "history": [
    {
      "role": "user",
      "content": "OFDM 是什么"
    },
    {
      "role": "assistant",
      "content": "..."
    }
  ],
  "status": "当前会话：..."
}
```

### POST `/api/v1/chat/threads/{thread_id}/rename`

请求体：

```json
{
  "title": "新标题"
}
```

返回会话操作响应。标题为空或超长时返回统一错误响应。

### DELETE `/api/v1/chat/threads/{thread_id}`

关闭会话并删除对应会话 DB。后端会先关闭缓存的 `ReactAgent`，再删除线程数据库文件。

### POST `/api/v1/chat/{thread_id}/stream`

使用 SSE 返回结构化事件。

请求体：

```json
{
  "message": "解释 OFDM 的基本原理"
}
```

事件类型：

```text
event: status
event: token
event: tool
event: references
event: done
event: error
```

`status`：

```json
{
  "thread_id": "thread_1",
  "phase": "start",
  "message": "解释 OFDM 的基本原理",
  "status": "当前会话：... · 思考中..."
}
```

`token`：

```json
{
  "thread_id": "thread_1",
  "text": "增量文本"
}
```

`tool`：

```json
{
  "thread_id": "thread_1",
  "phase": "start",
  "tool": "rag_summarize",
  "text": "[THINK] 正在调用工具：rag_summarize。\n",
  "args_preview": "...",
  "elapsed_ms": null,
  "result_preview": "",
  "error_preview": ""
}
```

`tool` 事件只允许返回 preview 字段，不返回完整 `args`、完整 `code` 或完整工具结果。

`done`：

```json
{
  "thread_id": "thread_1",
  "answer": "最终回答",
  "status": "当前会话：... · 回复完成",
  "trace_id": "abc12345",
  "elapsed_ms": 1200.0,
  "chunk_count": 20,
  "char_count": 600
}
```

`error`：

```json
{
  "thread_id": "thread_1",
  "message": "错误摘要",
  "answer": "可展示给用户的错误文本",
  "status": "当前会话：... · 处理失败"
}
```

## RAG API

### POST `/api/v1/rag/query`

请求体：

```json
{
  "query": "OFDM 是什么"
}
```

响应：

```json
{
  "query": "OFDM 是什么",
  "answer": "...",
  "references": [
    {
      "content": "...",
      "metadata": {
        "source": "通信原理知识100问.txt",
        "source_type": "file"
      }
    }
  ],
  "retrieval_debug": {},
  "rerank_debug": [],
  "metrics": {}
}
```

### GET `/api/v1/rag/metrics`

返回当前进程内 RAG 运行指标窗口，供控制台刷新展示。

```json
{
  "summary": {
    "total_queries": 1,
    "success_queries": 1,
    "failed_queries": 0,
    "empty_reference_queries": 0
  },
  "strategy_distribution": {
    "vector": 1
  },
  "recent_events": [
    {
      "ts": "2026-05-15 12:00:00",
      "ok": true,
      "strategy": "vector",
      "reference_count": 2
    }
  ]
}
```

### POST `/api/v1/rag/metrics/reset`

需要 Admin Token。清空当前进程内 RAG 指标窗口。

```json
{
  "message": "已重置 RAG 运行指标。"
}
```

### GET `/api/v1/rag/config`

需要 Admin Token。返回允许在线管理的 RAG 配置子集，不返回未纳入白名单的配置项。

```json
{
  "config": {
    "retrieval": {
      "top_k": 3,
      "final_k": 3
    },
    "chunk_size": 200,
    "chunk_overlap": 20
  },
  "default_config": {},
  "schema_info": {}
}
```

### PUT `/api/v1/rag/config`

需要 Admin Token。仅允许更新白名单内的检索、重排和分块参数；非法类型、越界数值或未知字段会通过 `warnings` 返回，不会静默写入。

请求体：

```json
{
  "config": {
    "retrieval": {
      "top_k": 5
    }
  }
}
```

响应：

```json
{
  "updated": true,
  "restart_required": true,
  "warnings": []
}
```

## Knowledge API

以下接口均需要 Admin Token。

### GET `/api/v1/knowledge/upload-policy`

返回当前上传入口可接受的扩展名，以及第一版已完整接入的扩展名。

```json
{
  "allowed_extensions": [".txt"],
  "fully_supported_extensions": [".txt"]
}
```

### POST `/api/v1/knowledge/upload`

使用 `multipart/form-data` 上传知识文件。

字段：

- `file`：待上传文件。
- `operator`：操作人标识。

响应只返回文件名、来源类型和结果，不返回服务器临时路径或绝对路径。

```json
{
  "filename": "demo.txt",
  "source_type": ".txt",
  "result": "✅ 已写入知识库。"
}
```

### POST `/api/v1/knowledge/web-ingest`

```json
{
  "urls": "https://example.com/a\nhttps://example.com/b",
  "operator": "api"
}
```

### POST `/api/v1/knowledge/sync`

同步已删除来源。

### POST `/api/v1/knowledge/snapshot`

```json
{
  "tag": "before-change"
}
```

### POST `/api/v1/knowledge/rollback`

```json
{
  "snapshot_name": "snapshot_xxx",
  "confirm_name": "snapshot_xxx"
}
```

`confirm_name` 必须与 `snapshot_name` 完全一致。响应不得暴露快照绝对路径。

## Trace API

以下接口均需要 Admin Token。

### GET `/api/v1/traces`

```json
{
  "items": [
    {
      "trace_id": "abc12345",
      "updated_at": 1770000000.0,
      "size": 4096
    }
  ]
}
```

### GET `/api/v1/traces/{trace_id}`

```json
{
  "trace_id": "abc12345",
  "events": [
    {
      "event": "tool_start",
      "tool": "python",
      "args_preview": "{'code': '<redacted code,len=120>'}",
      "code_preview": "<redacted code,len=120>"
    }
  ]
}
```

Trace API 只返回脱敏投影，不返回完整工具代码、完整工具参数、完整工具结果、完整模型输入输出。
