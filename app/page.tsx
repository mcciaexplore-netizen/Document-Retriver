"use client";
import { useEffect, useState, useCallback } from "react";
import {
  LayoutDashboard,
  Search,
  Files,
  Database,
  Layers,
  History,
  BriefcaseBusiness,
  Settings,
  LogOut,
  ChevronDown,
  ChevronRight,
  ShieldCheck,
  Plus,
  Menu,
  X,
  CheckCheck,
  LockKeyhole,
} from "lucide-react";
import { api, json } from "@/lib/api";
import { Loading, Empty } from "@/components/ui";
import type { User, Workspace, Evidence } from "@/types";
import { Logo } from "@/components/shared";
import { Dashboard } from "@/components/dashboard";
import { Login } from "@/components/login";
import { SearchPage } from "@/components/search";
import { FilesPage, UploadModal } from "@/components/files";
import { SourceViewer } from "@/components/source-viewer";
import { SourcesPage } from "@/components/sources";
import { WorkspacesPage } from "@/components/workspaces";
import { AuditPage } from "@/components/audit";
import { UseCases } from "@/components/use-cases";
import { SettingsPage } from "@/components/settings";

const NAV = [
  ["dashboard", "Dashboard", LayoutDashboard],
  ["search", "Enterprise Search", Search],
  ["files", "Files", Files],
  ["sources", "Data Sources", Database],
  ["workspaces", "Workspaces", Layers],
  ["audit", "Audit", History],
  ["cases", "Use Cases", BriefcaseBusiness],
  ["settings", "Settings", Settings],
] as const;

type Notice = { text: string; bad?: boolean };

