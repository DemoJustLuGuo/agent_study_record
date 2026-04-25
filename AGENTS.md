# AGENTS.md — 通信系统智能体项目协作规则

本文件是 AI/Agent 在本仓库内工作的最高优先级项目规则。执行任何代码、文档、配置或测试变更前，先按本文件判断项目边界、命令、验收标准和禁止行为。

## 1. 项目定位

- 项目类型：通信系统智能体 Web 工作台。
- 主要用途：提供通信领域 ReAct Agent 对话、RAG 检索问答、知识库生命周期管理、长期/短期记忆和工具调用追踪。
- 运行形态：Gradio Web UI，入口为 `python -m app.main`，默认监听 `127.0.0.1:7860`。
- 领域角色：Communication Engineer Agent，面向无线通信、协议分析、信号处理、网络故障定位、工程参数评估等任务。

核心目录：

```text
app/                    # Gradio UI、回调、会话线程管理
agent/                  # ReactAgent、中间件、工具注册与工具实现
rag/                    # Chroma 向量库、RAG、知识库生命周期、长期记忆
model/                  # ChatOpenAI / OpenAIEmbeddings 工厂
utils/                  # 配置、路径、日志、文件加载、提示词加载
model/config/           # 模型配置
agent/config/           # 记忆与提示词路径配置
agent/prompts/          # Agent 主提示词与报告提示词
rag/config/             # Chroma、检索、分块、网页入库配置
```

## 2. 技术栈与版本

以 `requirements.txt` 为准，当前关键栈：

- Python 3.10+
- Gradio 5.49.1
- LangChain 1.2.11
- LangChain Core 1.2.18
- LangGraph 1.1.0
- langgraph-prebuilt 1.0.8
- langchain-openai
- langchain-chroma 1.1.0
- ChromaDB 1.5.5
- langchain-experimental
- pypdf 6.9.0

默认模型接入为 OpenAI 兼容接口，当前配置面向 SiliconFlow / MiniMax-M2.5 与 Qwen3-Embedding-8B。模型名、base_url、embedding、温度等必须从配置读取，不得在业务代码中硬编码。

## 3. 开发期 Skills 调用

允许 Code Agent 使用 `langchain-ai/langchain-skills` 提供的 Agent Skills 作为开发期参考资料，以提升 LangChain / LangGraph / Deep Agents 代码质量。

安装方式（仅用于支持 Agent Skills 规范的编码代理，如 Claude Code、Cursor、Windsurf 等）：

```bash
npx skills add langchain-ai/langchain-skills --skill '*' --yes
```

如需全局安装：

```bash
npx skills add langchain-ai/langchain-skills --skill '*' --yes --global
```

调用要求：

- 涉及 LangChain / LangGraph / Deep Agents 设计或重构时，Code Agent 必须先参考对应 skill，再修改代码。
- 若本地未安装这些 skill，可参考 `https://github.com/langchain-ai/langchain-skills/` 的 README 和 `SKILL.md` 内容，但不得复制大段外部文档进仓库。
- skill 只作为工程实现指导，最终代码仍必须遵守本项目的 Tool 注册、trace、配置外置、安全边界和测试规则。

推荐 skill 使用场景：

