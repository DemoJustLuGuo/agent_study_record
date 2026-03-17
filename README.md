# AI Agent 框架 README（团队内开发版）

> 版本：2026-03（基于当前仓库代码快照）

## 1. 文档目标

本 README 面向团队内部开发，聚焦三件事：

1. 当前架构长什么样（模块边界与运行链路）
2. 目前开发不足在哪里（已识别技术债）
3. 下一步可扩展什么（可落地的演进方向）

---

## 2. 当前架构

### 2.1 总体架构图

```mermaid
flowchart TD
	 UI[Flask UI app/main.py] --> RA[ReactAgent]
	 RA --> AG[LangChain create_agent]

	 AG --> TOOLS[Tool Layer]
	 AG --> MW[Middleware Layer]

	 TOOLS --> T1[rag_summarize]
	 TOOLS --> T2[get_weather / get_user_location / get_user_id / get_current_month]
	 TOOLS --> T3[fetch_external_data]
	 TOOLS --> T4[fill_context_for_report]

	 T1 --> RAG[RAGSummarizeService]
	 RAG --> VS[VectorStoreService]
	 VS --> CH[(Chroma DB)]
	 RAG --> RP[rag prompt]
	 RAG --> LLM[chat model]

	 MW --> M1[monitor_tool]
	 MW --> M2[log_before_model]
	 MW --> M3[report_prompt_switch]
	 M3 --> P1[main_prompt]
	 M3 --> P2[report_prompt]

	 CFG[config/*.yml] --> RA
	 CFG --> VS
	 CFG --> RAG
	 CFG --> LLM
```

### 2.2 模块职责（按目录）

- app.py
	- 旧版 Streamlit 页面入口（保留）
- app/main.py
	- 轻量 Flask 页面入口（当前推荐）
	- 提供 /、/api/chat、/api/health
	- ReactAgent 惰性初始化，降低启动耗时
- agent/tools/react_agent.py
  - 封装 create_agent
  - 注入工具列表、系统提示词、中间件
- agent/tools/agent_tools.py
  - 定义工具函数（RAG、外部数据、用户上下文、天气等）
- agent/tools/middleware.py
  - 工具调用监控
  - 模型调用前日志
  - 按 context.report 动态切换提示词
- rag/vector_store.py
  - 文档加载与切分
  - Chroma 向量入库与 retriever 构建
- rag/rag_service.py
  - RAG 召回与摘要生成链
  - PromptTemplate + ChatModel + OutputParser
- model/factory.py
  - 聊天模型与 embedding 模型工厂
