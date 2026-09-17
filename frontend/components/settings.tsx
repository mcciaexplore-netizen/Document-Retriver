"use client";
import { useEffect, useState, FormEvent } from "react";
import { Settings, Plus, KeyRound } from "lucide-react";
import { api, json } from "@/lib/api";
import { Modal, Loading, ErrorBox } from "@/components/ui";
import { Heading, PrivateDeployment } from "@/components/shared";

export function SettingsPage({ user, toast }: any) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [old, setOld] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [users, setUsers] = useState<any[]>([]),
    [newUser, setNewUser] = useState(false),
    [name, setName] = useState(""),
    [email, setEmail] = useState(""),
    [newPassword, setNewPassword] = useState(""),
    [role, setRole] = useState("Viewer");
  const admin = user.role.toLowerCase() === "admin";
  useEffect(() => {
    api("/settings")
      .then(setData)
      .catch((e) => setError(e.message));
    if (admin)
      api<any[]>("/users")
        .then(setUsers)
        .catch(() => {});
  }, [admin]);
  async function changePassword(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api(
        "/auth/password",
        json({ current_password: old, new_password: password }),
      );
      toast("Password updated.");
      setOld("");
      setPassword("");
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  async function createUser(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/users", json({ name, email, password: newPassword, role }));
      setNewUser(false);
      setUsers(await api("/users"));
      toast("User created. Assign workspace access from Workspaces.");
      setName("");
      setEmail("");
      setNewPassword("");
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Heading
        eyebrow="WORKSPACE ADMINISTRATION"
        title="Settings"
        description="Application configuration, account security, and access management."
      />
      {error && <ErrorBox message={error} />}
      <div className="settings-grid">
        <section className="panel settings-panel">
          <div className="section-heading">
            <h2>Application configuration</h2>
            <Settings size={19} />
          </div>
          <p className="muted">
            Deployment configuration is managed through environment variables.
          </p>
          {!data ? (
            <Loading />
          ) : (
            <dl>
              {[
                [
                  "Max upload size",
                  `${data.max_upload_size_mb ?? data.max_upload_mb ?? 25} MB per file`,
                ],
                [
                  "Allowed file types",
                  (data.allowed_file_types || ["xlsx", "csv", "pdf", "pptx"])
                    .join(", ")
                    .toUpperCase(),
                ],
                [
                  "Auto index on upload",
                  data.auto_index_on_upload === false ? "Disabled" : "Enabled",
                ],
                [
                  "Storage location",
                  data.storage_location ||
                    data.storage_dir ||
                    "Private local storage",
                ],
                ["Search result limit", data.search_result_limit || 100],
                [
                  "Audit retention",
                  `${data.audit_retention_days || 365} days (archival policy)`,
                ],
              ].map(([k, v]) => (
                <div key={String(k)}>
                  <dt>{k}</dt>
                  <dd>{v}</dd>
                </div>
              ))}
            </dl>
          )}
        </section>
        <section className="panel settings-panel">
          <div className="section-heading">
            <h2>Account security</h2>
            <KeyRound size={19} />
          </div>
          <p className="muted">Signed in as {user.email}</p>
          <form onSubmit={changePassword}>
            <label>
              Current password
              <input
                required
                type="password"
                autoComplete="current-password"
                value={old}
                onChange={(e) => setOld(e.target.value)}
              />
            </label>
            <label>
              New password
              <input
                required
                minLength={10}
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="At least 10 characters"
              />
            </label>
            <button className="button primary" disabled={busy}>
              {busy ? "Updating…" : "Update password"}
            </button>
          </form>
        </section>
      </div>
      {admin && (
        <section className="panel user-management">
          <div className="section-heading">
            <h2>User management</h2>
            <button className="button small" onClick={() => setNewUser(true)}>
              <Plus size={16} />
              Add user
            </button>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Name</th>
                  <th>Email</th>
                  <th>Role</th>
                  <th>Access</th>
                </tr>
              </thead>
              <tbody>
                {users.map((u) => (
                  <tr key={u.id}>
                    <td>{u.name}</td>
                    <td>{u.email}</td>
                    <td className="capitalize">{u.role}</td>
                    <td>
                      {u.role.toLowerCase() === "admin"
                        ? "All workspaces"
                        : "Assigned workspaces"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      <PrivateDeployment />
      <Modal
        open={newUser}
        onClose={() => !busy && setNewUser(false)}
        title="Create user"
      >
        <form onSubmit={createUser}>
          <label>
            Full name
            <input
              required
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </label>
          <label>
            Email
            <input
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <label>
            Initial password
            <input
              type="password"
              minLength={10}
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
            />
          </label>
          <label>
            Role
            <select value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="Viewer">Viewer · search and view sources</option>
              <option value="Manager">
                Manager · upload, search, and audit
              </option>
              <option value="Admin">Admin · full access</option>
            </select>
          </label>
          <div className="modal-actions">
            <button className="button primary" disabled={busy}>
              {busy ? "Creating…" : "Create user"}
            </button>
          </div>
        </form>
      </Modal>
    </>
  );
}
