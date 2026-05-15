import {
  Database,
  MessageSquareText,
  RadioTower,
  Search,
  TerminalSquare,
} from "lucide-react";
import type { ReactNode } from "react";
import { StatusBar } from "./StatusBar";

export type PageKey = "chat" | "rag" | "knowledge" | "traces";

const navItems: { key: PageKey; label: string; icon: ReactNode }[] = [
  { key: "chat", label: "Chat", icon: <MessageSquareText className="h-4 w-4" /> },
  { key: "rag", label: "RAG", icon: <Search className="h-4 w-4" /> },
  { key: "knowledge", label: "Knowledge", icon: <Database className="h-4 w-4" /> },
  { key: "traces", label: "Traces", icon: <TerminalSquare className="h-4 w-4" /> },
];

type AppShellProps = {
  activePage: PageKey;
  children: ReactNode;
  onNavigate: (page: PageKey) => void;
};

export function AppShell({ activePage, children, onNavigate }: AppShellProps) {
  return (
    <div className="min-h-screen bg-console-bg text-console-text">
      <StatusBar />
      <div className="grid min-h-[calc(100vh-4.5rem)] grid-cols-1 md:grid-cols-[15rem_minmax(0,1fr)]">
        <aside className="border-b border-console-border bg-console-surface/70 p-3 md:border-b-0 md:border-r">
          <div className="mb-4 flex items-center gap-2 px-2 text-sm font-semibold text-console-text">
            <RadioTower className="h-5 w-5 text-console-accent" aria-hidden="true" />
            Agent Console
          </div>
          <nav className="grid grid-cols-2 gap-2 md:grid-cols-1" aria-label="主导航">
            {navItems.map((item) => (
              <button
                key={item.key}
                className={`nav-button ${
                  activePage === item.key ? "nav-button-active" : ""
                }`}
                onClick={() => onNavigate(item.key)}
                type="button"
              >
                {item.icon}
                <span>{item.label}</span>
              </button>
            ))}
          </nav>
        </aside>
        <main className="min-w-0 p-4 md:p-6">{children}</main>
      </div>
    </div>
  );
}