| 任务类型 | 必须优先参考的 skill | 本项目关注点 |
|---|---|---|
| 框架选型、Agent 架构调整 | `framework-selection` | 判断继续使用 `create_agent`、引入 LangGraph 状态机，或是否需要 Deep Agents |
| 依赖新增、版本兼容 | `langchain-dependencies` | 保持 `requirements.txt` 与 LangChain 1.x / LangGraph 1.x 兼容 |
| Agent、Tool、结构化输出 | `langchain-fundamentals` | `create_agent`、`@tool(args_schema=...)`、结构化输出、流式响应 |
| 中间件、人工确认、危险工具审批 | `langchain-middleware` | `python` / `matlab` 等高风险工具的审批、审计和降级 |
| RAG 管线、向量库、分块 | `langchain-rag` | Chroma 检索、文档加载、chunk 策略、引用输出 |
| LangGraph 状态、节点、边 | `langgraph-fundamentals` | 当 `ReactAgent` 需要显式状态机或复杂分支时使用 |
| 短期记忆、checkpointer、跨线程状态 | `langgraph-persistence` | `memory_db/thread_<n>.db`、`thread_id`、会话恢复 |
| 人工审核、interrupt/Command | `langgraph-human-in-the-loop` | 高风险工具调用和知识库回滚审批 |
| Deep Agents 评估 | `deep-agents-core`、`deep-agents-memory`、`deep-agents-orchestration` | 仅在明确要升级为 Deep Agents 架构时参考 |

## 4. 项目专属命令

在 Windows PowerShell 或项目根目录执行。不要只写通用命令，必须带上本项目的入口、路径或参数。

### 环境与启动

```powershell
python -m pip install -r requirements.txt
$env:OPENAI_API_KEY = "<从安全渠道取得的真实密钥>"
$env:SILICONFLOW_API_KEY = $env:OPENAI_API_KEY
$env:LOG_LEVEL = "INFO"
python -m app.main
```

可选启动脚本：

```powershell
.\Launch.ps1
```

```bat
launch.bat
```

调试 Agent 决策链时使用：

```powershell
$env:LANGCHAIN_DEBUG = "1"
$env:APP_DEBUG = "1"
python -m app.main
```

### 知识库与向量生命周期

```powershell
python rag/vector_store.py load
python rag/vector_store.py sync
python rag/vector_store.py snapshot --tag <safe_tag>
python rag/vector_store.py rollback <snapshot_dir_name>
```

要求：

- `rollback` 会替换当前 `chroma_db/`，只有用户明确要求回滚时才能执行。
- 执行 `snapshot` 或 `rollback` 前，先确认目标目录和当前业务意图。
- 不要手工删除 `chroma_db/`、`memory_db/`、`chroma_manifest.json`、`md5.text` 来“修复”数据问题。

### 格式化与基础检查

```powershell
python -m black agent app rag model utils
python -m compileall -q agent app rag model utils
```

只修改少量 Python 文件时，Black 命令必须限定到本次改动文件，例如：

```powershell
python -m black agent/tools/modules/protocol_tools.py agent/tools/registry.py
```

## 5. 测试框架与验收标准

标准测试框架为 `pytest`。新增或修改可执行逻辑时，必须补充或更新 `tests/` 下的 pytest 用例；当前仓库若缺少测试目录，需要在变更中创建最小测试覆盖。

推荐测试命令：

```powershell
python -m pytest tests -q
python -m compileall -q agent app rag model utils
```

按变更类型执行附加验证：

- Agent/工具变更：测试工具 `args_schema` 校验、成功返回、失败返回、注册表可发现；必要时用 `ReactAgent` mock 模型验证路由。
- RAG/向量库变更：测试分块、metadata、同 MD5 多来源、删除源文件同步、snapshot/rollback；禁止直接依赖真实线上密钥。
- UI 回调变更：测试 `app/runtime.py` 的纯函数和回调返回结构，确认 Gradio update 对象字段不破坏现有页面。
- 配置变更：测试缺失键、非法类型、环境变量密钥解析、启动期错误信息。
- 文档变更：至少运行 `python -m compileall -q agent app rag model utils`，确认没有误改代码；检查命令与真实入口一致。

验收标准：

- 所有新增/修改 Python 文件已执行 Black。
- `python -m compileall -q agent app rag model utils` 通过。
- 与本次变更相关的 `pytest` 用例通过；若测试无法运行，必须在最终说明中写明原因和残余风险。
- 不引入明文密钥、绝对本机路径、运行时数据库、日志或向量库二进制到提交内容。
- Agent 工具名称、注册表、提示词授权、README/开发规范说明保持一致。

