import { useState } from "react";
import { AppShell, type PageKey } from "./components/AppShell";
import { useAdminToken } from "./hooks/useAdminToken";
import { ChatPage } from "./pages/ChatPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { RagPage } from "./pages/RagPage";
import { TracesPage } from "./pages/TracesPage";

export default function App() {
  const [activePage, setActivePage] = useState<PageKey>("chat");
  const adminToken = useAdminToken();

  return (
    <AppShell activePage={activePage} onNavigate={setActivePage}>
      {activePage === "chat" ? <ChatPage /> : null}
      {activePage === "rag" ? <RagPage /> : null}
      {activePage === "knowledge" ? (
        <KnowledgePage
          adminToken={adminToken.token}
          adminTokenSource={adminToken.source}
          onAdminTokenChange={adminToken.setToken}
        />
      ) : null}
      {activePage === "traces" ? (
        <TracesPage
          adminToken={adminToken.token}
          adminTokenSource={adminToken.source}
          onAdminTokenChange={adminToken.setToken}
        />
      ) : null}
    </AppShell>
  );
}
