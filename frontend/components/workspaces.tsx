"use client";
import { useEffect, useState, useCallback, FormEvent } from "react";
import {
  Files,
  Database,
  Layers,
  Settings,
  ArrowRight,
  Plus,
  Trash2,
  X,
  Users,
} from "lucide-react";
import { api, json } from "@/lib/api";
import { Modal, Empty, ErrorBox } from "@/components/ui";
import { Heading, money } from "@/components/shared";

export function WorkspacesPage({
  workspaces,
  current,
  setWorkspace,
  isAdmin,
  changed,
  toast,
}: any) {
  const [editing, setEditing] = useState<any>(null),
    [name, setName] = useState(""),
    [description, setDescription] = useState(""),
    [busy, setBusy] = useState(false),
    [deleting, setDeleting] = useState<any>(null),
    [error, setError] = useState(""),
    [members, setMembers] = useState<any>(null);
  function edit(w: any) {
    setEditing(w);
    setName(w.name || "");
    setDescription(w.description || "");
    setError("");
  }
  async function save(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api(
        editing.id ? `/workspaces/${editing.id}` : "/workspaces",
        json({ name, description }, editing.id ? "PATCH" : "POST"),
      );
      setEditing(null);
      changed();
      toast("Workspace saved.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function remove() {
    setBusy(true);
    setError("");
    try {
      await api(`/workspaces/${deleting.id}`, { method: "DELETE" });
      setDeleting(null);
      changed();
      toast("Workspace deleted.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        eyebrow="ORGANIZE YOUR ENTERPRISE"
        title="Workspaces"
        description="Separate teams, documents, and access with dedicated search scopes."
        action={
          isAdmin && (
            <button className="button primary" onClick={() => edit({})}>
              <Plus size={17} />
              Create workspace
            </button>
          )
        }
      />
      <div className="workspace-grid">
        {workspaces.map((w: any, i: number) => (
          <section
            className={`workspace-card ${current === w.id ? "current" : ""}`}
            key={w.id}
          >
            <div className="workspace-card-top">
              <span className={`workspace-icon color-${i % 3}`}>
                <Layers size={24} />
              </span>
              {current === w.id && (
                <span className="badge good">
                  <i />
                  Current workspace
                </span>
              )}
            </div>
            <h2>{w.name}</h2>
            <p>
              {w.description ||
                "A private space for your team’s business documents."}
            </p>
            <div className="workspace-counts">
              <span>
                <Files size={16} />
                {w.file_count || 0} files
              </span>
              <span>
                <Database size={16} />
                {money(w.record_count || 0)} records
              </span>
            </div>
            <div className="workspace-actions">
              <button
                className="text-button"
                onClick={() => {
                  setWorkspace(w.id);
                  toast(`Switched to ${w.name}.`);
                }}
              >
                {current === w.id ? "Workspace selected" : "Switch workspace"}
                <ArrowRight size={15} />
              </button>
              {isAdmin && (
                <div>
                  <button
                    className="icon-button"
                    title="Manage workspace access"
                    aria-label={`Manage access to ${w.name}`}
                    onClick={() => setMembers(w)}
                  >
                    <Users size={16} />
                  </button>
                  <button
                    className="icon-button"
                    title="Rename workspace"
                    aria-label={`Edit ${w.name}`}
                    onClick={() => edit(w)}
                  >
                    <Settings size={16} />
                  </button>
                  <button
                    className="icon-button danger"
                    title="Delete workspace"
                    aria-label={`Delete ${w.name}`}
                    onClick={() => {
                      setError("");
                      setDeleting(w);
                    }}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              )}
            </div>
          </section>
        ))}
      </div>
      {!workspaces.length && (
        <Empty
          title="Your team’s knowledge starts here"
          description={
            isAdmin
              ? "Create a workspace, then upload the first documents."
              : "Ask your administrator to assign workspace access to your account."
          }
        />
      )}
      <Modal
        open={!!editing}
        onClose={() => !busy && setEditing(null)}
        title={editing?.id ? "Edit workspace" : "Create workspace"}
      >
        <form onSubmit={save}>
          {error && <ErrorBox message={error} />}
          <label>
            Workspace name
            <input
              autoFocus
              required
              maxLength={100}
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Procurement"
            />
          </label>
          <label>
            Description
            <textarea
              maxLength={500}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What belongs in this workspace?"
            />
          </label>
          <div className="modal-actions">
            <button
              type="button"
              className="button"
              onClick={() => setEditing(null)}
            >
              Cancel
            </button>
            <button className="button primary" disabled={busy}>
              {busy ? "Saving…" : "Save workspace"}
            </button>
          </div>
        </form>
      </Modal>
      <Modal
        open={!!deleting}
        onClose={() => !busy && setDeleting(null)}
        title="Delete workspace?"
      >
        <p>
          Delete <strong>{deleting?.name}</strong>, its files, and searchable
          records? This cannot be undone.
        </p>
        {error && <ErrorBox message={error} />}
        <div className="modal-actions">
          <button className="button" onClick={() => setDeleting(null)}>
            Cancel
          </button>
          <button
            className="button danger-fill"
            onClick={remove}
            disabled={busy}
          >
            {busy ? "Deleting…" : "Delete workspace"}
          </button>
        </div>
      </Modal>
      <MembersModal
        workspace={members}
        onClose={() => setMembers(null)}
        toast={toast}
      />
    </>
  );
}

export function MembersModal({ workspace, onClose, toast }: any) {
  const [users, setUsers] = useState<any[]>([]),
    [members, setMembers] = useState<any[]>([]),
    [selected, setSelected] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const load = useCallback(async () => {
    if (!workspace) return;
    try {
      setMembers(await api(`/workspaces/${workspace.id}/members`));
      setUsers(await api("/users"));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [workspace]);
  useEffect(() => {
    setError("");
    setSelected("");
    load();
  }, [load]);
  async function update(id: number, remove = false) {
    setBusy(true);
    setError("");
    try {
      await api(
        `/workspaces/${workspace.id}/members${remove ? `/${id}` : ""}`,
        remove ? { method: "DELETE" } : json({ user_id: id }),
      );
      await load();
      toast("Workspace access updated.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Modal
      open={!!workspace}
      onClose={onClose}
      title={`Access · ${workspace?.name || ""}`}
    >
      <p className="muted">
        Administrators can access every workspace. Add managers and viewers
        below.
      </p>
      {error && <ErrorBox message={error} />}
      <div className="member-list">
        {members.map((m: any) => (
          <div key={m.user_id || m.id}>
            <span>
              <strong>{m.name || m.user?.name || m.email}</strong>
              <small>{m.email || m.user?.email}</small>
            </span>
            <button
              disabled={busy}
              className="icon-button danger"
              aria-label="Remove member"
              onClick={() => update(m.user_id || m.id, true)}
            >
              <X size={17} />
            </button>
          </div>
        ))}
      </div>
      <label>
        Add user
        <select value={selected} onChange={(e) => setSelected(e.target.value)}>
          <option value="">Choose a user</option>
          {users
            .filter(
              (u) =>
                u.role.toLowerCase() !== "admin" &&
                !members.some((m) => (m.user_id || m.id) === u.id),
            )
            .map((u) => (
              <option value={u.id} key={u.id}>
                {u.name} · {u.role}
              </option>
            ))}
        </select>
      </label>
      <div className="modal-actions">
        <button
          className="button primary"
          disabled={!selected || busy}
          onClick={() => update(Number(selected))}
        >
          Grant workspace access
        </button>
      </div>
    </Modal>
  );
}
