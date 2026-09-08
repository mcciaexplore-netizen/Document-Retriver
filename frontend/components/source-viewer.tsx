"use client";
import { useEffect, useState } from "react";
import { ShieldCheck, Download, Copy, Link2 } from "lucide-react";
import { api } from "@/lib/api";
import {
  Modal,
  FileIcon,
  Loading,
  ErrorBox,
  locationLabel,
} from "@/components/ui";

export function SourceViewer({ result, onClose, toast }: any) {
  const [source, setSource] = useState<any>(null),
    [error, setError] = useState("");
  useEffect(() => {
    setSource(null);
    setError("");
    if (result) {
      let live = true;
      api(
        `/records/${result.result_id}/source${result.record_version ? `?version=${encodeURIComponent(result.record_version)}` : ""}`,
      )
        .then((s) => live && setSource(s))
        .catch((e) => live && setError(e.message));
      return () => {
        live = false;
      };
    }
  }, [result]);
  const loc = source?.location || result?.location || {};
  return (
    <Modal
      drawer
      open={!!result}
      onClose={onClose}
      title="Verify original evidence"
    >
      {result && (
        <>
          <div className="source-file">
            <FileIcon type={result.file.type} />
            <div>
              <h3>{result.file.name}</h3>
              <p>{locationLabel(loc)}</p>
            </div>
            <a
              className="button small"
              href={
                source && !error
                  ? `/api/files/${source.file.id}/download`
                  : undefined
              }
              aria-disabled={!source || !!error}
            >
              <Download size={15} />
              Original
            </a>
          </div>
          <div className="citation-box">
            <span>
              <Link2 size={15} />
              EXACT SOURCE CITATION
            </span>
            <p>
              {source?.citation?.text ||
                result.citation?.text ||
                `${result.file.name} → ${locationLabel(loc)}`}
            </p>
            <button
              className="icon-button"
              aria-label="Copy citation"
              title="Copy citation"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(
                    source?.citation?.text ||
                      result.citation?.text ||
                      `${result.file.name} → ${locationLabel(loc)}`,
                  );
                  toast("Citation copied.");
                } catch {
                  toast("Clipboard is unavailable in this browser.", true);
                }
              }}
            >
              <Copy size={17} />
            </button>
          </div>
          {error ? (
            <ErrorBox message={error} />
          ) : !source ? (
            <Loading label="Opening the cited source…" />
          ) : (
            <>
              <div className="source-section-heading">
                <h3>
                  {["xlsx", "csv"].includes(result.file.type)
                    ? "Spreadsheet context"
                    : result.file.type === "pdf"
                      ? "Original PDF page"
                      : "Extracted slide content"}
                </h3>
                <span className="badge good">
                  <i />
                  Source verified
                </span>
              </div>
              {["xlsx", "csv"].includes(result.file.type) ? (
                <>
                  <div className="table-scroll source-table">
                    <table>
                      <thead>
                        <tr>
                          <th>Row</th>
                          {source.headers?.map((h: any, i: number) => (
                            <th key={i}>
                              {h.key}
                              <small>{h.label}</small>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {source.rows?.map((r: any) => (
                          <tr key={r.row_number}>
                            <th>{r.row_number}</th>
                            {r.cells.map((c: any, i: number) => (
                              <td
                                key={i}
                                className={c.matched ? "matched-cell" : ""}
                                title={
                                  c.formula
                                    ? `Formula: ${c.formula}`
                                    : c.coordinate
                                }
                              >
                                {c.value || "—"}
                                {c.matched && <span>{c.coordinate}</span>}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="source-note">
                    <span className="matched-dot" />
                    The cited cell is highlighted. Surrounding rows are shown
                    for context.
                  </p>
                  {source.record?.metadata?.formula && (
                    <p className="formula">
                      Formula: {source.record.metadata.formula}
                    </p>
                  )}
                </>
              ) : result.file.type === "pdf" ? (
                <>
                  <div className="pdf-page">
                    {source.page?.image_url ? (
                      <img
                        src={source.page.image_url}
                        alt={`Page ${loc.page} from ${result.file.name}`}
                      />
                    ) : (
                      <iframe
                        title="Original PDF source"
                        src={`/api/files/${result.file.id}/download?inline=true#page=${loc.page || 1}`}
                      />
                    )}
                  </div>
                  <div className="source-text">
                    <span className="eyebrow">EXTRACTED PAGE TEXT</span>
                    <p>{source.page?.text || source.record?.content}</p>
                  </div>
                </>
              ) : (
                <div className="slide-preview">
                  <span className="eyebrow">SLIDE {loc.slide}</span>
                  <h2>{source.slide?.title}</h2>
                  <p>{source.slide?.content}</p>
                  {source.slide?.notes && (
                    <div className="slide-notes">
                      <h4>Speaker notes</h4>
                      <p>{source.slide.notes}</p>
                    </div>
                  )}
                </div>
              )}
              <div className="source-audit">
                <ShieldCheck size={18} />
                <div>
                  <strong>This source view is recorded.</strong>
                  <span>
                    File, location, user, and timestamp are saved in your audit
                    history.
                  </span>
                </div>
              </div>
            </>
          )}
        </>
      )}
    </Modal>
  );
}
