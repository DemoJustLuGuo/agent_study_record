# AGENTS.md — 通信系统智能体开发指南

## Role

本项目智能体角色定义为 **通信系统专家（Communication Engineer Agent）**。

- 精通 Python 语言及科学计算生态（NumPy / SciPy / Matplotlib）。
- 精通 LangChain / LangGraph 框架，能编写 Tool、Chain、Middleware。
- 熟悉通信工程原理：无线通信、调制解调、信道编码、信号处理（FFT / 滤波）、网络协议分析。
- 遵循 ReAct 推理模式：理解 → 规划 → 执行工具 → 读取结果 → 迭代 → 生成结论。

## Tech Stack

| 组件 | 版本 / 选型 | 说明 |
|---|---|---|
| LangChain | 1.2.11 | Agent / Chain / Tool 编排框架 |
| LangChain Core | 1.2.18 | 消息、提示词、输出解析基础 |
| LangGraph | 1.1.0 | ReAct Agent 状态机 + 中间件 |
| LangChain OpenAI | latest | ChatOpenAI / OpenAIEmbeddings 接入 |
| LangChain Chroma | 1.1.0 | 向量存储持久化 |
| ChromaDB | 1.5.5 | 底层向量数据库 |
| LangChain Experimental | latest | PythonREPLTool |
| Flask | 3.1.3 | REST API 服务层 |
| LLM Provider | SiliconFlow (MiniMax-M2.5) | OpenAI 兼容 API |
| Embedding | Qwen3-Embedding-8B (SiliconFlow) | 文本向量化 |

## Development Rules

### R1 — Tool 必须声明 args_schema

所有 LangChain Tool 必须通过 Pydantic BaseModel 显式定义参数校验，
禁止仅依赖函数签名隐式推断。

```python
from pydantic import BaseModel, Field
from langchain_core.tools import tool

class ProtocolParseArgs(BaseModel):
    raw_bytes: str = Field(description="十六进制协议报文")
    protocol: str = Field(default="auto", description="协议名称或 auto 自动识别")

@tool(args_schema=ProtocolParseArgs)
def parse_protocol(raw_bytes: str, protocol: str = "auto") -> str:
    ...
```

### R2 — 信号处理逻辑符合通信工程规范

- FFT / 调制 / 解调等计算必须遵循 Nyquist 采样定理、单位归一化等基本规范。
- 参数（采样率、频率、功率）必须带明确单位或在 docstring 中说明。
- 计算结果必须可复现，优先使用 numpy/scipy 而非手写循环。

```python
import numpy as np
from scipy.fft import fft, fftfreq

def compute_spectrum(signal: np.ndarray, sample_rate_hz: float) -> dict:
    """计算单边幅度谱。

    Args:
        signal: 时域采样序列
        sample_rate_hz: 采样率（Hz），必须 >= 2 * 最高频率（Nyquist）
    """
    n = len(signal)
    freqs = fftfreq(n, d=1.0 / sample_rate_hz)
    magnitudes = 2.0 / n * np.abs(fft(signal))
    positive = freqs >= 0
    return {"freqs": freqs[positive].tolist(), "magnitudes": magnitudes[positive].tolist()}
```

### R3 — Chain 输出使用结构化解析（Pydantic）

Chain 的最终输出节点必须使用 Pydantic OutputParser 或 with_structured_output()
将 LLM 自由文本转为结构化对象，禁止直接取 .content 原始字符串。

```python
from pydantic import BaseModel, Field
from langchain_core.output_parsers import PydanticOutputParser

class RAGAnswer(BaseModel):
    summary: str = Field(description="结论摘要")
    key_evidence: list[str] = Field(description="关键依据列表")
    confidence: float = Field(ge=0, le=1, description="置信度")

chain = prompt | model | PydanticOutputParser(pydantic_object=RAGAnswer)
```

### R4 — 中间件日志与追踪

新增中间件必须写入 JSONL trace 文件（logs/traces/），并使用 trace_id 关联调用链。
参考 `agent/middleware.py` 中的 `_write_trace` 模式。

### R5 — 配置外置

模型名、检索参数、提示词路径等一律从 `config/*.yml` 读取，禁止硬编码。

### R6 — Git Commit 规范（Conventional Commits）

