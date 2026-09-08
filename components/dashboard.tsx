"use client";
import { useEffect, useState } from "react";
import {
  Search,
  Files,
  Database,
  History,
  ChevronRight,
  ArrowRight,
  Upload,
  ShieldCheck,
  ArrowUpRight,
  HardDrive,
  FileCheck2,
  Activity,
  Eye,
  Link2,
  Clock3,
  FileSearch,
  ScanText,
} from "lucide-react";
import { api } from "@/lib/api";
import {
  FileIcon,
  Loading,
  Empty,
  ErrorBox,
  Badge,
  sizeLabel,
  dateLabel,
} from "@/components/ui";
import { Heading, QUICK, money } from "@/components/shared";

export function Dashboard({
  workspace,
  user,
  refresh,
  onSearch,
  onUpload,
  onFiles,
  canWrite,
}: any) {
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [q, setQ] = useState("");
  useEffect(() => {
    let live = true;
    api(`/dashboard?workspace_id=${workspace}`)
      .then((d) => {
        if (live) setData(d);
      })
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [workspace, refresh]);
  const stats = data?.stats || data || {};
  return (
    <>
      <Heading
        eyebrow="YOUR DOCUMENT INTELLIGENCE WORKSPACE"
        title={`Welcome back, ${user.name?.split(" ")[0] || "Admin"}`}
        description="A clear view of your files, evidence, and activity."
        action={
          <span className="date-tag">
            <Clock3 size={15} />
            {new Date().toLocaleDateString("en-IN", {
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </span>
        }
      />
      <section className="search-hero">
        <div className="hero-top">
          <span className="eyebrow">MCCIA ENTERPRISE DOCUMENT SEARCH</span>
          <span className="hero-secure">
            <ShieldCheck size={16} />
            PRIVATE ENTERPRISE SEARCH & AUDIT
          </span>
        </div>
        <h2>
          Find the evidence.<span> Move forward.</span>
        </h2>
        <p>
          Search company files, locate precise evidence and verify every result.
        </p>
        <form
          className="hero-search"
          onSubmit={(e) => {
            e.preventDefault();
            onSearch(q);
          }}
        >
          <Search size={23} />
          <input
            aria-label="Search enterprise files"
            placeholder="Search across your enterprise files..."
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          <kbd>ENTER ↵</kbd>
          <button className="button primary">
            Search
            <ArrowRight size={17} />
          </button>
        </form>
        <div className="quick-searches">
          <span>TRY A SEARCH</span>
          {QUICK.slice(0, 4).map((s) => (
            <button key={s} onClick={() => onSearch(s)}>
              {s}
              <ArrowUpRight size={12} />
            </button>
          ))}
        </div>
      </section>
      {error && <ErrorBox message={error} />}
      <div className="stats-grid">
        {[
          [Files, "Total files", stats.total_files],
          [FileCheck2, "Indexed files", stats.indexed_files],
          [
            Database,
            "Searchable records",
            stats.total_records ?? stats.searchable_records,
          ],
          [Search, "Searches today", stats.searches_today],
          [
            HardDrive,
            "Storage used",
            sizeLabel(stats.storage_used ?? stats.storage_bytes ?? 0),
          ],
          [
            Activity,
            "Failed jobs",
            stats.failed_jobs ?? stats.failed_processing_jobs,
          ],
        ].map(([Icon, label, value]: any) => (
          <div className="stat-card" key={label}>
            <div>
              <span>{label}</span>
              <Icon size={18} />
            </div>
            <strong>
              {data
                ? typeof value === "number"
                  ? money(value)
                  : (value ?? 0)
                : "—"}
            </strong>
            <span className="stat-caption">
              {label === "Failed jobs"
                ? value
                  ? "Needs attention"
                  : "All processing healthy"
                : label === "Storage used"
                  ? "Private local storage"
                  : label === "Searches today"
                    ? "In this workspace"
                    : "In this workspace"}
            </span>
          </div>
        ))}
      </div>
      <section className="workflow-section">
        <div className="section-heading">
          <h2>From files to verified evidence</h2>
          <span>ONE CONNECTED WORKFLOW</span>
        </div>
        <div className="workflow">
          {[
            [Upload, "Connect files", "Upload your business documents"],
            [ScanText, "Parse & index", "Preserve structure and context"],
            [Search, "Search & retrieve", "Find precise keyword matches"],
            [FileSearch, "Evidence results", "See exact source citations"],
            [ShieldCheck, "Verify & audit", "Inspect and trace every result"],
          ].map(([Icon, title, desc]: any, i) => (
            <div className="workflow-step" key={title}>
              <div className={`step-icon step-${i}`}>
                <Icon size={21} />
              </div>
              <span className="step-no">0{i + 1}</span>
              <h3>{title}</h3>
              <p>{desc}</p>
              {i < 4 && <ChevronRight className="step-arrow" size={16} />}
            </div>
          ))}
        </div>
      </section>
      {!data && !error ? (
        <Loading />
      ) : (
        <div className="dashboard-grid">
          <section className="panel">
            <div className="section-heading">
              <h2>Recent uploads</h2>
              <button className="text-button" onClick={onFiles}>
                View all files
                <ArrowRight size={15} />
              </button>
            </div>
            <div className="recent-files">
              {(data?.recent_uploads || []).slice(0, 5).map((f: any) => (
                <button className="recent-file" key={f.id} onClick={onFiles}>
                  <FileIcon type={f.file_type || f.type} />
                  <div>
                    <strong>{f.filename || f.name}</strong>
                    <span>
                      {sizeLabel(f.file_size || f.size)} ·{" "}
                      {dateLabel(f.uploaded_at || f.upload_date)}
                    </span>
                  </div>
                  <Badge status={f.processing_status || f.status} />
                  <ChevronRight size={16} />
                </button>
              ))}
              {!data?.recent_uploads?.length && (
                <Empty
                  title="Ready for your first file"
                  description="Upload a spreadsheet, PDF, or presentation."
                  action={
                    canWrite && (
                      <button className="button" onClick={onUpload}>
                        <Upload size={16} />
                        Upload files
                      </button>
                    )
                  }
                />
              )}
            </div>
          </section>
          <section className="panel">
            <div className="section-heading">
              <h2>Files by type</h2>
              <Database size={18} />
            </div>
            <TypeChart
              data={data?.files_by_type}
              total={stats.total_files || 0}
            />
          </section>
          <section className="panel">
            <div className="section-heading">
              <h2>Search activity</h2>
              <span>LAST 7 DAYS</span>
            </div>
            <ActivityChart data={data?.search_activity} />
          </section>
          <section className="panel">
            <div className="section-heading">
              <h2>Recent searches</h2>
              <History size={18} />
            </div>
            <div className="recent-searches">
              {(data?.recent_searches || [])
                .slice(0, 5)
                .map((s: any, i: number) => (
                  <button key={s.id || i} onClick={() => onSearch(s.query)}>
                    <Search size={16} />
                    <strong>{s.query || "All records"}</strong>
                    <span>
                      {s.result_count ?? s.total_results ?? ""} results
                    </span>
                    <ArrowUpRight size={15} />
                  </button>
                ))}
              {!data?.recent_searches?.length && (
                <p className="muted empty-small">
                  Your search history will appear here.
                </p>
              )}
            </div>
          </section>
          <section className="panel">
            <div className="section-heading">
              <h2>Most searched documents</h2>
              <FileSearch size={18} />
            </div>
            <RankedSources
              items={data?.most_searched_documents || data?.most_searched}
            />
          </section>
          <section className="panel">
            <div className="section-heading">
              <h2>Most accessed sources</h2>
              <Eye size={18} />
            </div>
            <RankedSources
              items={data?.most_accessed_sources || data?.most_accessed}
            />
          </section>
        </div>
      )}
      <div className="feature-grid">
        {[
          [
            Files,
            "MULTI-FORMAT SEARCH",
            "4 core file formats",
            "XLSX + CSV + PDF + PPTX",
          ],
          [
            ShieldCheck,
            "PRIVATE DEPLOYMENT",
            "Local search. Local index.",
            "Your files stay inside your infrastructure.",
          ],
          [
            Link2,
            "VERIFIABLE RESULTS",
            "Cell-level citations",
            "File, tab, row, cell, page or slide",
          ],
        ].map(([Icon, label, title, desc]: any) => (
          <div className="feature-card" key={label}>
            <Icon size={22} />
            <span>{label}</span>
            <h3>{title}</h3>
            <p>{desc}</p>
          </div>
        ))}
      </div>
    </>
  );
}

export function TypeChart({ data, total }: any) {
  const entries = Array.isArray(data)
    ? data.map((d) => [d.type || d.file_type, d.count])
    : Object.entries(data || {});
  const colors = ["#119e85", "#3e70c9", "#e99e47", "#e46e6e"];
  let offset = 0;
  const stops = entries.map(([, n]: any, i: number) => {
    const start = offset;
    offset += (Number(n) / Math.max(total, 1)) * 100;
    return `${colors[i % 4]} ${start}% ${offset}%`;
  });
  return (
    <div className="type-chart">
      <div
        className="donut"
        style={{
          background: stops.length
            ? `conic-gradient(${stops.join(",")})`
            : "#e8edf3",
        }}
      >
        <div>
          <strong>{total}</strong>
          <span>total files</span>
        </div>
      </div>
      <div className="chart-legend">
        {entries.length ? (
          entries.map(([type, n]: any, i: number) => (
            <div key={type}>
              <i style={{ background: colors[i % 4] }} />
              <span>{String(type).toUpperCase()}</span>
              <strong>{n}</strong>
            </div>
          ))
        ) : (
          <span className="muted">No files yet</span>
        )}
      </div>
    </div>
  );
}

export function ActivityChart({ data }: any) {
  const values = Array.isArray(data) ? data : [];
  const max = Math.max(1, ...values.map((d: any) => d.count || 0));
  return (
    <div className="activity-chart">
      {values.length ? (
        values.map((d: any, i: number) => (
          <div key={i}>
            <span>{d.count || 0}</span>
            <i
              style={{
                height: `${Math.max(3, ((d.count || 0) / max) * 92)}px`,
              }}
              title={`${d.date}: ${d.count} searches`}
            />
            <small>
              {new Date(d.date).toLocaleDateString("en-IN", {
                weekday: "short",
              })}
            </small>
          </div>
        ))
      ) : (
        <p className="muted">Search activity appears as your team searches.</p>
      )}
    </div>
  );
}

export function RankedSources({ items = [] }: any) {
  return (
    <div className="ranked-list">
      {items.length ? (
        items.slice(0, 4).map((s: any, i: number) => (
          <div key={i}>
            <span>{String(i + 1).padStart(2, "0")}</span>
            <strong>{s.filename || s.file_name || s.name}</strong>
            <b>{s.count || s.access_count || s.search_count || 0}</b>
          </div>
        ))
      ) : (
        <p className="muted empty-small">
          Activity will appear after you explore your files.
        </p>
      )}
    </div>
  );
}
