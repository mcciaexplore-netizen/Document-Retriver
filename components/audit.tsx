"use client";
import { useEffect, useState } from "react";
import { Search, ShieldCheck } from "lucide-react";
import { api } from "@/lib/api";
import {
  Loading,
  Empty,
  ErrorBox,
  Badge,
  dateLabel,
  locationLabel,
} from "@/components/ui";
import { Heading } from "@/components/shared";

export function AuditPage({ workspace, refresh }: any) {
  const [data, setData] = useState<any[] | null>(null),
    [error, setError] = useState(""),
    [q, setQ] = useState(""),
    [action, setAction] = useState("");
  useEffect(() => {
    api<any>(`/audit?workspace_id=${workspace}`)
      .then((d) => setData(Array.isArray(d) ? d : d.items || d.logs || []))
      .catch((e) => setError(e.message));
  }, [workspace, refresh]);
  const visible =
    data?.filter(
      (a) =>
        (!action || a.action === action) &&
        JSON.stringify(a).toLowerCase().includes(q.toLowerCase()),
    ) || [];
  return (
    <>
      <Heading
        eyebrow="EVERY ACTION, ACCOUNTED FOR"
        title="Audit trail"
        description="Trace searches, source views, uploads, and document changes."
        action={
          <span className="private-pill">
            <ShieldCheck size={15} />
            Server-recorded activity
          </span>
        }
      />
      <section className="panel">
        <div className="table-toolbar">
          <div className="input-with-icon">
            <Search size={17} />
            <input
              aria-label="Filter audit events"
              placeholder="Search audit events..."
              value={q}
              onChange={(e) => setQ(e.target.value)}
            />
          </div>
          <select
            aria-label="Audit action"
            value={action}
            onChange={(e) => setAction(e.target.value)}
          >
            <option value="">All actions</option>
            {Array.from(new Set(data?.map((a) => a.action) || [])).map((a) => (
              <option key={a}>{a}</option>
            ))}
          </select>
          <span>{visible.length} events</span>
        </div>
        {error ? (
          <ErrorBox message={error} />
        ) : !data ? (
          <Loading label="Loading audit events…" />
        ) : !visible.length ? (
          <Empty
            title="No audit events"
            description="Search and file activity in this workspace will appear here."
          />
        ) : (
          <div className="table-scroll">
            <table className="audit-table">
              <thead>
                <tr>
                  {[
                    "Timestamp",
                    "User",
                    "Action",
                    "Query / Details",
                    "File",
                    "Location",
                    "Status",
                  ].map((h) => (
                    <th key={h}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visible.map((a: any, i: number) => (
                  <tr key={a.id || i}>
                    <td>{dateLabel(a.timestamp || a.created_at)}</td>
                    <td>{a.user_name || a.user?.name || a.user || "System"}</td>
                    <td>
                      <span className="action-tag">{a.action}</span>
                    </td>
                    <td>
                      <span className="audit-query">
                        {a.query || a.details?.query || "—"}
                      </span>
                      {a.details && (
                        <details>
                          <summary>Event details</summary>
                          <pre>{JSON.stringify(a.details, null, 2)}</pre>
                        </details>
                      )}
                    </td>
                    <td>{a.file_name || a.filename || "—"}</td>
                    <td>
                      {typeof a.location === "string"
                        ? a.location
                        : locationLabel(a.location || {}) || "—"}
                    </td>
                    <td>
                      <Badge status={a.status || "success"} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