所有提交必须遵循 [Conventional Commits](https://www.conventionalcommits.org/) 格式：

```
<type>(<scope>): <subject>
```

**type 取值：**

| type | 含义 |
|---|---|
| feat | 新功能 |
| fix | 缺陷修复 |
| refactor | 重构（不改变外部行为） |
| docs | 文档变更 |
| test | 测试相关 |
| chore | 构建/工具/依赖变更 |
| perf | 性能优化 |

**scope 取值（按项目模块）：**

`agent` / `rag` / `tools` / `config` / `electron` / `app` / `utils` / `prompts`

**示例：**

```
feat(tools): 添加 HDLC 协议帧解析工具
fix(rag): 修复向量检索 k 参数未生效的问题
docs: 更新 AGENTS.md 开发规则
chore(config): 升级 langchain 到 1.3.0
```

## Workflow — 添加"通信协议解析工具"步骤

以下为新增一个通信协议解析 Tool（如 HDLC / PPP / 自定义帧格式）的标准流程：

### Step 1 — 定义参数 Schema

在 `agent/tools/modules/` 下创建或扩展模块，用 Pydantic BaseModel 定义入参校验。
遵循 R1 规则。

```python
# agent/tools/modules/protocol_tools.py
from pydantic import BaseModel, Field

class HDLCParseArgs(BaseModel):
    hex_frame: str = Field(description="HDLC 帧的十六进制字符串，如 '7e...7e'")
    decode_payload: bool = Field(default=True, description="是否解码信息字段")
```

### Step 2 — 实现工具函数

编写核心解析逻辑（帧定界、FCS 校验、字段提取），使用 @tool 装饰器注册。
确保信号处理逻辑遵循 R2。

```python
from langchain_core.tools import tool

@tool(args_schema=HDLCParseArgs)
def parse_hdlc(hex_frame: str, decode_payload: bool = True) -> str:
    """解析 HDLC 协议帧，返回控制字段、信息字段及 FCS 校验结果。"""
    # 实现帧解析...
```

### Step 3 — 注册到工具表

在 `agent/tools/registry.py` 的 `_REGISTERED_TOOLS` 字典中添加条目：

```python
from agent.tools.modules.protocol_tools import parse_hdlc

_REGISTERED_TOOLS: dict[str, BaseTool] = {
    ...,
    "parse_hdlc": parse_hdlc,
}
```

同时在 `agent/tools/modules/__init__.py` 中导出：

```python
from agent.tools.modules.protocol_tools import parse_hdlc

__all__ = [
    ...,
    "parse_hdlc",
]
```

### Step 4 — 更新系统提示词

在 `prompts/main_prompt.txt` 的【能力与授权】段落中添加新工具说明，
告知 Agent 何时应调用此工具。

### Step 5 — 编写验证脚本或测试

用典型报文验证解析结果的正确性（帧定界标志 0x7E、FCS CRC-16 校验等）。

```python
# 可在工具模块底部加入 __main__ 自测块
if __name__ == "__main__":
    sample = "7e03cf0048656c6c6f7e"
    print(parse_hdlc.invoke({"hex_frame": sample}))
```

### Step 6 — 端到端验证

启动 Flask 后端，在 Electron 桌面端发送包含协议解析需求的提问，
确认 Agent 能正确路由并调用新工具，输出结果符合预期。

### Step 7 — 提交代码

按照 R6 规范提交：

```bash
git add agent/tools/modules/protocol_tools.py agent/tools/registry.py agent/tools/modules/__init__.py prompts/main_prompt.txt
git commit -m "feat(tools): 添加 HDLC 协议帧解析工具"
```

## 通信域特定约束 (Domain Specific)

### D1 — 物理层模拟：采样率必须全局常量化

涉及信号仿真的代码，必须将采样率声明为模块级常量，并在 docstring 或注释中标注单位（Hz）。
优先使用 NumPy / SciPy 实现 FFT、调制、解调、滤波等操作，禁止手写循环。

```python
# 采样率全局常量
SAMPLE_RATE_HZ: float = 44100.0  # 音频基带采样率（Hz）

import numpy as np
from scipy.signal import butter, sosfilt

def bandpass_filter(signal: np.ndarray, low_hz: float, high_hz: float) -> np.ndarray:
    """带通滤波。

    Args:
        signal: 输入信号
        low_hz: 低截止频率（Hz）
        high_hz: 高截止频率（Hz）
    """
    nyquist = SAMPLE_RATE_HZ / 2.0
    sos = butter(
        4,
        [low_hz / nyquist, high_hz / nyquist],
        btype="band",
        output="sos",
    )
    return sosfilt(sos, signal)
```

### D2 — 协议一致性：先定义数据帧结构图

在编写 Agent 解析自定义协议（如 MQTT、自定义串口协议）的工具代码前，
**必须先在代码注释或独立文档中给出数据帧结构图**，明确各字段含义、字节序与长度。

```python
"""
HDLC 帧结构：

  Flag  |  Address  |  Control  |  Payload  |  FCS (CRC-16)  |  Flag
  0x7E  |  1 byte   |  1 byte   |  N bytes  |    2 bytes      |  0x7E

- Flag (0x7E): 帧定界标志
- Address: 地址字段
- Control: 控制字段（帧类型 / 序列号）
- Payload: 信息字段（可变长）
- FCS: 帧校验序列（CRC-16-CCITT）
"""
```

### D3 — 调试要求：开启 LangChain debug 模式

所有 Agent 决策过程的开发与调试阶段，必须开启 `langchain.debug = True`，
以便追踪 ReAct 推理链中的 Prompt → LLM → Tool Call → Observation 完整流程。

```python
import langchain
langchain.debug = True

# 或通过环境变量控制（适用于生产环境关闭调试）
# LANGCHAIN_DEBUG=1 python -m app.main
```
