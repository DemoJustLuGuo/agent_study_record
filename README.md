# 通信系统智能体项目（Agent + RAG）

基于 `LangChain + LangGraph + Gradio + ChromaDB` 的通信领域智能体项目，支持 ReAct 工具调用、知识库检索增强（RAG）、长时记忆，以及知识库生命周期管理（同步/快照/回滚）。

## 核心能力

- 通信领域 ReAct 智能体
- RAG 检索问答（Hybrid 召回 + 启发式重排 + 引用片段）
- 长时记忆写入与检索（`store_memory` / `search_memory`）
- 在线知识库上传与管理（文本上传 + 网页链接抓取入库）
- 工具调用过程可观测（日志 + Trace）

## 技术栈

- `Python 3.10+`
- `gradio==5.49.1`
- `langchain==1.2.11`
- `langchain-core==1.2.18`
- `langgraph==1.1.0`
- `langgraph-prebuilt==1.0.8`（与当前 `langgraph` 版本保持兼容）
- `langchain-chroma==1.1.0`
- `chromadb==1.5.5`
- `langchain-openai`（OpenAI 兼容接口，当前默认 SiliconFlow）
- `langchain-experimental`（`PythonREPLTool`）

## 目录结构（核心）

```text
agent_study_record/
├─ app/                    # Gradio UI（app_builder/runtime/ui/*）与启动入口
├─ agent/                  # ReactAgent、middleware、tools
├─ rag/                    # 向量库/RAG/知识库/记忆服务
├─ model/                  # ChatModel 与 Embedding 工厂
├─ model/config/           # 模型与推理配置
├─ rag/config/             # 向量检索参数与网页抓取参数
├─ agent/config/           # 提示词路径映射
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

## Gradio 页面与 API

- 智能体对话：流式 ReAct 交互
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



