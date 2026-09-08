"use client";
import { useEffect, useState, useCallback, useRef } from "react";
import {
  Search,
  History,
  ChevronRight,
  ArrowRight,
  ArrowUpRight,
  Download,
  SlidersHorizontal,
  X,
  Link2,
  CheckCheck,
  FileSearch,
} from "lucide-react";
import { api, json, downloadBlob } from "@/lib/api";
import {
  FileIcon,
  Empty,
  ErrorBox,
  dateLabel,
  locationLabel,
  Highlight,
} from "@/components/ui";
import type { Evidence } from "@/types";
import { Heading, QUICK } from "@/components/shared";

export function SearchPage({
  workspace,
  initialQuery,
  refresh,
  onSource,
  toast,
}: any) {
  const [q, setQ] = useState(initialQuery),
    [filters, setFilters] = useState<Record<string, string>>({}),
    [files, setFiles] = useState<any[]>([]),
    [result, setResult] = useState<any>(null),
    [history, setHistory] = useState<any[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [showFilters, setShowFilters] = useState(true),
    [exporting, setExporting] = useState(false);
  const request = useRef(0);
  const lastRequest = useRef<any>(null);
  useEffect(() => {
    api<any[]>(`/files?workspace_id=${workspace}`)
      .then(setFiles)
      .catch(() => {});
    api<any[]>(`/search/history?workspace_id=${workspace}`)
      .then(setHistory)
      .catch(() => {});
  }, [workspace, refresh]);
  const run = useCallback(
    async (query: string, f: Record<string, string>) => {
      const id = ++request.current;
      setBusy(true);
      setError("");
      const body = {
        query,
        workspace_id: workspace,
        filters: Object.fromEntries(
          Object.entries(f).filter(([, v]) => v !== ""),
        ),
      };
      try {
        const data = await api("/search", json(body));
        if (id === request.current) {
          setResult(data);
          lastRequest.current = body;
          api<any[]>(`/search/history?workspace_id=${workspace}`)
            .then(setHistory)
            .catch(() => {});
        }
      } catch (e) {
        if (id === request.current) {
          setError((e as Error).message);
          setResult(null);
        }
      } finally {
        if (id === request.current) setBusy(false);
      }
    },
    [workspace],
  );
  useEffect(() => {
    if (initialQuery) run(initialQuery, {});
  }, [initialQuery, run]);
  const field = (name: string, value: string) =>
    setFilters((f) => ({ ...f, [name]: value }));
  const results: Evidence[] = result?.results || [];
  async function exportResults() {
    if (!lastRequest.current) return;
    setExporting(true);
    try {
      const r = await fetch("/api/search/export", {
        ...json(lastRequest.current),
        credentials: "include",
        headers: { "Content-Type": "application/json" },
      });
      if (!r.ok) throw new Error("Export failed. Please try again.");
      downloadBlob(await r.blob(), "mccia-evidence.csv");
      toast("Evidence results exported; event recorded in audit.");
    } catch (e) {
      toast((e as Error).message, true);
    } finally {
      setExporting(false);
    }
  }
  return (
    <>
      <Heading
        eyebrow="EXACT EVIDENCE. VERIFIABLE SOURCES."
        title="Enterprise Search"
        description="Find the right information across every document in your workspace."
      />
      <form
        className="search-bar"
        onSubmit={(e) => {
          e.preventDefault();
          run(q, filters);
        }}
      >
        <Search size={22} />
        <input
          aria-label="Search query"
          placeholder="Search across your enterprise files..."
          value={q}
          onChange={(e) => setQ(e.target.value)}
        />
        {q && (
          <button
            type="button"
            className="icon-button"
            aria-label="Clear query"
            onClick={() => setQ("")}
          >
            <X size={18} />
          </button>
        )}
        <button className="button primary" disabled={busy}>
          {busy ? "Searching…" : "Search"}
          <ArrowRight size={16} />
        </button>
      </form>
      <div className="search-toolbar">
        <button
          className={`button small ${showFilters ? "selected" : ""}`}
          onClick={() => setShowFilters((v) => !v)}
        >
          <SlidersHorizontal size={16} />
          Filters
          {Object.values(filters).filter(Boolean).length > 0 && (
            <b>{Object.values(filters).filter(Boolean).length}</b>
          )}
        </button>
        <span>
          Keywords · "exact phrases" · AND / OR / NOT · numeric ranges
        </span>
        {result && (
          <button
            className="button small export"
            onClick={exportResults}
            disabled={exporting || busy || !results.length}
          >
            <Download size={16} />
            {exporting ? "Exporting…" : "Export CSV"}
          </button>
        )}
      </div>
      <div className={`search-layout ${showFilters ? "" : "no-filters"}`}>
        {showFilters && (
          <aside className="filter-panel">
            <div className="section-heading">
              <h3>Narrow your search</h3>
              <button
                className="text-button"
                onClick={() => {
                  setFilters({});
                  if (result) run(q, {});
                }}
              >
                Clear
              </button>
            </div>
            <label>
              File type
              <select
                value={filters.file_type || ""}
                onChange={(e) => field("file_type", e.target.value)}
              >
                <option value="">All file types</option>
                {["xlsx", "csv", "pdf", "pptx"].map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </label>
            <label>
              File
              <select
                value={filters.file_id || ""}
                onChange={(e) => field("file_id", e.target.value)}
              >
                <option value="">All documents</option>
                {files.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.filename}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Sheet
              <input
                placeholder="e.g. West Region"
                value={filters.sheet || ""}
                onChange={(e) => field("sheet", e.target.value)}
              />
            </label>
            <div className="form-two">
              <label>
                Page
                <input
                  type="number"
                  min="1"
                  value={filters.page || ""}
                  onChange={(e) => field("page", e.target.value)}
                />
              </label>
              <label>
                Slide
                <input
                  type="number"
                  min="1"
                  value={filters.slide || ""}
                  onChange={(e) => field("slide", e.target.value)}
                />
              </label>
            </div>
            <label>
              Source
              <select
                value={filters.source || ""}
                onChange={(e) => field("source", e.target.value)}
              >
                <option value="">All sources</option>
                <option value="upload">File upload</option>
                <option value="local_folder">Folder import</option>
                <option value="demo">Demo files</option>
              </select>
            </label>
            <label>
              Uploaded from
              <input
                type="date"
                value={filters.date_from || ""}
                onChange={(e) => field("date_from", e.target.value)}
              />
            </label>
            <label>
              Uploaded to
              <input
                type="date"
                value={filters.date_to || ""}
                onChange={(e) => field("date_to", e.target.value)}
              />
            </label>
            <div className="form-two">
              <label>
                Amount min
                <input
                  type="number"
                  step="any"
                  placeholder="0"
                  value={filters.amount_min || ""}
                  onChange={(e) => field("amount_min", e.target.value)}
                />
              </label>
              <label>
                Amount max
                <input
                  type="number"
                  step="any"
                  placeholder="Any"
                  value={filters.amount_max || ""}
                  onChange={(e) => field("amount_max", e.target.value)}
                />
              </label>
            </div>
            <label>
              Column / header
              <input
                placeholder="e.g. Total Spending"
                value={filters.header || ""}
                onChange={(e) => field("header", e.target.value)}
              />
            </label>
            <label>
              Category
              <input
                placeholder="e.g. Finance"
                value={filters.category || ""}
                onChange={(e) => field("category", e.target.value)}
              />
            </label>
            <label>
              Keyword
              <input
                value={filters.keyword || ""}
                onChange={(e) => field("keyword", e.target.value)}
                placeholder="Additional keyword"
              />
            </label>
            <label>
              Status
              <select
                value={filters.status || ""}
                onChange={(e) => field("status", e.target.value)}
              >
                <option value="">All indexed evidence</option>
                <option value="indexed">Indexed</option>
              </select>
            </label>
            <button
              className="button primary"
              disabled={busy}
              onClick={() => run(q, filters)}
            >
              Apply filters
            </button>
          </aside>
        )}
        <div className="results-main">
          {error && <ErrorBox message={error} />}{" "}
          {busy ? (
            <div aria-busy="true">
              <div className="skeleton summary-skeleton" />
              {[0, 1, 2].map((i) => (
                <div key={i} className="skeleton result-skeleton" />
              ))}
            </div>
          ) : result ? (
            <>
              {results.length > 0 && (
                <section className="evidence-summary">
                  <div className="summary-heading">
                    <span>
                      <CheckCheck size={18} />
                      Evidence Summary
                    </span>
                    <span>FROM INDEXED SOURCE RECORDS</span>
                  </div>
                  <div className="summary-body">
                    <div>
                      <span className="eyebrow">PRIMARY MATCH</span>
                      <h2>{results[0].value || results[0].matched_text}</h2>
                      <p>
                        <FileIcon type={results[0].file.type} size={16} />
                        {results[0].file.name}
                        <ChevronRight size={14} />
                        {locationLabel(results[0].location)}
                      </p>
                    </div>
                    <div className="summary-additional">
                      <strong>{Math.max(0, result.total_results - 1)}</strong>
                      <span>additional matches</span>
                      <button
                        className="text-button"
                        onClick={() => onSource(results[0])}
                      >
                        Verify source
                        <ArrowUpRight size={14} />
                      </button>
                    </div>
                  </div>
                </section>
              )}
              <div className="results-heading">
                <h2>
                  Evidence results <span>{result.total_results}</span>
                </h2>
                <span>
                  Ranked by relevance
                  {result.total_results > results.length
                    ? ` · showing ${results.length}`
                    : ""}
                </span>
              </div>
              {results.length ? (
                results.map((r) => (
                  <article className="result-card" key={r.result_id}>
                    <div className="result-top">
                      <FileIcon type={r.file.type} />
                      <div>
                        <strong>{r.file.name}</strong>
                        <span>{locationLabel(r.location)}</span>
                      </div>
                      <span className="match-score">
                        {Math.round(r.score * 100)}% match
                      </span>
                    </div>
                    <div className="result-content">
                      {r.value && (
                        <h3>
                          <Highlight
                            text={String(r.value)}
                            query={result.query}
                          />
                        </h3>
                      )}
                      <p>
                        <Highlight
                          text={r.matched_text || r.content}
                          query={result.query}
                        />
                      </p>
                    </div>
                    <div className="result-footer">
                      <span>
                        <Link2 size={14} />
                        {r.file.type.toUpperCase()} ·{" "}
                        {locationLabel(r.location)}
                        {(r.source_timestamp || r.uploaded_at) && (
                          <small>
                            {" "}
                            · Modified{" "}
                            {dateLabel(r.source_timestamp || r.uploaded_at)}
                          </small>
                        )}
                      </span>
                      <button
                        className="button small"
                        onClick={() => onSource(r)}
                      >
                        Open source
                        <ArrowUpRight size={15} />
                      </button>
                    </div>
                  </article>
                ))
              ) : (
                <Empty
                  title="No matching evidence"
                  description="Try fewer keywords, check an exact ID, or broaden your filters."
                  action={
                    <button
                      className="button"
                      onClick={() => {
                        setFilters({});
                        setQ("");
                        run("", {});
                      }}
                    >
                      Browse all indexed records
                    </button>
                  }
                />
              )}
            </>
          ) : (
            <div className="search-start">
              <div className="search-start-icon">
                <FileSearch size={38} />
              </div>
              <h2>Your next answer starts with a source.</h2>
              <p>
                Search a phrase, purchase order, amount, or document name.
                <br />
                Every match leads back to the original evidence.
              </p>
              <div className="suggestion-grid">
                {QUICK.map((s) => (
                  <button
                    key={s}
                    onClick={() => {
                      setQ(s);
                      run(s, filters);
                    }}
                  >
                    <Search size={16} />
                    {s}
                    <ArrowUpRight size={15} />
                  </button>
                ))}
              </div>
              {history.length > 0 && (
                <div className="history-list">
                  <h3>Recent searches</h3>
                  {history.slice(0, 6).map((h: any, i: number) => (
                    <button
                      key={i}
                      onClick={() => {
                        setQ(h.query);
                        setFilters(h.filters || {});
                        run(h.query, h.filters || {});
                      }}
                    >
                      <History size={15} />
                      {h.query || "All records"}
                      <span>{dateLabel(h.created_at || h.timestamp)}</span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