### 5.1 Skills 辅助开发的测试用例要求

当 Code Agent 因参考 `langchain-ai/langchain-skills` 而修改本项目代码时，必须按使用的 skill 补充对应测试：

| 使用的 skill | 必补测试用例 |
|---|---|
| `langchain-fundamentals` | Tool 必须有 `args_schema`；工具能通过 `invoke({...})` 成功执行；非法参数触发 Pydantic 校验或统一失败返回；`agent/tools/registry.py` 能发现新工具 |
| `langchain-middleware` | 中间件写入 `logs/traces/<trace_id>.jsonl` 的事件名、trace_id、耗时字段；工具异常时写入 `tool_error`；日志不包含完整密钥 |
| `langchain-rag` | 检索返回数量符合配置；references metadata 已脱敏；空知识库或低命中时返回可解释结果；分块参数变更不破坏入库 |
| `langgraph-persistence` | 相同 `thread_id` 能恢复会话状态；不同 `thread_id` 状态隔离；关闭会话后不会误删其他会话 DB |
| `langgraph-human-in-the-loop` / `langchain-middleware` | 高风险工具或 rollback 操作必须经过显式审批开关；拒绝审批时不执行副作用 |
| `langchain-dependencies` | `requirements.txt` 中新增依赖可安装；关键版本不破坏 `python -m compileall -q agent app rag model utils` |
| Deep Agents 相关 skills | 必须证明不改变现有 Gradio 入口；新增能力应有单独配置开关和回退路径 |

测试命名建议：

```text
tests/test_tools_<tool_name>.py
tests/test_middleware_trace.py
tests/test_rag_retrieval.py
tests/test_chat_persistence.py
tests/test_config_validation.py
```

优质测试示例：

```python
def test_registered_tool_has_args_schema():
    from agent.tools.registry import get_registered_tool_map

    tool = get_registered_tool_map()["rag_summarize"]
    assert tool.args_schema is not None
    assert "query" in tool.args_schema.model_fields
```

```python
def test_tool_failure_contract():
    from agent.tools.modules.shared import format_tool_failure

    result = format_tool_failure(
        tool_name="demo",
        reason="输入为空",
        solution="请提供有效输入。",
    )
    assert result.startswith("【失败】demo调用失败")
    assert "原因：输入为空" in result
    assert "解决方案：请提供有效输入。" in result
```

## 6. 编码规则

### 6.1 Tool 必须显式 args_schema

所有 LangChain Tool 必须用 Pydantic `BaseModel` 定义入参。禁止只依赖函数签名隐式推断。

优质示例：

```python
from pydantic import BaseModel, Field
from langchain_core.tools import tool


class HDLCParseArgs(BaseModel):
    hex_frame: str = Field(description="HDLC 帧十六进制字符串，例如 7e03cf...7e")
    decode_payload: bool = Field(default=True, description="是否按 UTF-8 尝试解码信息字段")


@tool(args_schema=HDLCParseArgs, description="解析 HDLC 帧并返回字段、载荷和 FCS 校验结果")
def parse_hdlc(hex_frame: str, decode_payload: bool = True) -> str:
    """解析 HDLC 帧。hex_frame 单位为字节序列的十六进制文本。"""
    frame = bytes.fromhex("".join(hex_frame.split()))
    if len(frame) < 6 or frame[0] != 0x7E or frame[-1] != 0x7E:
        return "【失败】parse_hdlc调用失败\n原因：缺少 HDLC 起止标志 0x7E\n解决方案：请提供完整帧。"
    ...
```

注册要求：

- 在 `agent/tools/modules/<name>_tools.py` 实现工具。
- 在 `agent/tools/registry.py` 加入 `_REGISTERED_TOOLS`。
- 在 `agent/tools/modules/__init__.py` 和必要的兼容导出层同步导出。
- 在 `agent/prompts/main_prompt.txt` / `agent/prompts/report_prompt.txt` 的工具授权段落补充使用场景。