export default function Application() {
  const [user, setUser] = useState<User | null>(null),
    [boot, setBoot] = useState(true),
    [page, setPage] = useState("dashboard"),
    [workspaces, setWorkspaces] = useState<Workspace[]>([]),
    [workspaceLoading, setWorkspaceLoading] = useState(true),
    [workspace, setWorkspace] = useState<number>(0),
    [menu, setMenu] = useState(false),
    [notice, setNotice] = useState<Notice | null>(null),
    [refresh, setRefresh] = useState(0),
    [uploadOpen, setUploadOpen] = useState(false),
    [source, setSource] = useState<Evidence | null>(null),
    [initialQuery, setInitialQuery] = useState("");
  const toast = useCallback((text: string, bad = false) => {
    setNotice({ text, bad });
  }, []);
  useEffect(() => {
    if (notice) {
      const t = setTimeout(() => setNotice(null), 6000);
      return () => clearTimeout(t);
    }
  }, [notice]);
  useEffect(() => {
    const expired = () => {
      setUser(null);
      setWorkspaces([]);
      setWorkspace(0);
      setSource(null);
      setUploadOpen(false);
      setWorkspaceLoading(true);
      setPage("dashboard");
    };
    window.addEventListener("mccia:session-expired", expired);
    return () => window.removeEventListener("mccia:session-expired", expired);
  }, []);
  useEffect(() => {
    api<User>("/auth/me")
      .then(setUser)
      .catch(() => {})
      .finally(() => setBoot(false));
  }, []);
  const loadWorkspaces = useCallback(async () => {
    try {
      const data = await api<Workspace[]>("/workspaces");
      setWorkspaces(data);
      setWorkspace((old) =>
        data.some((w) => w.id === old) ? old : data[0]?.id || 0,
      );
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setWorkspaceLoading(false);
    }
  }, [toast]);
  useEffect(() => {
    if (user) loadWorkspaces();
  }, [user, loadWorkspaces, refresh]);
  const go = (p: string) => {
    setPage(p);
    setMenu(false);
  };
  const search = (q: string) => {
    setInitialQuery(q);
    setPage("search");
  };
  const current = workspaces.find((w) => w.id === workspace);
  const canWrite =
    !!user && ["admin", "manager"].includes(user.role.toLowerCase());
  const isAdmin = user?.role.toLowerCase() === "admin";
  const changed = () => setRefresh((n) => n + 1);
  if (boot)
    return (
      <div className="boot">
        <Logo />
        <Loading label="Opening your private workspace…" />
      </div>
    );
  if (!user) return <Login onLogin={setUser} />;
  return (
    <div className="app-shell">
      {menu && <div className="mobile-shade" onClick={() => setMenu(false)} />}
      <aside className={`sidebar ${menu ? "open" : ""}`}>
        <Logo />
        <div className="workspace-switch">
          <span>YOUR WORKSPACE</span>
          <div>
            <Layers size={18} />
            <select
              aria-label="Current workspace"
              value={workspace}
              onChange={(e) => {
                setWorkspace(Number(e.target.value));
                setSource(null);
              }}
            >
              {workspaces.map((w) => (
                <option key={w.id} value={w.id}>
                  {w.name}
                </option>
              ))}
            </select>
            <ChevronDown size={15} />
          </div>
        </div>
        <nav>
          {NAV.filter(([id]) => !(id === "audit" && !canWrite)).map(
            ([id, label, Icon]) => (
              <button
                key={id}
                onClick={() => go(id)}
                className={page === id ? "active" : ""}
              >
                <Icon size={19} />
                {label}
                {page === id && <span className="nav-dot" />}
              </button>
            ),
          )}
        </nav>
        <div className="sidebar-bottom">
          <div className="private-label">
            <ShieldCheck size={19} />
            <div>
              <strong>Private by design</strong>
              <span>Inside your infrastructure</span>
            </div>
          </div>
          <div className="user-block">
            <span className="avatar">
              {user.name?.slice(0, 2).toUpperCase() || "MC"}
            </span>
            <div>
              <strong>{user.name}</strong>
              <span className="capitalize">{user.role}</span>
            </div>
            <button
              className="icon-button"
              title="Sign out"
              aria-label="Sign out"
              onClick={async () => {
                try {
                  await api("/auth/logout", json({}));
                  setUser(null);
                  setWorkspaces([]);
                  setWorkspace(0);
                  setWorkspaceLoading(true);
                  setPage("dashboard");
                } catch (e) {
                  toast((e as Error).message, true);
                }
              }}
            >
              <LogOut size={18} />
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="icon-button mobile-menu"
              onClick={() => setMenu(true)}
              aria-label="Open navigation"
            >
              <Menu />
            </button>
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>{current?.name || "MCCIA"}</strong>
            <ChevronRight size={14} />
            <span>{NAV.find((n) => n[0] === page)?.[1]}</span>
          </div>
          <div className="top-actions">
            <span className="private-pill">
              <LockKeyhole size={13} />
              Private workspace
            </span>
            {canWrite && (
              <button
                className="button primary small"
                onClick={() => setUploadOpen(true)}
              >
                <Plus size={16} />
                Upload files
              </button>
            )}
          </div>
        </header>
        <main key={`${workspace}-${page}`}>
          {workspaceLoading ? (
            <Loading label="Loading your workspaces…" />
          ) : !workspace && page !== "workspaces" && page !== "settings" ? (
            <Empty
              title={
                isAdmin
                  ? "Create your first workspace"
                  : "Workspace access needed"
              }
              description={
                isAdmin
                  ? "Give your documents a private, organized home."
                  : "Ask your administrator to assign you to a workspace, then sign in again."
              }
              action={
                isAdmin && (
                  <button
                    className="button primary"
                    onClick={() => go("workspaces")}
                  >
                    Manage workspaces
                  </button>
                )
              }
            />
          ) : page === "dashboard" ? (
            <Dashboard
              workspace={workspace}
              user={user}
              refresh={refresh}
              onSearch={search}
              onUpload={() => setUploadOpen(true)}
              onFiles={() => go("files")}
              canWrite={canWrite}
            />
          ) : page === "search" ? (
            <SearchPage
              workspace={workspace}
              initialQuery={initialQuery}
              refresh={refresh}
              onSource={setSource}
              toast={toast}
            />
          ) : page === "files" ? (
            <FilesPage
              workspace={workspace}
              refresh={refresh}
              canWrite={canWrite}
              isAdmin={isAdmin}
              onUpload={() => setUploadOpen(true)}
              changed={changed}
              toast={toast}
              onSource={setSource}
            />
          ) : page === "sources" ? (
            <SourcesPage
              canWrite={canWrite}
              onUpload={() => setUploadOpen(true)}
            />
          ) : page === "workspaces" ? (
            <WorkspacesPage
              workspaces={workspaces}
              current={workspace}
              setWorkspace={setWorkspace}
              isAdmin={isAdmin}
              changed={changed}
              toast={toast}
            />
          ) : page === "audit" ? (
            <AuditPage workspace={workspace} refresh={refresh} />
          ) : page === "cases" ? (
            <UseCases onSearch={search} />
          ) : (
            <SettingsPage user={user} toast={toast} />
          )}
        </main>
        <footer>
          <span>MCCIA Enterprise Document Search</span>
          <span>Your files. Exact evidence. Verifiable sources.</span>
        </footer>
      </div>
      <UploadModal
        open={uploadOpen}
        onClose={() => setUploadOpen(false)}
        workspace={workspace}
        workspaceName={current?.name || ""}
        changed={changed}
      />
      <SourceViewer
        result={source}
        onClose={() => setSource(null)}
        toast={toast}
      />
      {notice && (
        <div className={`toast ${notice.bad ? "bad" : ""}`} role="status">
          {notice.bad ? <X size={18} /> : <CheckCheck size={18} />}
          <span>{notice.text}</span>
          <button
            onClick={() => setNotice(null)}
            aria-label="Dismiss notification"
          >
            <X size={16} />
          </button>
        </div>
      )}
    </div>
  );
}
