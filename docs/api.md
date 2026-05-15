# 后端 API 契约说明

本文档记录当前 FastAPI 后端的第一版响应契约。`api.main` 是正式后端控制面，`app.main` 保留为旧 Gradio UI / 本地调试入口：

```powershell
venv\Scripts\python.exe -m app.main
venv\Scripts\python.exe -m api.main
```

`api.main` 默认监听 `127.0.0.1:8000`。Gradio 默认监听 `127.0.0.1:7860`，但默认不展示 Gradio API，也不通过 Gradio API 暴露 UI 回调。若需要本地调试 Gradio API 文档，可显式设置：

```powershell
$env:GRADIO_SHOW_API = "1"
venv\Scripts\python.exe -m app.main
```

对外集成、管理操作和新前端对接应使用 FastAPI。管理类接口需要在运行环境设置 `APP_ADMIN_TOKEN`，请求时使用：

```text
Authorization: Bearer <APP_ADMIN_TOKEN>
```

真实 API Key 不通过后端 API 返回。通过 settings API 保存真实密钥时，只写入当前后端进程的 `os.environ`，多 worker 或重启后仍应通过进程启动环境配置。

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
  "version": "0.14.0"
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

创建新会话。响应包含 `thread_id`、`threads`、`choices`、`history`、`status`。`choices` 是兼容旧 Gradio 选择器的 `[label, value]` 元组列表，前端新实现可优先使用 `threads`。

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

## Knowledge API

以下接口均需要 Admin Token。

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

## Settings API

以下接口均需要 Admin Token。

### GET `/api/v1/settings/connection`

```json
{
  "openai_base_url": "https://...",
  "api_key_configured": false,
  "api_key": "",
  "status": "...",
  "note": "真实 API Key 不会通过 API 返回..."
}
```

### POST `/api/v1/settings/connection`

```json
{
  "openai_base_url": "https://...",
  "openai_api_key": "SILICONFLOW_API_KEY"
}
```

响应：

```json
{
  "message": "...",
  "note": "真实 API Key 写入 os.environ 时只影响当前后端进程..."
}
```

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
