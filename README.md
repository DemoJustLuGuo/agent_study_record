# 通信系统智能体项目（Agent + RAG）

这是一个基于 `LangChain + LangGraph + Gradio + ChromaDB` 的通信领域智能体项目，支持 ReAct 工具调用、知识库检索增强（RAG）、长时记忆，以及知识库生命周期管理（同步/快照/回滚）。

## 核心能力

- 通信领域 ReAct 智能体
- 智能体多会话标签页（左侧垂直会话列表，支持新建/切换/重命名/关闭）
- 短期记忆（`langgraph-checkpoint-sqlite`，每会话独立 `memory_db/thread_<n>.db`）
- 会话压缩（`SummarizationMiddleware`，触发策略与模型配置见 `agent/config/memory_config.yml`）
- RAG 检索问答（Hybrid 召回 + 启发式重排 + 引用片段）
- 长时记忆写入与检索（`store_memory` / `search_memory`）
- 在线知识库上传与管理（文本上传 + 网页链接抓取入库）
  - 网页抓取默认启用保守清洗：过滤广告、弹窗、页脚/侧栏等明显噪声区域
- 工具调用过程可观测（日志 + Trace）

## 快速开始
  
### (1) 安装依赖

```bash
pip install -r requirements.txt
```

### (2) 配置模型

编辑 `model/config/agent.yml` 或设置环境变量：

- `OPENAI_API_KEY`（可填环境变量名，如 `SILICONFLOW_API_KEY`）
- `openai_base_url`（默认 `https://api.siliconflow.cn/v1`）
- `chat_model_name`
- `embedding_model_name`

### (3) 初始化知识库（建议）

```bash
python rag/vector_store.py load
```

### (4) 启动后端与前端

FastAPI 后端：

```bash
python -m api.main
```

React 控制台：

```bash
cd web
npm install
npm run dev
```

默认后端地址：`http://127.0.0.1:8000`。默认前端地址：`http://127.0.0.1:5173`。

Gradio 旧 UI / 本地调试入口：

```bash
python -m app.main
```

Windows：

```bat
launch.bat
```

PowerShell：

```powershell
Launch.ps1
```

日志等级可通过环境变量 `LOG_LEVEL` 控制（`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`）。


## 目录结构（核心）

```text
agent_study_record/
├─ web/                    # React + TypeScript + Tailwind 前端控制台
├─ api/                    # FastAPI 正式后端控制面
├─ app/                    # Gradio UI（app_builder/runtime/ui/*）与启动入口
├─ agent/                  # ReactAgent、middleware、tools
├─ rag/                    # 向量库/RAG/知识库/记忆服务
├─ model/                  # ChatModel 与 Embedding 工厂
├─ model/config/           # 模型与推理配置
├─ rag/config/             # 向量检索参数与网页抓取参数
├─ agent/config/           # 提示词路径映射与记忆配置
├─ agent/prompts/          # Agent 提示词
├─ rag/prompts/            # RAG 提示词
├─ data/                   # 知识源文件
├─ chroma_db/              # 向量库持久化
└─ logs/                   # 运行日志与 trace
```

## 运行链路

1. 用户在 React 控制台输入问题（`web/src/*` 调用 FastAPI）
2. FastAPI 通过 `services/chat_service.py` 进入 Agent 流式服务
3. `ReactAgent.execute_events()` 调用 `create_agent(...)` 流式推理
4. Agent 通过 `agent/tools/registry.py` 注册工具并按需调用
5. `agent/middleware.py` 记录模型/工具事件到 `logs/traces/*.jsonl`
6. RAG/Memory 工具进入 `rag/*`，访问 Chroma 向量库并返回结果

## 可用工具（当前注册）

- `rag_summarize`
- `web_search`
- `fill_context_for_report`
- `python`
- `matlab`
- `store_memory`
- `search_memory`

## Gradio 页面与 FastAPI 控制面

- `cd web && npm run dev` 启动的是 React/TS/Tailwind 前端控制台，覆盖 Chat、RAG、Knowledge、Settings、Traces 日常工作流。
- `python -m app.main` 启动的是旧 Gradio UI / 本地调试入口，默认不展示 Gradio API，也不通过 Gradio API 暴露 UI 回调。
- 如需调试 Gradio API 文档，可在本地显式设置 `GRADIO_SHOW_API=1` 后启动 Gradio。
- `python -m api.main` 启动的是正式 FastAPI 后端控制面，外部集成、新前端对接、聊天 SSE、RAG 查询、知识库管理、连接设置和 trace 查询都应使用 FastAPI。
- FastAPI 管理类接口使用 `APP_ADMIN_TOKEN` 鉴权；真实 API Key 不应通过接口返回或写入文档。

## 知识库生命周期（CLI）

```bash
python rag/vector_store.py load
python rag/vector_store.py sync
python rag/vector_store.py snapshot --tag release_note
python rag/vector_store.py rollback <snapshot_name>
```

## 可观测性

- 普通日志：`logs/*.log`
- Trace 日志：`logs/traces/<trace_id>.jsonl`
- 在线 RAG 指标面板：查询成功率、空命中率、平均检索/重排/生成耗时、策略分布
- 中间件覆盖：
  - 工具调用开始/结束/异常
  - 模型调用前后与耗时
  - 系统提示词/报告提示词动态切换



