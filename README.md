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

### (4) 启动应用

python：
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

默认访问地址：`http://127.0.0.1:7860`

日志等级可通过环境变量 `LOG_LEVEL` 控制（`DEBUG`/`INFO`/`WARNING`/`ERROR`/`CRITICAL`）。


## 目录结构（核心）

```text
agent_study_record/
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

1. 用户在 Gradio 输入问题（`app/ui/*.py` 定义界面，`app/runtime.py` 执行回调）
2. `ReactAgent.execute_stream()` 调用 `create_agent(...)` 流式推理
3. Agent 通过 `agent/tools/registry.py` 注册工具并按需调用
4. `agent/middleware.py` 记录模型/工具事件到 `logs/traces/*.jsonl`
5. RAG/Memory 工具进入 `rag/*`，访问 Chroma 向量库并返回结果

## 可用工具（当前注册）

- `rag_summarize`
- `web_search`
- `fill_context_for_report`
- `python`
- `matlab`
- `store_memory`
- `search_memory`

## Gradio 页面与 API

- 智能体对话：流式 ReAct 交互
  - `stream_thread_reply`（按 thread_id 处理多会话）
  - `create_chat_thread` / `switch_chat_thread` / `rename_chat_thread` / `close_chat_thread`
  - 会话会在重启后从 `memory_db/thread_<n>.db` 恢复；关闭会话即删除对应 db
- 在线 RAG：`rag_query`
  - `rag_metrics_refresh`
  - `rag_metrics_reset`
- 知识库管理：
  - `knowledge_upload`
  - `knowledge_web_ingest`
  - `knowledge_sync`
  - `knowledge_snapshot`
  - `knowledge_rollback`

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



