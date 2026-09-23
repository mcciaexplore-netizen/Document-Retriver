"use client";
import { useEffect, useState, useRef } from "react";
import {
  Search,
  Upload,
  CheckCheck,
  ArrowRight,
  ArrowUpRight,
  X,
} from "lucide-react";
import { api, json, upload, waitForFiles } from "@/lib/api";
import { FileIcon, Loading, ErrorBox, Highlight, locationLabel } from "@/components/ui";
import { Heading } from "@/components/shared";
import type { Evidence } from "@/types";

export function QuickQueryPage({ workspace, onSource, changed, toast }: any) {
  const [maxMB, setMaxMB] = useState(25);
  const [selected, setSelected] = useState<File[]>([]);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const [q, setQ] = useState("");
  const [result, setResult] = useState<any>(null);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api("/settings")
      .then((d) => setMaxMB(d.max_upload_mb))
      .catch(() => {});
  }, []);

  function add(list: FileList | File[] | null) {
    if (!list) return;
    setError("");
    setResult(null);
    const valid: File[] = [];
    const invalid: string[] = [];
    Array.from(list).forEach((f) => {
      if (!/\.(xlsx|csv|pdf|pptx)$/i.test(f.name))
        invalid.push(`${f.name}: unsupported file type`);
      else if (f.size > maxMB * 1024 * 1024)
        invalid.push(`${f.name}: exceeds ${maxMB} MB`);
      else valid.push(f);
    });
    setSelected((old) => {
      const combined = [...old, ...valid];
      const unique = combined.filter(
        (f, index, self) =>
          index ===
          self.findIndex(
            (t) => t.name === f.name && t.size === f.size && t.lastModified === f.lastModified
          )
      );
      return unique;
    });
    if (invalid.length) setError(invalid.join("; "));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!selected.length || !q.trim() || !workspace) return;
    setBusy(true);
    setError("");
    setProgress(0);
    setResult(null);
    try {
      // 1. Upload files
      const data = await upload(selected, workspace, "replace", setProgress, "Quick Query");
      const fileIds = (data.files || []).map((f: any) => f.id);
      
      // Wait for indexing
      setProgress(99); // Indicate processing
      await waitForFiles(fileIds, workspace);

      // 2. Query search
      setProgress(100);
      const searchBody = {
        query: q,
        workspace_id: workspace,
        filters: { file_ids: fileIds },
      };
      
      const searchData = await api("/search", json(searchBody));
      setResult(searchData);
      changed(); // Trigger workspace refresh
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const results: Evidence[] = result?.results || [];

  const groupedResults = results.reduce((acc, r) => {
    const fileId = r.file.id;
    if (!acc[fileId]) acc[fileId] = { file: r.file, records: [] };
    acc[fileId].records.push(r);
    return acc;
  }, {} as Record<number, { file: any; records: Evidence[] }>);

  function renderAIResponse(text: string) {
    const parts = text.split(/(\[\d+\])/g);
    return parts.map((part, i) => {
      const match = part.match(/\[(\d+)\]/);
      if (match) {
        const index = parseInt(match[1]) - 1;
        const source = results[index];
        if (source) {
          return (
            <button key={i} type="button" onClick={() => onSource(source)} style={{ background: 'var(--primary)', color: 'white', border: 'none', borderRadius: '4px', padding: '2px 6px', margin: '0 4px', cursor: 'pointer', fontSize: '0.85em' }}>
              {part}
            </button>
          );
        }
      }
      return <span key={i}>{part}</span>;
    });
  }

  return (
    <>
      <Heading
        eyebrow="CONTEXTUAL SEARCH"
        title="Quick Query"
        description="Upload specific files and instantly search across them to find exact answers."
      />

      <form className="panel" onSubmit={submit}>
        {error && <ErrorBox message={error} />}
        
        <div
          className={`drop-zone ${drag ? "drag" : ""} ${selected.length ? "compact" : ""}`}
          onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
          onDragLeave={() => setDrag(false)}
          onDrop={(e) => { e.preventDefault(); setDrag(false); if (!busy) add(e.dataTransfer.files); }}
        >
          {selected.length === 0 ? (
            <>
              <div className="upload-glyph"><Upload size={26} /></div>
              <h3>Drop your documents here</h3>
              <p>XLSX, CSV, PDF and PPTX · Up to {maxMB} MB per file</p>
              <div>
                <button type="button" className="button primary" disabled={busy} onClick={() => input.current?.click()}>
                  Choose files
                </button>
              </div>
            </>
          ) : (
             <div className="upload-list" style={{ marginTop: 0 }}>
               {selected.map((f, i) => (
                 <div key={`${f.name}-${i}`}>
                   <FileIcon type={f.name.split(".").pop() || ""} size={18} />
                   <span>{f.name}</span>
                   <button type="button" className="icon-button" aria-label={`Remove ${f.name}`} disabled={busy} onClick={() => setSelected((old) => old.filter((_, j) => i !== j))}>
                     <X size={16} />
                   </button>
                 </div>
               ))}
               <button type="button" className="button small" disabled={busy} onClick={() => input.current?.click()}>
                 + Add more files
               </button>
             </div>
          )}
          <input type="file" ref={input} hidden multiple accept=".xlsx,.csv,.pdf,.pptx" onChange={(e) => add(e.target.files)} />
        </div>

        <div className="search-bar" style={{ marginTop: '20px' }}>
          <Search size={22} />
          <input
            aria-label="Search query"
            placeholder="What information are you looking for in these files?"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            disabled={busy}
          />
          {q && (
            <button type="button" className="icon-button" onClick={() => setQ("")} disabled={busy}>
              <X size={18} />
            </button>
          )}
          <button type="submit" className="button primary" disabled={busy || !selected.length || !q.trim()}>
            {busy ? "Processing…" : "Upload & Search"}
            <ArrowRight size={16} />
          </button>
        </div>

        {busy && (
          <div className="upload-progress" style={{ marginTop: '20px' }}>
            <div>
              <strong>
                {progress < 100
                  ? "Uploading files…"
                  : "Searching through indexed documents…"}
              </strong>
              <span>{progress}% uploaded</span>
            </div>
            <progress max={100} value={progress} />
          </div>
        )}
      </form>

      {result && !busy && (
        <div className="results-main">
          <div className="results-heading">
            <h2>
              Found {result.total_results} matches
            </h2>
            <span>in {Object.keys(groupedResults).length} document(s)</span>
          </div>

          {result.ai_response && (
            <div className="evidence-summary" style={{ borderColor: '#e1d5f2', background: '#faf6ff' }}>
              <div className="summary-body" style={{ padding: '20px' }}>
                <div style={{ width: '100%' }}>
                  <p style={{ lineHeight: '1.6', whiteSpace: 'pre-wrap', fontSize: '1.05em', color: '#2d1554', margin: 0 }}>
                    {renderAIResponse(result.ai_response)}
                  </p>
                </div>
              </div>
            </div>
          )}

          {Object.keys(groupedResults).length > 0 ? (
            Object.values(groupedResults).map((group: any) => (
              <section key={group.file.id} style={{ marginBottom: '30px', padding: '20px', background: 'var(--bg-panel)', borderRadius: '8px', border: '1px solid var(--border)' }}>
                <h3 style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '15px' }}>
                  <FileIcon type={group.file.type} size={24} />
                  Found in {group.file.type.toUpperCase()} ({group.file.name})
                </h3>
                
                {group.records.map((r: Evidence) => (
                  <article className="result-card" key={r.result_id} style={{ border: 'none', background: 'var(--bg-body)', marginBottom: '10px' }}>
                     <div className="result-top">
                       <span>{locationLabel(r.location)}</span>
                       <span className="match-score">{Math.round(r.score * 100)}% match</span>
                     </div>
                     <div className="result-content">
                       {r.value && <h3><Highlight text={String(r.value)} query={result.query} /></h3>}
                       <p><Highlight text={r.matched_text || r.content} query={result.query} /></p>
                     </div>
                     <div className="result-footer">
                       <button className="button small" onClick={() => onSource(r)}>
                         Open source <ArrowUpRight size={15} />
                       </button>
                     </div>
                  </article>
                ))}
              </section>
            ))
          ) : (
            <div className="empty" style={{ textAlign: 'center', padding: '40px' }}>
              <h3>No matching evidence found</h3>
              <p>Try different keywords or check the file contents.</p>
            </div>
          )}
        </div>
      )}
    </>
  );
}