- utils/*
  - 配置读取、路径处理、日志、文件加载、提示词加载

### 2.3 请求执行链路

1. 用户在 UI 输入问题
2. ReactAgent 发起 agent.stream(..., stream_mode="values")
3. Agent 依据上下文决定直接回答或调用工具
4. monitor_tool 记录调用信息，并在 fill_context_for_report 后写入 context.report=True
5. report_prompt_switch 每次模型调用前选择 main_prompt 或 report_prompt
6. 若调用 rag_summarize，则进入 RAG 链：检索 -> 拼接上下文 -> LLM 生成
7. 输出逐块回传到 Flask 页面

### 2.4 数据与配置流

- 模型配置：config/rag.yml
- 向量库配置：config/chroma.yml
- 提示词路径配置：config/prompts.yml
- 外部业务数据配置：config/agent.yml
- 知识数据目录：data/
- 向量持久化目录：chroma_db/
- 文件去重指纹：md5.text

---

## 3. 本地开发与调试流程

### 3.1 建议启动顺序

先安装轻量前端依赖：

```bash
pip install flask
```

```bash
python rag/vector_store.py
python app/main.py
```

### 3.2 开发常用检查点

- 检查配置是否可读：config/*.yml 路径和键名
- 检查提示词是否有效：prompts/*.txt 当前应为可执行业务提示，而非占位文本
- 检查向量库是否已有数据：chroma_db/ 与 md5.text
- 检查日志输出：logs/

---

## 4. 当前开发不足（技术债清单）

以下问题按“优先级 + 影响面”整理，供迭代排期。

### 4.1 高优先级（建议优先修复）

1. 提示词仍是占位内容
	- main_prompt.txt / rag_summarize.txt / report_prompt.txt 当前均为占位文案
	- 直接影响 Agent 行为稳定性与业务可用性

2. 工具契约不一致
	- fetch_external_data 标注返回 str，但实际返回 dict 或 None
	- 异常分支注释写“返回空字符串”，代码未按该契约实现
	- 增加了调用侧解析风险

3. 非工具函数被加入 tools 列表
	- generate_external_data 为内部缓存函数，不是面向 LLM 的稳定业务工具
	- 放入 tools 可能导致模型误调用或无效调用路径

### 4.2 中优先级（可并行修复）

1. 时间上下文硬编码
	- get_current_month() 固定返回“当前月份是6月”
	- 会造成事实性错误，影响报告可信度

2. RAG 调试输出污染
	- rag_service.py 中 print_prompt 会打印完整提示词
	- 在生产日志中可能产生冗余与敏感信息暴露风险

3. 类型标注与实际不一致
	- retriever_docs() 标注返回 str，实际返回召回文档列表
	- 增加维护成本和静态检查噪声

4. 文件扫描异常返回值设计不合理
	- listdir_with_allowed_type 在目录非法时返回 allowed_types
	- 返回值语义与函数名不一致，调用端易出现隐式错误

### 4.3 低优先级（架构演进期处理）

1. 缺少依赖锁定文件
	- 当前仓库未见 requirements.txt / pyproject.toml
	- 环境复现成本偏高

2. 缺少自动化测试
	- 工具层、RAG 层、中间件层均未建立单元测试与回归测试

3. 向量数据生命周期管理不足
	- 当前主要依赖 md5 增量，缺少“删除源文件后向量清理”“版本回滚”等机制

---

## 5. 可扩展内容（建议路线）

### 5.1 Agent 与工具层扩展

1. 建立工具注册规范
	- 区分 internal function 与 agent tool
	- 统一入参与返回 Schema（建议 pydantic）

2. 增加工具权限与路由策略
	- 按场景白名单控制可用工具
	- 限制高成本工具的调用频率

3. 引入失败兜底策略
	- 工具超时/异常时，返回可解释降级消息

### 5.2 RAG 能力扩展

1. 检索优化
	- 多路召回（关键词 + 向量）
	- 加入 reranker 提升相关性

2. 数据治理
	- 文档 metadata 标准化（source、version、timestamp）
	- 设计增量更新 + 失效清理机制

3. 质量评估
	- 建立离线评测集，度量召回率/回答准确率

### 5.3 提示词与上下文扩展

1. 提示词版本化
	- 按场景维护 prompt v1/v2，并记录变更说明

2. 场景状态机扩展
	- 在 report 之外增加 review、analysis 等模式
	- 用显式状态迁移替代隐式上下文开关

### 5.4 工程化扩展

1. 依赖与环境标准化
	- 增加 requirements.txt 或 pyproject.toml
	- 固定关键版本，保证团队复现

2. 测试与 CI
	- 为工具层、RAG 层、中间件层补单元测试
	- 加入 lint/type-check/test 的最小 CI 流水线

3. 可观测性
	- 接入 LangSmith 或 OpenTelemetry
	- 统一链路追踪与错误定位

---

## 6. 建议迭代节奏（内部参考）

### Sprint 1（稳定性）

1. 替换三类占位提示词
2. 修正工具返回契约与类型标注
3. tools 列表仅保留真正工具
4. 去除或降级 print_prompt 调试输出

### Sprint 2（可扩展性）

1. 引入依赖锁定和基础 CI
2. 建立最小评测集与回归测试
3. 增加 RAG metadata 与增量更新策略

### Sprint 3（能力升级）

1. 引入 reranker/混合检索
2. 增加多场景 prompt 状态机
3. 接入链路观测平台

---

## 7. 结论

当前项目已具备“可运行的 Agent + RAG 骨架”，并且结构清晰、便于迭代。团队下一阶段重点应从“功能可跑通”转向“契约一致性、可观测性、可评测性、可扩展性”，逐步推进到可持续交付的工程形态。
