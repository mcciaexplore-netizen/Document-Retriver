"""Create real, downloadable demo documents and index them through the normal parser."""
import csv
import hashlib
import io
import os
import uuid

import fitz
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from pptx import Presentation
from pptx.util import Inches, Pt

from . import config
from .database import SessionLocal
from .indexing import process_file
from .models import AuditLog, File, Membership, ProcessingJob, User, Workspace
from .security import hash_password


def demo_xlsx():
    workbook = Workbook()
    workbook.remove(workbook.active)
    for region, total in [("West Region", 1845000), ("South Region", 1610000)]:
        sheet = workbook.create_sheet(region)
        sheet.append(["Cost Center", "Category", "Vendor", "Approval Status", "Purchase Order", "Total Spending"])
        categories = ["Machine maintenance", "Raw materials", "Quality inspection", "Transport services", "Safety equipment", "Electrical spares", "Factory utilities", "CNC maintenance", "Packaging supplies", "Staff training", "Calibration services", "Pollution control", "Tooling equipment", "Warehouse operations", "Contract services", "Insurance renewal", "Budget allocation"]
        for index, category in enumerate(categories):
            sheet.append([4012 + index, category, "ABC Industrial Supplies" if index % 2 == 0 else "Pune Precision Works", "Approved" if index % 5 else "Pending", f"PO-{1023 + index}", 65000 + index * 12500])
        sheet.append([4012, f"Total Spending {region.split()[0]}", "ABC Industrial Supplies", "Approved", "PO-1023", total])
        sheet.append(["", "Forecast uplift", "", "", "", "=F19*1.05"])
        for cell in sheet[1]:
            cell.fill = PatternFill("solid", fgColor="075E61")
            cell.font = Font(color="FFFFFF", bold=True)
        for row in sheet.iter_rows(min_row=2):
            row[5].number_format = '₹#,##0'
        for column in "ABCDEF":
            sheet.column_dimensions[column].width = 27 if column in "BC" else 21
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = "A1:F19"
    output = io.BytesIO()
    workbook.save(output)
    workbook.close()
    return output.getvalue()


def demo_csv():
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["Vendor ID", "Supplier", "Material", "Approval Status", "Purchase Order", "Quotation Amount", "Contract Expiry", "Invoice"])
    writer.writerows([
        ["VEN-001", "ABC Industrial Supplies", "Stainless steel", "Approved supplier", "PO-1023", 500000, "2027-03-31", "INV-4402"],
        ["VEN-002", "Pune Precision Works", "CNC tooling", "Approved supplier", "PO-2388", 275000, "2027-06-30", "INV-4403"],
        ["VEN-003", "Deccan Logistics", "Transport vendor", "Approved", "PO-1067", 85000, "2026-12-31", "INV-4404"],
        ["VEN-004", "Sahyadri Metals", "Stainless steel", "Pending review", "PO-1120", 620000, "2027-01-15", "INV-4405"],
        ["VEN-005", "Precision Maintenance Co", "Machine maintenance", "Approved", "PO-1155", 180000, "2027-09-30", "INV-4406"],
        ["VEN-006", "Green Factory Services", "Pollution control", "Approved", "PO-1194", 145000, "2027-02-28", "INV-4407"],
    ])
    return output.getvalue().encode("utf-8-sig")


def demo_pdf():
    document = fitz.open()
    sections = [
        ("Factory compliance register", ["MCCIA | Enterprise document search demonstration", "Factory licence expiry: 31 March 2027. Licence ID: FAC-MH-4012.", "Approval status: Approved compliance document.", "Responsible department: Compliance. Review frequency: Quarterly.", "Pollution certificate: MPCB-2026-1182; valid until 30 September 2027.", "Evidence owner: Operations Manager. Next review: 15 December 2026."]),
        ("Supplier contracts and renewal schedule", ["Contract expiry register | FY 2026-27", "ABC Industrial Supplies: approved supplier for stainless steel.", "Contract reference: CT-2026-103. Expiry: 31 March 2027.", "Purchase order PO-1023 links to invoice INV-4402.", "Renewal requires an approved quality inspection report and vendor evaluation."]),
        ("Maintenance and safety controls", ["Machine maintenance record | Manufacturing", "CNC machine M-04: preventive maintenance every 30 days.", "Latest maintenance: 02 September 2026. Inspection result: Passed.", "Safety inspection certificate: SAFE-2091, approved by plant supervisor.", "Records must be retained in the private compliance workspace."]),
    ]
    for title, paragraphs in sections:
        page = document.new_page(width=595, height=842)
        page.draw_rect(fitz.Rect(0, 0, 595, 110), color=None, fill=(.02, .28, .32))
        page.insert_text((40, 65), title, fontsize=20, color=(1, 1, 1))
        for index, paragraph in enumerate(paragraphs):
            page.insert_textbox(fitz.Rect(40, 145 + index * 75, 555, 205 + index * 75), paragraph, fontsize=12, color=(.15, .2, .25))
        page.insert_text((40, 810), f"MCCIA sample document | Page {len(document)}", fontsize=9)
    data = document.tobytes()
    document.close()
    return data