### 6.2 Chain 输出优先结构化

需要被程序消费的 Chain 输出必须使用 Pydantic parser 或 `with_structured_output()`。仅面向用户最终展示的自由文本可以保留 Markdown/纯文本。

优质示例：

```python
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser


class RAGAnswer(BaseModel):
    summary: str = Field(description="结论摘要")
    key_evidence: list[str] = Field(default_factory=list, description="引用依据")
    confidence: float = Field(ge=0, le=1, description="置信度")


parser = PydanticOutputParser(pydantic_object=RAGAnswer)
chain = prompt | model | parser
```

### 6.3 通信工程计算必须可复现

- 信号处理、调制解调、FFT、滤波必须遵循采样率、Nyquist、单位归一化等基本规则。
- 采样率、频率、功率等参数必须在变量名、docstring 或注释中标明单位。
- 优先使用 NumPy/SciPy，避免手写循环实现标准数值算法。

优质示例：

```python
import numpy as np
from scipy.fft import fft, fftfreq


SAMPLE_RATE_HZ: float = 48_000.0  # 基带采样率，单位 Hz


def compute_single_sided_spectrum(samples: np.ndarray) -> dict[str, list[float]]:
    """计算单边幅度谱。

    Args:
        samples: 时域采样序列。

    Returns:
        freqs_hz: 频率轴，单位 Hz。
        magnitudes: 单边幅度谱，按 2/N 归一化。
    """
    n = int(samples.size)
    if n == 0:
        return {"freqs_hz": [], "magnitudes": []}
    freqs = fftfreq(n, d=1.0 / SAMPLE_RATE_HZ)
    mags = 2.0 / n * np.abs(fft(samples))
    positive = freqs >= 0
    return {
        "freqs_hz": freqs[positive].tolist(),
        "magnitudes": mags[positive].tolist(),
    }
```

### 6.4 协议解析先写帧结构

新增通信协议解析工具前，必须在代码注释或文档中写明帧结构、字段长度、字节序和校验规则。

```python
"""
HDLC 帧结构：

  Flag | Address | Control | Payload | FCS        | Flag
  0x7E | 1 byte  | 1 byte  | N bytes | 2 bytes LE | 0x7E

- FCS: CRC-16-CCITT，按接收帧尾部小端字节序解析。
- Payload: 信息字段，可选 UTF-8 解码；失败时返回 hex。
"""
```

### 6.5 中间件必须保留 trace_id

新增中间件必须写 JSONL trace，并复用 `agent/middleware.py` 的 `_write_trace` 风格。日志内容要截断和脱敏，不得写入完整 API Key、完整用户隐私数据或超大模型响应。

```python
_write_trace(
    runtime,
    "tool_end",
    tool=tool_name,
    elapsed_ms=elapsed_ms,
    result_preview=_preview_text(result_text, limit=800),
)
```

### 6.6 配置外置

以下内容必须来自配置或环境变量：

- 模型名、base_url、temperature、embedding 模型。
- RAG top_k、chunk_size、chunk_overlap、rerank 权重。
- 提示词路径。
- 高风险工具开关、管理操作鉴权参数。

禁止在业务代码中硬编码真实密钥、真实私有 URL、个人路径和临时本机配置。

## 7. AI 禁止行为

以下操作未经用户明确要求不得执行：

- 修改、提交或展示真实 API Key；不得把真实密钥写入README、日志或测试快照。
- 删除或重建 `chroma_db/`、`memory_db/`、`logs/`、`chroma_manifest.json`、`md5.text`、`rag/data/`。
- 执行 `git reset --hard`、`git checkout -- <file>`、批量删除、强制清理未跟踪文件。
- 执行 `rag/vector_store.py rollback` 或删除快照，除非用户明确指定快照和目的。
- 把 Gradio 服务改为默认 `0.0.0.0` 暴露，除非同时补充鉴权和用户明确要求。
- 放宽 `.gitignore` 以纳入日志、向量库、会话 DB、缓存或密钥文件。
- 引入新的 LLM provider、数据库、前端框架或大型依赖，除非需求明确且说明迁移成本。
- 绕过 `agent/tools/registry.py` 私自让 Agent 调用未注册工具。
- 在工具中新增无审计的任意文件读写、网络访问、系统命令执行能力。

