import { Search, Settings2, Shield, TerminalSquare } from "lucide-react";

const policyRows = [
  {
    name: "检索摘要工具",
    tools: "rag_summarize",
    risk: "低风险",
    policy: "允许在默认智能体中使用，返回引用片段和摘要。",
  },
  {
    name: "网页检索工具",
    tools: "web_search",
    risk: "中风险",
    policy: "需要保留来源和 trace，后续应增加请求域名审计。",
  },
  {
    name: "报告上下文工具",
    tools: "fill_context_for_report",
    risk: "低风险",
    policy: "仅补全报告上下文，不执行外部副作用。",
  },
  {
    name: "代码执行工具",
    tools: "python, matlab",
    risk: "高风险",
    policy: "后续必须绑定审批、管理员权限和工具参数预览。",
  },
  {
    name: "长期记忆工具",
    tools: "store_memory, search_memory",
    risk: "中风险",
    policy: "需要区分个人记忆、知识库和可检索范围。",
  },
];

const nextSteps = [
  "在工具注册表增加风险级别、管理员要求、确认要求和允许的智能体配置。",
  "把高风险工具调用决策写入 trace，保留拒绝、允许、失败三类事件。",
  "将知识库回滚、快照等管理操作纳入同一策略视图。",
];

export function ToolsPoliciesPage() {
  return (
    <section className="space-y-5">
      <div className="panel p-5">
        <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold tracking-[0.2em] text-console-accent">
              工具与策略
            </p>
            <h1 className="mt-2 text-2xl font-semibold text-console-text">
              工具与策略
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-console-subdued">
              第一阶段先把工具治理作为独立工作台栏目呈现。当前页面只展示规划视图，不改变工具注册、授权或后端执行路径。
            </p>
          </div>
          <div className="rounded-2xl border border-console-danger/40 bg-console-danger/10 px-4 py-3 text-sm text-red-100">
            高风险工具不得仅靠提示词约束。
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_24rem]">
        <section className="panel overflow-hidden">
          <div className="border-b border-white/10 px-5 py-4">
            <div className="flex items-center gap-2 text-sm font-semibold">
              <Shield className="h-4 w-4 text-console-accent" aria-hidden="true" />
              当前工具策略草案
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[46rem] text-left text-sm">
              <thead className="bg-black/20 text-xs uppercase tracking-wider text-console-subdued">
                <tr>
                  <th className="px-5 py-3">能力</th>
                  <th className="px-5 py-3">工具</th>
                  <th className="px-5 py-3">风险</th>
                  <th className="px-5 py-3">策略</th>
                </tr>
              </thead>
              <tbody>
                {policyRows.map((row) => (
                  <tr className="border-t border-white/5" key={row.name}>
                    <td className="px-5 py-4 font-medium text-console-text">
                      {row.name}
                    </td>
                    <td className="px-5 py-4 font-mono text-xs text-console-subdued">
                      {row.tools}
                    </td>
                    <td className="px-5 py-4">
                      <span className="status-pill">{row.risk}</span>
                    </td>
                    <td className="px-5 py-4 text-console-subdued">{row.policy}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <aside className="space-y-4">
          <section className="panel p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <Settings2 className="h-4 w-4 text-console-accent" aria-hidden="true" />
              后续实现要点
            </div>
            <div className="space-y-2">
              {nextSteps.map((item) => (
                <div
                  className="rounded-2xl border border-white/10 bg-black/20 p-3 text-xs leading-5 text-console-subdued"
                  key={item}
                >
                  {item}
                </div>
              ))}
            </div>
          </section>

          <section className="panel p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <TerminalSquare className="h-4 w-4 text-console-accent" aria-hidden="true" />
              策略事件
            </div>
            <p className="text-xs leading-5 text-console-subdued">
              后续工具执行链路应写入允许、拒绝、审批、异常事件。该栏目会与运行追踪联动，但不直接展示完整工具参数。
            </p>
          </section>

          <section className="panel p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <Search className="h-4 w-4 text-console-accent" aria-hidden="true" />
              作用域
            </div>
            <p className="text-xs leading-5 text-console-subdued">
              策略应绑定到智能体配置，而不是只绑定到全局工具名，避免所有对话共享同一风险面。
            </p>
          </section>
        </aside>
      </div>
    </section>
  );
}
