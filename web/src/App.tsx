import { useEffect, useState } from "react";
import { AdminShell } from "./components/AdminShell";
import { TokenGate } from "./components/TokenGate";
import { useAdminToken } from "./hooks/useAdminToken";
import { ChatPage } from "./pages/ChatPage";
import { AgentProfilesPage } from "./pages/AgentProfilesPage";
import { KnowledgePage } from "./pages/KnowledgePage";
import { RagPage } from "./pages/RagPage";
import { ToolsPoliciesPage } from "./pages/ToolsPoliciesPage";
import { TracesPage } from "./pages/TracesPage";

export default function App() {
  const [pathname, setPathname] = useState(window.location.pathname);
  const adminToken = useAdminToken();

  useEffect(() => {
    const handlePopState = () => setPathname(window.location.pathname);
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, []);

  if (pathname === "/" || pathname === "/chat") {
    return (
      <AdminShell activePath="/chat" showAdminControls={false}>
        <ChatPage />
      </AdminShell>
    );
  }

  if (pathname.startsWith("/admin")) {
    const rawAdminPath = pathname === "/admin" ? "/admin/profiles" : pathname;
    const adminPath =
      rawAdminPath === "/admin/rag" ? "/admin/settings" : rawAdminPath;
    return (
      <TokenGate>
        <AdminShell activePath={adminPath}>
          {adminPath === "/admin/profiles" && <AgentProfilesPage />}
          {adminPath === "/admin/knowledge" && (
            <KnowledgePage
              adminToken={adminToken.token}
              adminTokenSource={adminToken.source}
              onAdminTokenChange={adminToken.setToken}
            />
          )}
          {adminPath === "/admin/tools" && <ToolsPoliciesPage />}
          {adminPath === "/admin/traces" && (
            <TracesPage
              adminToken={adminToken.token}
              adminTokenSource={adminToken.source}
              onAdminTokenChange={adminToken.setToken}
            />
          )}
          {adminPath === "/admin/settings" && (
            <RagPage
              adminToken={adminToken.token}
              adminTokenSource={adminToken.source}
              onAdminTokenChange={adminToken.setToken}
            />
          )}
        </AdminShell>
      </TokenGate>
    );
  }

  return <div>Not Found</div>;
}