如果发现现有工作区已有用户改动，不得回滚。先阅读差异并在当前变更中避开或兼容。

## 8. 提交、更新日志与 PR 规范

### Commit

遵循 Conventional Commits：

```text
<type>(<scope>): <subject>
```

允许的 type：

- `feat`: 新功能
- `fix`: 缺陷修复
- `refactor`: 不改变行为的重构
- `docs`: 文档变更
- `test`: 测试相关
- `chore`: 构建、依赖、脚本、维护
- `perf`: 性能优化

建议 scope：

- `agent`
- `tools`
- `rag`
- `config`
- `app`
- `utils`
- `prompts`
- `docs`

示例：

```text
feat(tools): 添加 HDLC 协议帧解析工具
fix(rag): 修复同 MD5 多来源向量缺失问题
docs(docs): 重写 AGENTS 项目协作规则
test(rag): 增加向量生命周期回归测试
```

### 更新日志

参考 `更新日志.md` 的现有格式。功能、架构、依赖、启动链路、安全策略或测试体系发生变化时，必须追加新版本段落：

```markdown
## v0.13.1 - YYYY-MM-DD
### 变更摘要
- ...

### 涉及文件
- ...
```

版本递增规则：

- 功能里程碑：递增次版本，例如 `v0.13.0 -> v0.14.0`。
- 修复、文档、小型增强：递增修订号，例如 `v0.13.0 -> v0.13.1`。

### PR 说明

PR 必须包含：

- 变更摘要：说明改了什么和为什么。
- 影响范围：列出 `agent`、`rag`、`app`、`config`、`prompts` 等受影响模块。
- 测试结果：贴出实际执行的命令和结果。
- 风险与回滚：说明是否影响向量库、记忆库、密钥配置、工具安全边界。
- 截图或日志：UI/Agent 流式交互变更需要提供关键截图或 trace 摘要。

不要在 PR 中粘贴真实密钥、完整私有日志、完整用户对话或本机绝对路径。

## 9. 常见任务清单

### 新增 Agent 工具

1. 在 `agent/tools/modules/` 新增或扩展工具模块。
2. 定义 Pydantic `args_schema`。
3. 实现工具，失败返回统一使用 `【失败】工具名调用失败`、`原因：`、`解决方案：`。
4. 注册到 `agent/tools/registry.py`。
5. 更新 `agent/tools/modules/__init__.py` 和兼容导出。
6. 更新 `agent/prompts/main_prompt.txt` 与 `agent/prompts/report_prompt.txt` 的工具授权说明。
7. 增加 pytest，覆盖参数校验、成功路径、失败路径、注册表可见性。
8. 执行 Black、pytest、compileall。
9. 若是用户可见能力，更新 README/开发规范/更新日志。

### 修改 RAG 或知识库生命周期

1. 先确认是否影响 `chroma_db/`、manifest、md5、snapshot。
2. 用临时测试目录或 mock Chroma，避免测试污染真实向量库。
3. 覆盖新增、更新、删除、重复内容、多来源同 MD5、回滚失败等场景。
4. 前端 references 只展示脱敏 metadata，不暴露服务器绝对路径。
5. 执行 `python -m pytest tests -q` 和 `python -m compileall -q agent app rag model utils`。

### 修改配置或启动链路

1. 保持 `launch.bat`、`Launch.ps1`、README、AGENTS 命令一致。
2. 配置新增字段必须有默认值、校验逻辑和失败提示。
3. 密钥只允许使用环境变量名或运行时环境变量，不写真实值。
4. 执行启动前置检查：配置读取、模型工厂初始化、compileall。
