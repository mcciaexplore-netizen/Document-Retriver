import csv
import io
import json
from fastapi.testclient import TestClient
from main import app
from seed import demo_xlsx, demo_pdf, demo_pptx
from database import SessionLocal
from models import SearchRecord, SpreadsheetCell


def upload(client, workspace_id, name, data):
    response = client.post("/api/files/upload", data={"workspace_id": workspace_id}, files=[("files", (name, data, "application/octet-stream"))])
    assert response.status_code == 202, response.text
    assert not response.json()["errors"], response.text
    file = response.json()["files"][0]
    detail = client.get(f"/api/files/{file['id']}")
    assert detail.json()["status"] == "indexed", detail.text
    return file["id"]


def search(client, workspace_id, query, filters=None):
    response = client.post("/api/search", json={"workspace_id": workspace_id, "query": query, "filters": filters or {}})
    assert response.status_code == 200, response.text
    return response.json()


def test_auth_session_and_origin(client):
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "admin@mccia.org", "password": "incorrect"}).status_code == 401
    response = client.post("/api/auth/login", json={"email": "admin@mccia.org", "password": "Mccia@2026!"})
    assert response.status_code == 200
    assert "httponly" in response.headers["set-cookie"].lower()
    assert client.get("/api/auth/me").json()["role"] == "Admin"
    assert client.post("/api/workspaces", json={"name": "Untrusted"}, headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_seed_precise_excel_evidence(admin):
    workspaces = admin.get("/api/workspaces").json()
    finance = next(w for w in workspaces if w["name"] == "Finance")
    result = search(admin, finance["id"], "total spending west")
    assert result["total_results"] > 0
    primary = result["results"][0]
    assert primary["value"] == "₹18,45,000"
    assert primary["location"]["cell"] == "F19"
    assert primary["location"]["sheet"] == "West Region"
    source = admin.get(f"/api/records/{primary['result_id']}/source").json()
    matched = [cell for row in source["rows"] for cell in row["cells"] if cell["matched"]]
    assert len(matched) == 1
    assert matched[0]["coordinate"] == "F19"
    assert source["headers"][5]["label"] == "Total Spending"
    assert any(result["value"] == "₹18,45,000" for result in search(admin, finance["id"], "1845000")["results"])


def test_csv_boolean_exact_numeric_filters_duplicate_and_export(admin, workspace):
    data = b'ID,Supplier,Status,Budget,Formula\nPO-1023,Alpha Steel,Approved,150000,=1+1\nPO-2388,Beta Steel,Pending,90000,safe\nPO-1024,Alpha Parts,Approved,250000,safe\n'
    file_id = upload(admin, workspace, "../vendors.csv", data)
    assert admin.get(f"/api/files/{file_id}").json()["filename"] == "vendors.csv"
    assert search(admin, workspace, '"Alpha Steel" AND Approved')["total_results"] == 5
    assert search(admin, workspace, '(Alpha OR Beta) AND NOT Pending')["total_results"] == 10
    numeric = search(admin, workspace, "budget above 100000")
    assert {result["value"] for result in numeric["results"]} == {"150000", "250000"}
    assert search(admin, workspace, "", {"amount_min": 200000, "file_type": "csv"})["results"][0]["value"] == "250000"
    assert search(admin, workspace, "PO-2388", {"file_id": file_id})["total_results"] == 5
    assert search(admin, workspace, "SQL' OR 1=1 --")["total_results"] == 0
    assert search(admin, workspace, "%")["total_results"] == 0
    duplicate = admin.post("/api/files/upload", data={"workspace_id": workspace}, files=[("files", ("same.csv", data))]).json()
    assert len(duplicate["skipped"]) == 1
    exported = admin.post("/api/search/export", json={"workspace_id": workspace, "query": "", "filters": {}})
    rows = list(csv.reader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert any(row[1] == "'=1+1" for row in rows[1:])
    assert "text/csv" in exported.headers["content-type"]
    audit = admin.get("/api/audit", params={"workspace_id": workspace}).json()
    assert {"upload", "search", "export", "upload_duplicate"}.issubset({event["action"] for event in audit})


def test_all_formats_sources_reindex_and_delete(admin, workspace):
    cases = [("book.xlsx", demo_xlsx(), "total spending west", "xlsx"), ("register.pdf", demo_pdf(), "factory licence expiry", "pdf"), ("deck.pptx", demo_pptx(), "CNC downtime", "pptx")]
    for filename, data, term, kind in cases:
        file_id = upload(admin, workspace, filename, data)
        result = search(admin, workspace, term, {"file_id": file_id})["results"][0]
        response = admin.get(f"/api/records/{result['id']}/source")
        assert response.status_code == 200, response.text
        source = response.json()
        assert source["type"] == kind
        assert source["citation"]["file_id"] == file_id
        if kind == "pdf":
            image = admin.get(source["page"]["image_url"])
            assert image.status_code == 200, image.text[:100] if image.status_code != 200 else ""
            assert image.content.startswith(b"\x89PNG")
        elif kind == "pptx":
            assert "CNC" in source["slide"]["content"]
            assert source["slide"]["notes"]
        else:
            with SessionLocal() as db:
                formula = db.query(SpreadsheetCell).join(SearchRecord, SearchRecord.id == SpreadsheetCell.record_id).filter(SearchRecord.file_id == file_id, SpreadsheetCell.formula.isnot(None)).first()
                assert formula.formula == "=F19*1.05"
        assert admin.get(f"/api/files/{file_id}/download").content == data
        assert admin.post(f"/api/files/{file_id}/reindex").status_code == 202
        assert search(admin, workspace, term, {"file_id": file_id})["total_results"] > 0
        assert admin.delete(f"/api/files/{file_id}").status_code == 200
        assert search(admin, workspace, term, {"file_id": file_id})["total_results"] == 0
        assert admin.get(f"/api/files/{file_id}/download").status_code == 404


def test_failed_processing_and_validation(admin, workspace):
    bad = admin.post("/api/files/upload", data={"workspace_id": workspace}, files=[("files", ("bad.pdf", b"not a PDF"))]).json()
    file_id = bad["files"][0]["id"]
    detail = admin.get(f"/api/files/{file_id}").json()
    assert detail["status"] == "failed"
    assert "valid PDF" in detail["error"]
    assert detail["job"]["status"] == "failed"
    unsupported = admin.post("/api/files/upload", data={"workspace_id": workspace}, files=[("files", ("app.exe", b"binary"))]).json()
    assert "Unsupported" in unsupported["errors"][0]["error"]
    assert admin.post("/api/search", json={"workspace_id": workspace, "query": '"unfinished'}).status_code == 422
    assert admin.post("/api/search", json={"workspace_id": workspace, "query": "term AND"}).status_code == 422
    assert admin.post("/api/search", json={"workspace_id": workspace, "filters": {"page": 0}}).status_code == 422


def test_workspace_permissions_membership_and_viewer(admin, workspace):
    file_id = upload(admin, workspace, "private.csv", b"ID,Value\nSECRET-77,Confidential\n")
    record_id = search(admin, workspace, "SECRET-77")["results"][0]["id"]
    users = admin.get("/api/users").json()
    viewer = next(user for user in users if user["role"] == "Viewer")
    manager = next(user for user in users if user["role"] == "Manager")
    admin.post("/api/auth/login", json={"email": "viewer@mccia.org", "password": "Viewer@2026!"})
    assert all(w["id"] != workspace for w in admin.get("/api/workspaces").json())
    assert admin.get(f"/api/files/{file_id}").status_code == 404
    assert admin.get(f"/api/records/{record_id}/source").status_code == 404
    assert admin.post("/api/search", json={"workspace_id": workspace, "query": "SECRET"}).status_code == 404
    assert admin.get("/api/audit").status_code == 403
    assert admin.post("/api/workspaces", json={"name": "Forbidden"}).status_code == 403
    admin.post("/api/auth/login", json={"email": "admin@mccia.org", "password": "Mccia@2026!"})
    assert admin.post(f"/api/workspaces/{workspace}/members", json={"user_id": viewer["id"]}).status_code == 200
    assert admin.post(f"/api/workspaces/{workspace}/members", json={"user_id": manager["id"]}).status_code == 200
    admin.post("/api/auth/login", json={"email": "viewer@mccia.org", "password": "Viewer@2026!"})
    assert search(admin, workspace, "SECRET")["total_results"] == 2
    assert admin.get(f"/api/records/{record_id}/source").status_code == 200
    assert admin.post(f"/api/files/{file_id}/reindex").status_code == 403
    assert admin.delete(f"/api/files/{file_id}").status_code == 403
    admin.post("/api/auth/login", json={"email": "manager@mccia.org", "password": "Manager@2026!"})
    assert admin.get("/api/audit", params={"workspace_id": workspace}).status_code == 200
    upload(admin, workspace, "manager.csv", b"Status\nApproved\n")
    assert admin.delete(f"/api/files/{file_id}").status_code == 403


def test_dashboard_and_history_from_actual_events(admin, workspace):
    upload(admin, workspace, "dashboard.csv", b"Code,Amount\nCODE-1,3000\n")
    search(admin, workspace, "CODE-1")
    dashboard = admin.get("/api/dashboard", params={"workspace_id": workspace}).json()
    assert dashboard["stats"]["total_files"] == 1
    assert dashboard["stats"]["total_records"] == 2
    assert dashboard["stats"]["searches_today"] == 1
    assert len(dashboard["search_activity"]) == 7
    assert admin.get("/api/search/history", params={"workspace_id": workspace}).json()[0]["query"] == "CODE-1"


def test_password_change_keeps_current_session_and_revokes_others(admin):
    created = admin.post("/api/users", json={"name": "Password Test", "email": "password-test@mccia.org", "password": "Original@2026!", "role": "Viewer"})
    assert created.status_code == 201, created.text
    with TestClient(app) as first, TestClient(app) as second:
        credentials = {"email": "password-test@mccia.org", "password": "Original@2026!"}
        assert first.post("/api/auth/login", json=credentials).status_code == 200
        assert second.post("/api/auth/login", json=credentials).status_code == 200
        assert first.post("/api/auth/password", json={"current_password": "wrong", "new_password": "Changed@2026!"}).status_code == 400
        assert first.post("/api/auth/password", json={"current_password": "Original@2026!", "new_password": "short"}).status_code == 422
        changed = first.post("/api/auth/password", json={"current_password": "Original@2026!", "new_password": "Changed@2026!"})
        assert changed.status_code == 200, changed.text
        assert first.get("/api/auth/me").status_code == 200
        assert second.get("/api/auth/me").status_code == 401
        assert second.post("/api/auth/login", json=credentials).status_code == 401
        credentials["password"] = "Changed@2026!"
        assert second.post("/api/auth/login", json=credentials).status_code == 200


def test_source_preserves_blank_cells_headers_and_timestamp(admin, workspace):
    response = admin.post("/api/files/upload", data={"workspace_id": workspace, "last_modified": json.dumps(["2024-03-01T10:30:00Z"])}, files=[("files", ("sparse.csv", b"ID,Optional,Amount,Empty\nID-100,,150000,\n,,,\nID-200,Present,200000,\n"))])
    assert response.status_code == 202, response.text
    file_id = response.json()["files"][0]["id"]
    detail = admin.get(f"/api/files/{file_id}").json()
    assert detail["last_modified"] == "2024-03-01T10:30:00Z"
    result = search(admin, workspace, "ID-100", {"header": "Amount"})["results"][0]
    assert result["value"] == "150000"
    source = admin.get(f"/api/records/{result['id']}/source").json()
    assert [header["label"] for header in source["headers"]] == ["ID", "Optional", "Amount", "Empty"]
    assert all(len(row["cells"]) == 4 for row in source["rows"])
    assert [cell["value"] for cell in source["rows"][0]["cells"]] == ["ID-100", "", "150000", ""]
    assert source["rows"][0]["cells"][2]["matched"]
    assert source["rows"][1]["row_number"] == 3
    assert all(cell["value"] == "" for cell in source["rows"][1]["cells"])
    assert admin.post(f"/api/files/{file_id}/reindex").status_code == 202
    assert admin.get(f"/api/files/{file_id}").json()["last_modified"] == "2024-03-01T10:30:00Z"


def test_record_versions_reject_stale_citations_after_reindex(admin, workspace):
    file_id = upload(admin, workspace, "versions.csv", b"ID,Amount\nVERSION-01,500\n")
    previous = search(admin, workspace, "VERSION-01")["results"][0]
    assert admin.get(f"/api/records/{previous['id']}/source", params={"version": previous["record_version"]}).status_code == 200
    assert admin.post(f"/api/files/{file_id}/reindex").status_code == 202
    fresh = search(admin, workspace, "VERSION-01")["results"][0]
    assert fresh["record_version"] != previous["record_version"]
    assert admin.get(f"/api/records/{previous['id']}/source", params={"version": previous["record_version"]}).status_code in {404, 409}
    before = admin.get("/api/audit", params={"workspace_id": workspace}).json()
    mismatch = admin.get(f"/api/records/{fresh['id']}/source", params={"version": previous["record_version"]})
    assert mismatch.status_code == 409, mismatch.text
    after = admin.get("/api/audit", params={"workspace_id": workspace}).json()
    assert len(after) == len(before), "Rejected source requests must not log a successful source opening."
    opened = admin.get(f"/api/records/{fresh['id']}/source", params={"version": fresh["record_version"]})
    assert opened.status_code == 200, opened.text
    assert opened.json()["record"]["record_version"] == fresh["record_version"]
