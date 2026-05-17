# 通信系统智能体项目（Agent + RAG）

这是一个基于 `LangChain + LangGraph + FastAPI + React + ChromaDB` 的通信领域智能体项目，支持 ReAct 工具调用、知识库检索增强（RAG）、长时记忆，以及知识库生命周期管理（上传/同步/快照/回滚）。

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

### (2) 配置本地环境

复制 `.env.example` 为 `.env`，填写本机开发所需的环境变量：

- `APP_ADMIN_TOKEN`：FastAPI 管理类接口鉴权 token。
- `OPENAI_BASE_URL`：OpenAI 兼容接口地址；未设置时继续使用 `model/config/agent.yml` 中的 `openai_base_url`。
- `OPENAI_API_KEY` / `SILICONFLOW_API_KEY`：真实密钥只放在 `.env` 或系统环境变量中。
- `VITE_API_BASE_URL`：前端本地开发访问的后端地址。管理 token 不使用 `VITE_*`，避免被打包进浏览器代码。

`.env` 已被 `.gitignore` 忽略，不要提交真实密钥。管理页在已通过当前 token 鉴权后可轮换 `APP_ADMIN_TOKEN`，后端会写回 `.env` 并更新当前进程环境变量；手工修改 `.env` 后仍需要重启后端。前端 `VITE_*` 变量变更后需要重启 Vite。

### (3) 初始化知识库（建议）

```bash
python rag/vector_store.py load
```

### (4) 启动后端与前端

FastAPI 后端：

```powershell
venv\Scripts\python.exe -m api.main
```

React 控制台：

```powershell
cd web
npm install
npm run dev
```

默认后端地址：`http://127.0.0.1:8000`。默认前端地址：`http://127.0.0.1:5173`。

仓库不再提供 `Launch.ps1` / `launch.bat` 一键启动脚本。前后端启动均使用上面的显式命令。

日志等级可通过环境变量 `LOG_LEVEL` 控制（`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`）。


## 目录结构（核心）

```text
agent_study_record/
├─ web/                    # React + TypeScript + Tailwind 前端控制台
├─ api/                    # FastAPI 正式后端控制面
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

## FastAPI 控制面与 React 前端

- `cd web && npm run dev` 启动的是 React/TS/Tailwind 前端控制台，覆盖 Chat、RAG、Knowledge、Traces 日常工作流。
- `venv\Scripts\python.exe -m api.main` 启动的是正式 FastAPI 后端控制面，外部集成、新前端对接、聊天 SSE、RAG 查询、知识库管理和 trace 查询都应使用 FastAPI。
- FastAPI 管理类接口使用 `APP_ADMIN_TOKEN` 鉴权；模型连接地址和真实 API Key 只通过 `.env` 或系统环境变量管理，不通过 Web UI 或 API 写入。React 前端不读取 `APP_ADMIN_TOKEN`，只在浏览器本地保存用户输入的管理 token。

## 知识库生命周期（CLI）

```bash
python rag/vector_store.py load
python rag/vector_store.py sync
python rag/vector_store.py snapshot --tag release_note
python rag/vector_store.py rollback <snapshot_name>
```

## 本地运行数据移除

仓库不再提供 `Remove-Logs.ps1` / `Remove-RagDB.ps1` 清理脚本。需要清理本地运行数据时，先停止后端和前端进程，再按目标执行显式命令。

清理日志与 trace：

```powershell
Remove-Item -LiteralPath .\logs -Recurse -Force
```

清理 RAG 向量库与指纹文件（会使知识库需要重新 `load` 或重新入库）：

```powershell
Remove-Item -LiteralPath .\chroma_db -Recurse -Force
Remove-Item -LiteralPath .\chroma_manifest.json -Force
Remove-Item -LiteralPath .\md5.text -Force
```

不要把 `chroma_db/`、`logs/`、`memory_db/`、`chroma_manifest.json` 或 `md5.text` 提交到 Git。清理 `memory_db/` 会删除本地会话记忆，默认不建议执行。

## 可观测性

- 普通日志：`logs/*.log`
- Trace 日志：`logs/traces/<trace_id>.jsonl`
- 在线 RAG 指标面板：查询成功率、空命中率、平均检索/重排/生成耗时、策略分布
- 中间件覆盖：
  - 工具调用开始/结束/异常
  - 模型调用前后与耗时
  - 系统提示词/报告提示词动态切换



