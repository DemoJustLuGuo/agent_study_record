import { Database, Search, Settings2, Shield } from "lucide-react";

const profileCards = [
  {
    title: "通信工程师智能体",
    status: "默认配置",
    description: "承接通用无线通信、协议分析、链路预算和工程参数问答。",
    items: ["主提示词", "通用工具白名单", "默认知识库作用域"],
    icon: <Settings2 className="h-5 w-5 text-console-accent" aria-hidden="true" />,
  },
  {
    title: "检索问答智能体",
    status: "待拆分",
    description: "面向证据优先的知识库问答，要求引用片段支撑关键结论。",
    items: ["检索增强参数", "引用策略", "证据不足降级"],
    icon: <Search className="h-5 w-5 text-console-accent" aria-hidden="true" />,
  },
  {
    title: "报告生成智能体",
    status: "规划中",
    description: "复用报告提示词和上下文填充工具，输出结构化工程报告。",
    items: ["报告提示词", "上下文补全", "格式约束"],
    icon: <Database className="h-5 w-5 text-console-accent" aria-hidden="true" />,
  },
  {
    title: "安全受限智能体",
    status: "规划中",
    description: "默认禁用高风险工具，用于演示、评审和低权限问答场景。",
    items: ["禁用代码执行", "只读知识库", "最小工具集"],
    icon: <Shield className="h-5 w-5 text-console-accent" aria-hidden="true" />,
  },
];

export function AgentProfilesPage() {
  return (
    <section className="space-y-5">
      <div className="panel p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold tracking-[0.2em] text-console-accent">
              智能体配置
            </p>
            <h1 className="mt-2 text-2xl font-semibold text-console-text">
              智能体配置
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-console-subdued">
              第一阶段先建立工作台信息架构。这里用于承载后续“基础模型、提示词、工具白名单、知识库作用域、检索参数”的组合配置；当前不会写入后端配置。
            </p>
          </div>
          <span className="status-pill">阶段一：结构占位</span>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {profileCards.map((profile) => (
          <article className="panel p-5" key={profile.title}>
            <div className="flex items-start justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="rounded-2xl border border-white/10 bg-black/20 p-3">
                  {profile.icon}
                </div>
                <div>
                  <h2 className="text-base font-semibold text-console-text">
                    {profile.title}
                  </h2>
                  <p className="mt-1 text-xs text-console-subdued">
                    {profile.description}
                  </p>
                </div>
              </div>
              <span className="status-pill whitespace-nowrap">{profile.status}</span>
            </div>
            <div className="mt-4 grid gap-2 md:grid-cols-3">
              {profile.items.map((item) => (
                <div
                  className="rounded-2xl border border-white/10 bg-black/20 px-3 py-2 text-xs text-console-subdued"
                  key={item}
                >
                  {item}
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
