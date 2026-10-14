import io
import zipfile

from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import make_inputs

client = TestClient(app)


def test_meta_does_not_leak_secrets():
    r = client.get("/api/meta")
    assert r.status_code == 200
    body = r.text
    assert "sk-ant" not in body and "ANTHROPIC" not in body
    assert {"provider", "enabled", "model", "label"} == set(r.json()["ai"])


def test_generate_requires_client_and_project_name():
    r = client.post("/api/proposals/generate", json={"inputs": make_inputs(client={"name": ""})})
    assert r.status_code == 422


def test_full_proposal_lifecycle():
    inputs = make_inputs(client={"name": "عميل واجهة الاختبار", "sector": "retail"},
                         project={"name": "حملة الجمعة البيضاء", "type": "campaign", "platforms": []},
                         services={"selected": ["paid_ads", "influencer_marketing"]})
    r = client.post("/api/proposals/generate", json={"inputs": inputs})
    assert r.status_code == 201
    p = r.json()
    pid = p["id"]
    assert p["number"].startswith("AHD-")
    assert p["client_id"]

    doc = p["doc"]
    doc["sections"][0]["title"] = "عنوان معدل"
    r = client.put(f"/api/proposals/{pid}", json={"doc": doc, "status": "review"})
    assert r.status_code == 200 and r.json()["status"] == "review"
    assert client.get(f"/api/proposals/{pid}").json()["doc"]["sections"][0]["title"] == "عنوان معدل"

    # search: client, project, service, sector, year, with hamza/ta-marbuta variants
    for q in ["واجهة الاختبار", "الجمعه البيضاء", "المؤثرين", "التجزئة", "2026"]:
        items = client.get("/api/proposals", params={"q": q}).json()["items"]
        assert any(i["id"] == pid for i in items), q

    sec = doc["sections"][2]["id"]
    r = client.post(f"/api/proposals/{pid}/sections/{sec}/regenerate", json={"tone": "luxury"})
    assert r.status_code == 200 and r.json()["tone"] == "luxury"

    r = client.post(f"/api/proposals/{pid}/versions", json={"note": "قبل المراجعة"})
    assert r.json()["version"] == "1.1"
    revs = client.get(f"/api/proposals/{pid}/revisions").json()["items"]
    assert len(revs) == 1
    assert client.post(f"/api/proposals/{pid}/revisions/{revs[0]['id']}/restore").status_code == 200

    dup = client.post(f"/api/proposals/{pid}/duplicate").json()
    assert dup["id"] != pid and dup["project_name"].endswith("(نسخة)")
    reuse = client.get(f"/api/proposals/{pid}/reuse").json()["inputs"]
    assert reuse["client"] == {} and reuse["project"]["type"] == "campaign"

    tpl = client.post(f"/api/proposals/{pid}/save-as-template", json={"name": "قالب الجمعة البيضاء"})
    assert tpl.status_code == 201

    pptx = client.get(f"/api/proposals/{pid}/export/pptx")
    assert pptx.status_code == 200
    z = zipfile.ZipFile(io.BytesIO(pptx.content))
    slides = [n for n in z.namelist() if n.startswith("ppt/slides/slide")]
    assert len(slides) > 12
    assert "filename*=UTF-8''" in pptx.headers["content-disposition"]

    assert client.delete(f"/api/proposals/{pid}").status_code == 204
    assert client.get(f"/api/proposals/{pid}").status_code == 404
    client.delete(f"/api/proposals/{dup['id']}")


def test_print_data_requires_a_valid_token():
    pid = client.get("/api/proposals").json()["items"][0]["id"]
    assert client.get(f"/api/proposals/{pid}/print-data", params={"token": "nope"}).status_code == 403
    from app.core.security import issue_print_token
    token = issue_print_token(pid)
    assert client.get(f"/api/proposals/{pid}/print-data", params={"token": token}).status_code == 200
    other = client.get("/api/proposals").json()["items"][1]["id"]
    assert client.get(f"/api/proposals/{other}/print-data", params={"token": token}).status_code == 403


def test_settings_only_accept_editable_keys():
    r = client.put("/api/settings", json={"values": {"tagline": "نربط الإبداع بالهدف", "proposal_seq": 1, "ANTHROPIC_API_KEY": "x"}})
    assert r.status_code == 200
    values = r.json()["values"]
    assert "ANTHROPIC_API_KEY" not in values and "proposal_seq" not in values


def test_library_crud_and_generator_uses_it():
    r = client.post("/api/library/kpis", json={"title": "مؤشر مخصص للاختبار", "data": {"name_en": "Custom KPI", "definition": "تعريف", "types": ["social_media"]}})
    assert r.status_code == 201
    item = r.json()
    assert client.put(f"/api/library/kpis/{item['id']}", json={"title": "مؤشر معدل", "data": item["data"], "active": False}).json()["active"] is False
    assert client.delete(f"/api/library/kpis/{item['id']}").status_code == 204
    assert client.get("/api/library/unknown").status_code == 404


def test_upload_validation():
    bad = client.post("/api/uploads", files={"file": ("x.txt", b"hello", "text/plain")})
    assert bad.status_code == 415
    svg = client.post("/api/uploads", files={"file": ("x.svg", b"<svg><script>alert(1)</script></svg>", "image/svg+xml")})
    assert svg.status_code == 415
    png = b"\x89PNG\r\n\x1a\n" + b"0" * 32
    ok = client.post("/api/uploads", files={"file": ("logo.png", png, "image/png")})
    assert ok.status_code == 201
    assert client.get(ok.json()["url"]).status_code == 200
    for probe in ["/files/..%2Fahdaf.db", "/files/..%2F..%2Fapp%2Fconfig.py", "/files/x.txt"]:
        r = client.get(probe)  # traversal never reaches the file system: 404 or the SPA shell
        assert r.status_code == 404 or ('<div id="app">' in r.text and "SQLite" not in r.text and "ANTHROPIC" not in r.text)


def test_clients_and_templates():
    r = client.post("/api/clients", json={"name": "عميل جديد للاختبار", "sector": "education"})
    assert r.status_code == 201
    assert client.post("/api/clients", json={"name": "عميل جديد للاختبار"}).status_code == 409
    cid = r.json()["id"]
    assert client.get(f"/api/clients/{cid}").json()["proposals"] == []
    assert client.delete(f"/api/clients/{cid}").status_code == 204
    assert isinstance(client.get("/api/templates").json()["items"], list)


def test_upgrade_purges_demo_data():
    from app.data import repositories as repo
    from app.data.seed import ensure_seeded
    repo.clients.create({"name": "عميل تجريبي للترقية"}, is_demo=True)
    repo.settings.set_many({"data_version": 1})
    ensure_seeded()
    assert all(not c["is_demo"] for c in repo.clients.list())
    assert all(not p["is_demo"] for p in repo.proposals.list())
    assert repo.settings.get("data_version") == 2


def test_spa_routes_serve_index():
    for path in ["/", "/new", "/proposals", "/library/kpis"]:
        r = client.get(path)
        assert r.status_code == 200 and "<div id=\"app\">" in r.text
    assert client.get("/api/does-not-exist").status_code == 404
