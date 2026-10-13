"""The in-browser dispatcher (app/browser.py) must answer like the HTTP API."""
import json
import zipfile
import io

from app import browser
from tests.conftest import make_inputs


def call(method, path, body=None, query=None):
    out = json.loads(browser.handle(method, path, json.dumps(query or {}), json.dumps(body)))
    return out["status"], out["body"]


def test_meta_marks_browser_edition_and_rules_engine():
    status, body = call("GET", "/api/meta")
    assert status == 200 and body["edition"] == "browser" and body["ai"]["enabled"] is False


def test_proposal_lifecycle_through_dispatcher():
    status, body = call("POST", "/api/proposals/generate", {"inputs": make_inputs(client={"name": ""})})
    assert status == 422
    status, p = call("POST", "/api/proposals/generate", {"inputs": make_inputs(client={"name": "عميل نسخة المتصفح"})})
    assert status == 201 and p["doc"]["sections"]
    pid = p["id"]
    assert call("GET", f"/api/proposals/{pid}")[0] == 200
    status, listing = call("GET", "/api/proposals", query={"q": "نسخة المتصفح"})
    assert any(i["id"] == pid for i in listing["items"])
    sid = p["doc"]["sections"][1]["id"]
    status, sec = call("POST", f"/api/proposals/{pid}/sections/{sid}/regenerate", {"tone": "formal"})
    assert status == 200 and sec["tone"] == "formal"
    assert call("PUT", f"/api/proposals/{pid}", {"status": "nope"})[0] == 422
    assert call("PUT", f"/api/proposals/{pid}", {"status": "sent"})[1]["status"] == "sent"
    pptx = browser.export_pptx(pid)
    assert len([n for n in zipfile.ZipFile(io.BytesIO(pptx)).namelist() if n.startswith("ppt/slides/slide")]) > 10
    assert call("DELETE", f"/api/proposals/{pid}")[0] == 204
    assert call("GET", f"/api/proposals/{pid}")[0] == 404


def test_settings_and_library_through_dispatcher():
    status, body = call("PUT", "/api/settings", {"values": {"tagline": "نربط الإبداع بالهدف", "proposal_seq": 99}})
    assert status == 200 and "proposal_seq" not in body["values"]
    assert call("GET", "/api/library/nothing")[0] == 404
    assert call("GET", "/api/unknown")[0] == 404
