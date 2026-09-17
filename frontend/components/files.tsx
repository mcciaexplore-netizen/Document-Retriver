"use client";
import { useEffect, useState, useRef } from "react";
import {
  Search,
  Upload,
  FolderOpen,
  RefreshCw,
  Download,
  Trash2,
  Eye,
  X,
  CheckCheck,
  LockKeyhole,
} from "lucide-react";
import { api, json, upload, waitForFiles } from "@/lib/api";
import {
  Modal,
  FileIcon,
  Loading,
  Empty,
  ErrorBox,
  Badge,
  sizeLabel,
  dateLabel,
} from "@/components/ui";
import { Heading, money } from "@/components/shared";

export function FilesPage({
  workspace,
  refresh,
  canWrite,
  isAdmin,
  onUpload,
  changed,
  toast,
  onSource,
}: any) {
  const [files, setFiles] = useState<any[] | null>(null),
    [error, setError] = useState(""),
    [query, setQuery] = useState(""),
    [type, setType] = useState(""),
    [pending, setPending] = useState<number | null>(null),
    [deleting, setDeleting] = useState<any>(null);
  useEffect(() => {
    let live = true;
    setError("");
    setFiles(null);
    api<any[]>(`/files?workspace_id=${workspace}`)
      .then((d) => live && setFiles(d))
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [workspace, refresh]);
  useEffect(() => {
    if (
      !files?.some((f) =>
        ["uploaded", "processing"].includes(f.processing_status),
      )
    )
      return;
    const timer = setInterval(() => {
      api<any[]>(`/files?workspace_id=${workspace}`)
        .then((data) => {
          setFiles(data);
          setError("");
        })
        .catch((e) => setError(e.message));
    }, 2000);
    return () => clearInterval(timer);
  }, [files, workspace]);
  async function action(file: any, kind: string) {
    setPending(file.id);
    try {
      if (kind === "reindex") {
        await api(`/files/${file.id}/reindex`, json({}));
        const [updated] = await waitForFiles([file.id], workspace);
        if (updated.processing_status === "failed")
          throw new Error(updated.error || "Re-indexing failed.");
        toast("Re-indexing completed.");
        changed();
      } else if (kind === "delete") {
        await api(`/files/${file.id}`, { method: "DELETE" });
        toast("File and its indexed records deleted.");
        setDeleting(null);
        changed();
      } else {
        const data = await api(`/files/${file.id}/records`);
        if (data?.length) onSource(data[0]);
        else
          toast(
            file.error || "This file has no indexed records to preview.",
            true,
          );
      }
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setPending(null);
      changed();
    }
  }
  const visible =
    files?.filter(
      (f) =>
        f.filename.toLowerCase().includes(query.toLowerCase()) &&
        (!type || f.file_type === type),
    ) || [];
  return (
    <>
      <Heading
        eyebrow="YOUR DOCUMENT LIBRARY"
        title="Files"
        description="Manage documents, monitor indexing, and inspect original sources."
        action={
          canWrite && (
            <button className="button primary" onClick={onUpload}>
              <Upload size={17} />
              Upload / Sync
            </button>
          )
        }
      />
      <div className="panel">
        <div className="table-toolbar">
          <div className="input-with-icon">
            <Search size={17} />
            <input
              aria-label="Find files"
              placeholder="Find a file..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </div>
          <select
            aria-label="File type filter"
            value={type}
            onChange={(e) => setType(e.target.value)}
          >
            <option value="">All file types</option>
            {["xlsx", "csv", "pdf", "pptx"].map((t) => (
              <option key={t}>{t}</option>
            ))}
          </select>
          <span>{visible.length} documents</span>
        </div>
        {error ? (
          <ErrorBox message={error} />
        ) : !files ? (
          <Loading />
        ) : !visible.length ? (
          <Empty
            title="No files here yet"
            description="Upload documents to start building your searchable library."
            action={
              canWrite && (
                <button className="button primary" onClick={onUpload}>
                  Upload files
                </button>
              )
            }
          />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {[
                    "File name",
                    "Type / Size",
                    "Source",
                    "Uploaded",
                    "Status",
                    "Records",
                    "Actions",
                  ].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map((f) => (
                  <tr key={f.id}>
                    <td>
                      <div className="file-name">
                        <FileIcon type={f.file_type} />
                        <div>
                          <strong>{f.filename}</strong>
                          {f.error && (
                            <span className="error-text">{f.error}</span>
                          )}
                        </div>
                      </div>
                    </td>
                    <td>
                      <span className="type-text">{f.file_type}</span>
                      <small>{sizeLabel(f.file_size)}</small>
                    </td>
                    <td className="capitalize">{f.source_type}</td>
                    <td>{dateLabel(f.uploaded_at || f.upload_date)}</td>
                    <td>
                      <Badge status={f.processing_status} />
                      {f.job?.status === "processing" && (
                        <small>{f.job.progress}%</small>
                      )}
                    </td>
                    <td>{money(f.indexed_records || 0)}</td>
                    <td>
                      <div className="row-actions">
                        <button
                          className="icon-button"
                          title="View source"
                          aria-label={`View ${f.filename}`}
                          disabled={pending === f.id}
                          onClick={() => action(f, "view")}
                        >
                          <Eye size={17} />
                        </button>
                        <a
                          className="icon-button"
                          href={`/api/files/${f.id}/download`}
                          title="Download original"
                          aria-label={`Download ${f.filename}`}
                        >
                          <Download size={17} />
                        </a>
                        {canWrite && (
                          <button
                            className="icon-button"
                            title="Re-index"
                            aria-label={`Re-index ${f.filename}`}
                            disabled={pending === f.id}
                            onClick={() => action(f, "reindex")}
                          >
                            <RefreshCw
                              size={16}
                              className={pending === f.id ? "spin" : ""}
                            />
                          </button>
                        )}
                        {isAdmin && (
                          <button
                            className="icon-button danger"
                            title="Delete"
                            aria-label={`Delete ${f.filename}`}
                            onClick={() => setDeleting(f)}
                          >
                            <Trash2 size={16} />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <Modal
        open={!!deleting}
        onClose={() => setDeleting(null)}
        title="Delete document?"
      >
        <p>
          Delete <strong>{deleting?.filename}</strong> and all of its indexed
          evidence? This cannot be undone. The deletion remains in the audit
          log.
        </p>
        <div className="modal-actions">
          <button className="button" onClick={() => setDeleting(null)}>
            Cancel
          </button>
          <button
            className="button danger-fill"
            disabled={!!pending}
            onClick={() => action(deleting, "delete")}
          >
            {pending ? "Deleting…" : "Delete document"}
          </button>
        </div>
      </Modal>
    </>
  );
}

export function UploadModal({
  open,
  onClose,
  workspace,
  workspaceName,
  changed,
}: any) {
  const [maxMB, setMaxMB] = useState(25),
    [selected, setSelected] = useState<File[]>([]),
    [busy, setBusy] = useState(false),
    [progress, setProgress] = useState(0),
    [error, setError] = useState(""),
    [result, setResult] = useState<any>(null),
    [drag, setDrag] = useState(false),
    [duplicate, setDuplicate] = useState("skip"),
    [category, setCategory] = useState("");
  const input = useRef<HTMLInputElement>(null),
    folder = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (open) {
      api("/settings")
        .then((d) => setMaxMB(d.max_upload_mb))
        .catch(() => {});
      setSelected([]);
      setResult(null);
      setError("");
      setProgress(0);
      setCategory("");
    }
  }, [open]);
  function add(list: FileList | File[] | null) {
    if (!list) return;
    setResult(null);
    setError("");
    const valid: File[] = [];
    const invalid: string[] = [];
    Array.from(list).forEach((f) => {
      if (!/\.(xlsx|csv|pdf|pptx)$/i.test(f.name))
        invalid.push(`${f.name}: unsupported file type`);
      else if (f.size > maxMB * 1024 * 1024)
        invalid.push(`${f.name}: exceeds ${maxMB} MB`);
      else valid.push(f);
    });
    setSelected((old) => [
      ...old,
      ...valid.filter(
        (f) =>
          !old.some(
            (o) =>
              o.name === f.name &&
              o.size === f.size &&
              o.lastModified === f.lastModified,
          ),
      ),
    ]);
    if (invalid.length) setError(invalid.join("; "));
  }
  async function submit() {
    setBusy(true);
    setError("");
    setProgress(0);
    try {
      const data = await upload(
        selected,
        workspace,
        duplicate,
        setProgress,
        category,
      );
      setResult({
        ...data,
        files: await waitForFiles(
          (data.files || []).map((f: any) => f.id),
          workspace,
        ),
      });
      setSelected([]);
      changed();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const results = Array.isArray(result)
    ? result
    : [
        ...(result?.files || result?.results || []),
        ...(result?.skipped || []).map((f: any) => ({
          ...f,
          status: "skipped",
          message: f.reason,
        })),
        ...(result?.errors || []).map((f: any) => ({ ...f, status: "failed" })),
      ];
  return (
    <Modal
      open={open}
      onClose={() => !busy && onClose()}
      title="Connect your files"
    >
      <p className="muted">
        Upload to <strong>{workspaceName}</strong>. Files are parsed and indexed
        inside your infrastructure.
      </p>
      <input
        type="file"
        ref={input}
        hidden
        multiple
        accept=".xlsx,.csv,.pdf,.pptx"
        onChange={(e) => add(e.target.files)}
      />
      <input
        type="file"
        ref={folder}
        hidden
        multiple
        {...({ webkitdirectory: "", directory: "" } as any)}
        onChange={(e) => add(e.target.files)}
      />
      <div
        className={`drop-zone ${drag ? "drag" : ""}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDrag(true);
        }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          if (!busy) add(e.dataTransfer.files);
        }}
      >
        <div className="upload-glyph">
          <Upload size={26} />
        </div>
        <h3>Drop your documents here</h3>
        <p>
          XLSX, CSV, PDF and PPTX · Up to {maxMB} MB per file · 30 files per
          batch
        </p>
        <div>
          <button
            className="button primary"
            disabled={busy}
            onClick={() => input.current?.click()}
          >
            Choose files
          </button>
          <button
            className="button"
            disabled={busy}
            onClick={() => folder.current?.click()}
          >
            <FolderOpen size={16} />
            Choose folder
          </button>
        </div>
      </div>
      {error && <ErrorBox message={error} />}
      {selected.length > 30 && (
        <ErrorBox message="Choose up to 30 files per upload batch. Remove files to continue." />
      )}
      <div className="upload-list">
        {selected.map((f, i) => (
          <div key={`${f.name}-${i}`}>
            <FileIcon type={f.name.split(".").pop() || ""} size={18} />
            <span>
              {f.name}
              <small>{sizeLabel(f.size)}</small>
            </span>
            <button
              className="icon-button"
              aria-label={`Remove ${f.name}`}
              disabled={busy}
              onClick={() =>
                setSelected((old) => old.filter((_, j) => i !== j))
              }
            >
              <X size={16} />
            </button>
          </div>
        ))}
      </div>
      {busy && (
        <div className="upload-progress">
          <div>
            <strong>
              {progress < 100
                ? "Uploading files…"
                : "Parsing and building the search index…"}
            </strong>
            <span>{progress}% uploaded</span>
          </div>
          <progress max={100} value={progress} />
          <p>Keep this window open while source records are prepared.</p>
        </div>
      )}
      {result && (
        <div className="upload-results">
          <h3>
            <CheckCheck size={18} />
            Upload processing complete
          </h3>
          {results.map((f: any, i: number) => (
            <div key={i}>
              <strong>{f.filename || f.name || f.file?.filename}</strong>
              <Badge status={f.processing_status || f.status || "indexed"} />
              {(f.error || f.message) && <p>{f.error || f.message}</p>}
            </div>
          ))}
          {!results.length && (
            <p>Files have been processed. Check Files for indexing status.</p>
          )}
        </div>
      )}
      <label className="duplicate-setting">
        Category (optional)
        <input
          maxLength={80}
          placeholder="e.g. Finance"
          value={category}
          disabled={busy}
          onChange={(e) => setCategory(e.target.value)}
        />
      </label>
      <label className="duplicate-setting">
        When the same file already exists
        <select
          value={duplicate}
          disabled={busy}
          onChange={(e) => setDuplicate(e.target.value)}
        >
          <option value="skip">Skip duplicate content</option>
          <option value="replace">Re-index duplicate content</option>
        </select>
      </label>
      <div className="modal-actions">
        <span className="muted">
          <LockKeyhole size={14} />
          Private file storage
        </span>
        <button className="button" disabled={busy} onClick={onClose}>
          {result ? "Done" : "Cancel"}
        </button>
        <button
          className="button primary"
          disabled={
            !selected.length || selected.length > 30 || busy || !workspace
          }
          onClick={submit}
        >
          <Upload size={16} />
          {busy
            ? "Processing…"
            : `Upload & index${selected.length ? ` (${selected.length})` : ""}`}
        </button>
      </div>
    </Modal>
  );
}
