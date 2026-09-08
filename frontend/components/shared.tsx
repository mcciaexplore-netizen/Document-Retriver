"use client";
import { ShieldCheck, Check } from "lucide-react";

export function Logo() {
  return (
    <div className="brand">
      <img
        src="/mccia-logo.png"
        alt="MCCIA — Mahratta Chamber of Commerce, Industries and Agriculture"
      />
      <span>ENTERPRISE DOCUMENT SEARCH</span>
    </div>
  );
}

export function Heading({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow?: string;
  title: string;
  description: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="page-heading">
      <div>
        {eyebrow && <span className="eyebrow">{eyebrow}</span>}
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action}
    </div>
  );
}

export function PrivateDeployment() {
  return (
    <section className="private-section">
      <div className="private-symbol">
        <ShieldCheck size={34} />
      </div>
      <div>
        <span className="eyebrow">PRIVATE DEPLOYMENT</span>
        <h2>Your files stay inside your infrastructure.</h2>
        <p>
          Local deployment, a private database, and access controlled by your
          organization.
        </p>
        <div className="private-checks">
          {[
            "Role-based access",
            "Audit logs",
            "Private indexing",
            "No external document processing",
            "Air-gapped deployment supported",
          ].map((s) => (
            <span key={s}>
              <Check size={15} />
              {s}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

export const QUICK = [
  "Total spending west",
  "Approved supplier",
  "Contract expiry",
  "Purchase order PO-1023",
  "Budget allocation",
  "Cost center 4012",
];

export const money = (n: number) => new Intl.NumberFormat("en-IN").format(n);
