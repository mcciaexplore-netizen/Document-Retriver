"use client";
import {
  Plus,
  FolderOpen,
  ArrowUpRight,
  LockKeyhole,
  Network,
} from "lucide-react";
import { FileIcon, Badge } from "@/components/ui";
import { Heading, PrivateDeployment } from "@/components/shared";

export function SourcesPage({ canWrite, onUpload }: any) {
  return (
    <>
      <Heading
        eyebrow="CONNECTED KNOWLEDGE"
        title="Data Sources"
        description="One search experience. Every business file, precisely indexed."
        action={
          canWrite && (
            <button className="button primary" onClick={onUpload}>
              <Plus size={17} />
              Connect files
            </button>
          )
        }
      />
      <section className="panel">
        <div className="table-scroll">
          <table className="sources-table">
            <thead>
              <tr>
                {[
                  "Source",
                  "Data coverage",
                  "Citation precision",
                  "Indexing",
                  "Access",
                  "Status",
                  "Actions",
                ].map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[
                [
                  "xlsx",
                  "Excel & CSV",
                  "Rows, columns, formulas and values",
                  "File → Sheet → Row → Cell",
                  "On upload / re-index",
                  "Private",
                  "Available",
                ],
                [
                  "pdf",
                  "PDF Documents",
                  "Text, paragraphs and pages",
                  "File → Page → Paragraph",
                  "On upload / re-index",
                  "Private",
                  "Available",
                ],
                [
                  "pptx",
                  "PowerPoint Decks",
                  "Slides, titles, text, tables, notes",
                  "File → Slide → Text block",
                  "On upload / re-index",
                  "Private",
                  "Available",
                ],
                [
                  "drive",
                  "Google Drive",
                  "Enterprise folders via an optional connector",
                  "File → Link → Location",
                  "Connector required",
                  "Not connected",
                  "Planned",
                ],
                [
                  "folder",
                  "Local / Network Folders",
                  "Browser-selected folder imports",
                  "File → Source location",
                  "Manual import",
                  "Private",
                  "Import available",
                ],
              ].map(
                ([
                  type,
                  name,
                  coverage,
                  citation,
                  indexing,
                  access,
                  status,
                ]) => (
                  <tr key={name}>
                    <td>
                      <div className="file-name">
                        {type === "drive" || type === "folder" ? (
                          <span className="file-icon folder">
                            <FolderOpen size={22} />
                          </span>
                        ) : (
                          <FileIcon type={type} />
                        )}
                        <strong>{name}</strong>
                      </div>
                    </td>
                    <td>{coverage}</td>
                    <td>{citation}</td>
                    <td>{indexing}</td>
                    <td>
                      <LockKeyhole size={13} /> {access}
                    </td>
                    <td>
                      <Badge status={status} />
                    </td>
                    <td>
                      {type === "drive" ? (
                        <span className="muted">Not configured</span>
                      ) : canWrite ? (
                        <button className="text-button" onClick={onUpload}>
                          Import
                          <ArrowUpRight size={14} />
                        </button>
                      ) : (
                        <span className="muted">View only</span>
                      )}
                    </td>
                  </tr>
                ),
              )}
            </tbody>
          </table>
        </div>
      </section>
      <div className="info-card">
        <Network size={25} />
        <div>
          <h3>Folder import, with a path to sync</h3>
          <p>
            Choose a local or mounted network folder in Upload / Sync. Supported
            documents are imported together. Continuous folder monitoring and
            Google Drive OAuth are optional deployment integrations and are not
            connected in this installation.
          </p>
        </div>
      </div>
      <PrivateDeployment />
    </>
  );
}