def demo_pptx():
    presentation = Presentation()
    slides = [
        ("Operations review | September 2026", "MCCIA Enterprise Document Search\nManufacturing and logistics evidence\nPrepared for the MSME operations committee"),
        ("Machine maintenance and CNC downtime", "CNC downtime: 12 hours in August 2026\nMachine maintenance record: M-04 / MAINT-0926\nPreventive maintenance completion: 96%\nQuality inspection report: QIR-4402 — Passed"),
        ("Procurement and budget allocation", "Approved supplier: ABC Industrial Supplies\nPurchase order PO-1023: stainless steel materials\nBudget allocation: INR 2,000,000\nCost center 4012: West Region manufacturing"),
        ("Dispatch and logistics", "Shipment LR 39082: dispatched on 04 September 2026\nDispatch invoice: INV-4402\nTransport vendor: Deccan Logistics\nDelivery status: Received at Pune manufacturing unit"),
    ]
    for title, content in slides:
        slide = presentation.slides.add_slide(presentation.slide_layouts[1])
        slide.shapes.title.text = title
        slide.placeholders[1].text = content
        slide.notes_slide.notes_text_frame.text = f"Source notes: {title}. Demonstration figures for private enterprise search."
    output = io.BytesIO()
    presentation.save(output)
    return output.getvalue()


def bootstrap():
    with SessionLocal() as db:
        admin_email = os.getenv("ADMIN_EMAIL", "admin@mccia.org").lower()
        admin = db.query(User).filter_by(email=admin_email).first()
        if not admin:
            password = os.getenv("ADMIN_PASSWORD")
            if not password and not config.DEMO_SEED:
                raise RuntimeError("Set ADMIN_PASSWORD before starting with DEMO_SEED=false.")
            admin = User(name="MCCIA Admin", email=admin_email, role="Admin", password_hash=hash_password(password or "Mccia@2026!"))
            db.add(admin)
            db.commit()
        if not config.DEMO_SEED or db.query(Workspace).count():
            return
        users = [admin]
        for name, email, role, variable, fallback in [("Priya Sharma", "manager@mccia.org", "Manager", "MANAGER_PASSWORD", "Manager@2026!"), ("Rahul Deshmukh", "viewer@mccia.org", "Viewer", "VIEWER_PASSWORD", "Viewer@2026!")]:
            member = db.query(User).filter_by(email=email).first()
            if not member:
                member = User(name=name, email=email, role=role, password_hash=hash_password(os.getenv(variable, fallback)))
                db.add(member)
                db.flush()
            users.append(member)
        workspaces = []
        for name, description, color in [("Finance", "Spending, supplier records and business evidence", "teal"), ("Procurement", "Approved vendors, quotations and purchase orders", "blue"), ("Compliance", "Licences, certificates and regulatory records", "green"), ("Operations", "Manufacturing, maintenance and logistics", "amber")]:
            workspace = Workspace(name=name, description=description, color=color)
            db.add(workspace)
            db.flush()
            workspaces.append(workspace)
            for member in users:
                db.add(Membership(workspace_id=workspace.id, user_id=member.id))
        db.commit()
        tasks = []
        for filename, factory, category in [("spending_report.xlsx", demo_xlsx, "Finance"), ("approved_suppliers.csv", demo_csv, "Procurement"), ("compliance_register.pdf", demo_pdf, "Compliance"), ("operations_review.pptx", demo_pptx, "Operations")]:
            data = factory()
            extension = filename.rsplit(".", 1)[1]
            key = f"{uuid.uuid4().hex}.{extension}"
            (config.STORAGE_PATH / key).write_bytes(data)
            file = File(workspace_id=workspaces[0].id, filename=filename, file_type=extension, file_size=len(data), storage_key=key, checksum=hashlib.sha256(data).hexdigest(), category=category, source_type="upload", uploaded_by=admin.id)
            db.add(file)
            db.flush()
            job = ProcessingJob(file_id=file.id)
            db.add(job)
            db.flush()
            db.add(AuditLog(user_id=admin.id, user_name=admin.name, workspace_id=workspaces[0].id, action="upload", file_id=file.id, file_name=filename, details_json={"source": "demo_seed", "size": len(data)}))
            tasks.append((file.id, job.id))
        db.commit()
    for file_id, job_id in tasks:
        process_file(file_id, job_id)
