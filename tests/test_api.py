import importlib

from fastapi.testclient import TestClient

DOC = """Kestrel IT Solutions Ltd
Invoice Number: INV-2001
Invoice Date: 01/09/2026
Due Date: 01/10/2026
Subtotal: £100.00
VAT (20%): £20.00
Total Due: £120.00
"""


def make_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("DOCFLOW_DB", str(tmp_path / "test.db"))
    for var in ["ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DOCFLOW_PROVIDER"]:
        monkeypatch.delenv(var, raising=False)
    import docflow.api as api
    importlib.reload(api)
    return TestClient(api.app)


def test_upload_review_and_metrics(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    assert c.get("/health").json()["status"] == "ok"

    first = c.post("/documents", files={"file": ("a.txt", DOC.encode(), "text/plain")}).json()
    assert first["decision"] == "auto_approved"

    dupe = c.post("/documents", files={"file": ("b.txt", DOC.encode(), "text/plain")}).json()
    assert dupe["decision"] == "rejected"

    broken = DOC.replace("Total Due: £120.00", "Total Due: £150.00")
    pending = c.post("/documents", files={"file": ("c.txt", broken.replace("INV-2001", "INV-2002").encode(), "text/plain")}).json()
    assert pending["status"] == "pending"
    assert c.get("/documents", params={"status": "pending"}).json()[0]["id"] == pending["id"]

    reviewed = c.post(f"/documents/{pending['id']}/review", json={"approve": True}).json()
    assert reviewed["status"] == "approved"

    m = c.get("/metrics").json()
    assert m["documents"] == 3 and m["by_decision"]["rejected"] == 1


def test_rejects_unsupported_files(tmp_path, monkeypatch):
    c = make_client(tmp_path, monkeypatch)
    r = c.post("/documents", files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415
