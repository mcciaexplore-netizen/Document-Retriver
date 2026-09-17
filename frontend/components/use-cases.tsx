"use client";
import { Search, BriefcaseBusiness, ArrowUpRight } from "lucide-react";
import { Heading, PrivateDeployment } from "@/components/shared";

export function UseCases({ onSearch }: any) {
  const cases = [
    [
      "Procurement",
      "Supplier records, quotations, and purchase orders",
      ["approved supplier", "purchase order PO-1023", "vendor quotation"],
    ],
    [
      "Finance",
      "Spending, invoices, and budget allocations",
      [
        "total spending west",
        "machine maintenance expenses",
        "invoice INV-4402",
      ],
    ],
    [
      "Compliance",
      "Licences, certificates, and renewal dates",
      [
        "factory licence expiry",
        "approved compliance document",
        "pollution certificate",
      ],
    ],
    [
      "Manufacturing",
      "Equipment records and quality documentation",
      [
        "machine maintenance record",
        "CNC downtime",
        "quality inspection report",
      ],
    ],
    [
      "Logistics",
      "Shipments, dispatch records, and transport partners",
      ["shipment LR 39082", "dispatch invoice", "transport vendor"],
    ],
  ];
  return (
    <>
      <Heading
        eyebrow="BUILT FOR MSMEs"
        title="Everyday questions. Exact evidence."
        description="Practical ways to find business information across your enterprise documents."
      />
      <div className="use-case-grid">
        {cases.map(([name, desc, queries], i) => (
          <section className="use-case-card" key={String(name)}>
            <span className="use-case-no">0{i + 1}</span>
            <BriefcaseBusiness size={24} />
            <h2>{name}</h2>
            <p>{desc}</p>
            <div>
              {(queries as string[]).map((q) => (
                <button key={q} onClick={() => onSearch(q)}>
                  <Search size={15} />
                  {q}
                  <ArrowUpRight size={15} />
                </button>
              ))}
            </div>
          </section>
        ))}
      </div>
      <p className="muted">
        Examples search your current workspace. Results depend on the documents
        you have indexed.
      </p>
      <PrivateDeployment />
    </>
  );
}
