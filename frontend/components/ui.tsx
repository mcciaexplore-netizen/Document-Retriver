"use client";
import * as Dialog from "@radix-ui/react-dialog";
import {
  X,
  LoaderCircle,
  FileSpreadsheet,
  FileText,
  Presentation,
  FolderOpen,
  AlertCircle,
} from "lucide-react";
export function Modal({
  open,
  onClose,
  title,
  children,
  drawer = false,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  drawer?: boolean;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(v) => !v && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="overlay" />
        <Dialog.Content
          className={drawer ? "modal drawer" : "modal"}
          aria-describedby={undefined}
        >
          <div className="modal-heading">
            <Dialog.Title>{title}</Dialog.Title>
            <Dialog.Close className="icon-button" aria-label="Close">
              <X size={20} />
            </Dialog.Close>
          </div>
          {children}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function FileIcon({ type, size = 22 }: { type: string; size?: number }) {
  const Icon =
    type === "xlsx" || type === "csv"
      ? FileSpreadsheet
      : type === "pptx"
        ? Presentation
        : FileText;
  return (
    <span className={`file-icon ${type}`}>
      <Icon size={size} />
    </span>
  );
}
export function Loading({ label = "Loading workspace…" }: { label?: string }) {
  return (
    <div className="loading">
      <LoaderCircle size={23} className="spin" />
      <span>{label}</span>
    </div>
  );
}
export function Empty({
  title,
  description,
  action,
}: {
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="empty">
      <FolderOpen size={34} />
      <h3>{title}</h3>
      <p>{description}</p>
      {action}
    </div>
  );
}
export function ErrorBox({ message }: { message: string }) {
  return (
    <div role="alert" className="error">
      <AlertCircle size={18} />
      <span>{message}</span>
    </div>
  );
}
export function Badge({ status }: { status: string }) {
  return (
    <span
      className={`badge ${["indexed", "success", "connected", "active"].includes(status?.toLowerCase()) ? "good" : status?.toLowerCase() === "failed" ? "bad" : "neutral"}`}
    >
      <i />
      {status}
    </span>
  );
}
export function sizeLabel(n = 0) {
  return n > 1048576
    ? `${(n / 1048576).toFixed(1)} MB`
    : n > 1024
      ? `${(n / 1024).toFixed(1)} KB`
      : `${n} B`;
}
export function dateLabel(s?: string) {
  return s
    ? new Date(s.endsWith("Z") || s.includes("+") ? s : s + "Z").toLocaleString(
        "en-IN",
        {
          day: "2-digit",
          month: "short",
          year: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        },
      )
    : "—";
}
export function locationLabel(l: Record<string, any> = {}) {
  return [
    l.sheet || l.sheet_name,
    l.cell || l.cell_coordinate,
    l.row && !l.cell ? `Row ${l.row}` : null,
    l.column && !l.cell ? `Column ${l.column}` : null,
    l.page ? `Page ${l.page}` : null,
    l.paragraph ? `Paragraph ${l.paragraph}` : null,
    l.slide ? `Slide ${l.slide}` : null,
    l.block ? `Block ${l.block}` : null,
  ]
    .filter(Boolean)
    .join(" / ");
}
export function Highlight({
  text = "",
  query = "",
}: {
  text: string;
  query: string;
}) {
  const words =
    query
      .match(/[\p{L}\p{N}-]+/gu)
      ?.filter((w) => !["AND", "OR", "NOT"].includes(w)) || [];
  if (!words.length) return <>{text}</>;
  const regex = new RegExp(
    `(${words.map((w) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`,
    "gi",
  );
  return (
    <>
      {String(text)
        .split(regex)
        .map((part, i) => (i % 2 ? <mark key={i}>{part}</mark> : part))}
    </>
  );
}
