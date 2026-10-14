"""Data access layer. Every SQL statement in the app lives here."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.arabic import normalize
from app.data.db import get_connection, transaction


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:16]


def _row(row) -> dict | None:
    return dict(row) if row is not None else None


def _loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


# --------------------------------------------------------------------------- clients
class ClientRepo:
    FIELDS = ("name", "sector", "contact_name", "contact_email", "contact_phone", "about", "website", "logo")

    def list(self, q: str = "") -> list[dict]:
        conn = get_connection()
        rows = conn.execute(
            """SELECT c.*, (SELECT COUNT(*) FROM proposals p WHERE p.client_id = c.id) AS proposals_count,
                      (SELECT MAX(p.updated_at) FROM proposals p WHERE p.client_id = c.id) AS last_proposal_at
               FROM clients c ORDER BY c.updated_at DESC"""
        ).fetchall()
        items = [dict(r) for r in rows]
        if q:
            nq = normalize(q)
            items = [c for c in items if nq in normalize(f"{c['name']} {c.get('sector') or ''} {c.get('contact_name') or ''}")]
        return items

    def get(self, client_id: str) -> dict | None:
        return _row(get_connection().execute("SELECT * FROM clients WHERE id = ?", (client_id,)).fetchone())

    def find_by_name(self, name: str) -> dict | None:
        target = normalize(name)
        for row in get_connection().execute("SELECT * FROM clients").fetchall():
            if normalize(row["name"]) == target:
                return dict(row)
        return None

    def create(self, data: dict, is_demo: bool = False) -> dict:
        cid = data.get("id") or new_id()
        ts = now_iso()
        values = {f: data.get(f) for f in self.FIELDS}
        with transaction() as conn:
            conn.execute(
                f"INSERT INTO clients (id, {', '.join(self.FIELDS)}, is_demo, created_at, updated_at) "
                f"VALUES (?, {', '.join('?' * len(self.FIELDS))}, ?, ?, ?)",
                (cid, *values.values(), int(is_demo), ts, ts),
            )
        return self.get(cid)

    def update(self, client_id: str, data: dict) -> dict | None:
        fields = [f for f in self.FIELDS if f in data]
        if fields:
            with transaction() as conn:
                conn.execute(
                    f"UPDATE clients SET {', '.join(f + ' = ?' for f in fields)}, updated_at = ? WHERE id = ?",
                    (*[data[f] for f in fields], now_iso(), client_id),
                )
        return self.get(client_id)

    def delete(self, client_id: str) -> None:
        with transaction() as conn:
            conn.execute("UPDATE proposals SET client_id = NULL WHERE client_id = ?", (client_id,))
            conn.execute("DELETE FROM clients WHERE id = ?", (client_id,))

    def delete_demo(self) -> None:
        with transaction() as conn:
            conn.execute("UPDATE proposals SET client_id = NULL WHERE client_id IN (SELECT id FROM clients WHERE is_demo = 1)")
            conn.execute("DELETE FROM clients WHERE is_demo = 1")

    def upsert_by_name(self, name: str, sector: str | None = None, extra: dict | None = None) -> dict:
        existing = self.find_by_name(name)
        payload = {"name": name, "sector": sector, **(extra or {})}
        payload = {k: v for k, v in payload.items() if v not in (None, "")}
        if existing:
            return self.update(existing["id"], payload)
        return self.create(payload)


# --------------------------------------------------------------------------- proposals
LIST_COLUMNS = ("id, number, client_id, client_name, project_name, project_type, sector, status, version, "
                "is_demo, created_at, updated_at, meta")


class ProposalRepo:
    def _decode(self, row) -> dict | None:
        if row is None:
            return None
        d = dict(row)
        for key, default in (("inputs", {}), ("doc", {}), ("meta", {})):
            if key in d:
                d[key] = _loads(d[key], default)
        d["is_demo"] = bool(d.get("is_demo"))
        return d

    def list(self, q: str = "", status: str = "", project_type: str = "", year: str = "",
             client_id: str = "", limit: int = 200) -> list[dict]:
        sql = f"SELECT {LIST_COLUMNS} FROM proposals WHERE 1=1"
        params: list[Any] = []
        for term in normalize(q).split():
            sql += " AND search_text LIKE ?"
            params.append(f"%{term}%")
        if status:
            sql += " AND status = ?"
            params.append(status)
        if project_type:
            sql += " AND project_type = ?"
            params.append(project_type)
        if year:
            sql += " AND substr(created_at, 1, 4) = ?"
            params.append(year)
        if client_id:
            sql += " AND client_id = ?"
            params.append(client_id)
        sql += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = get_connection().execute(sql, params).fetchall()
        out = []
        for r in rows:
            d = self._decode(r)
            meta = d.pop("meta", {}) or {}
            d["services"] = meta.get("service_labels", [])
            d["missing_count"] = len(meta.get("missing", []))
            d["type_label"] = meta.get("type_label", "")
            d["sector_label"] = meta.get("sector_label", d.get("sector") or "")
            out.append(d)
        return out

    def get(self, proposal_id: str) -> dict | None:
        return self._decode(get_connection().execute("SELECT * FROM proposals WHERE id = ?", (proposal_id,)).fetchone())

    def create(self, record: dict) -> dict:
        pid = record.get("id") or new_id()
        ts = now_iso()
        with transaction() as conn:
            conn.execute(
                """INSERT INTO proposals (id, number, client_id, client_name, project_name, project_type, sector,
                       status, version, inputs, doc, meta, search_text, is_demo, owner, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (pid, record["number"], record.get("client_id"), record["client_name"], record["project_name"],
                 record.get("project_type"), record.get("sector"), record.get("status", "draft"),
                 record.get("version", "1.0"), _dumps(record.get("inputs", {})), _dumps(record.get("doc", {})),
                 _dumps(record.get("meta", {})), record.get("search_text", ""), int(record.get("is_demo", False)),
                 record.get("owner"), record.get("created_at", ts), record.get("updated_at", ts)),
            )
        return self.get(pid)

    def update(self, proposal_id: str, changes: dict) -> dict | None:
        allowed = ("number", "client_id", "client_name", "project_name", "project_type", "sector", "status",
                   "version", "inputs", "doc", "meta", "search_text")
        sets, params = [], []
        for key in allowed:
            if key in changes:
                value = changes[key]
                if key in ("inputs", "doc", "meta"):
                    value = _dumps(value)
                sets.append(f"{key} = ?")
                params.append(value)
        if not sets:
            return self.get(proposal_id)
        sets.append("updated_at = ?")
        params.append(now_iso())
        params.append(proposal_id)
        with transaction() as conn:
            conn.execute(f"UPDATE proposals SET {', '.join(sets)} WHERE id = ?", params)
        return self.get(proposal_id)

    def delete(self, proposal_id: str) -> None:
        with transaction() as conn:
            conn.execute("DELETE FROM proposal_revisions WHERE proposal_id = ?", (proposal_id,))
            conn.execute("DELETE FROM proposals WHERE id = ?", (proposal_id,))

    def delete_demo(self) -> None:
        with transaction() as conn:
            conn.execute("DELETE FROM proposal_revisions WHERE proposal_id IN (SELECT id FROM proposals WHERE is_demo = 1)")
            conn.execute("DELETE FROM proposals WHERE is_demo = 1")

    def years(self) -> list[str]:
        rows = get_connection().execute(
            "SELECT DISTINCT substr(created_at, 1, 4) AS y FROM proposals ORDER BY y DESC").fetchall()
        return [r["y"] for r in rows]

    def stats(self) -> dict:
        conn = get_connection()
        rows = conn.execute("SELECT status, COUNT(*) AS n FROM proposals GROUP BY status").fetchall()
        by_status = {r["status"]: r["n"] for r in rows}
        total = sum(by_status.values())
        clients = conn.execute("SELECT COUNT(*) AS n FROM clients").fetchone()["n"]
        month = now_iso()[:7]
        this_month = conn.execute("SELECT COUNT(*) AS n FROM proposals WHERE substr(created_at,1,7) = ?",
                                  (month,)).fetchone()["n"]
        return {"total": total, "by_status": by_status, "clients": clients, "this_month": this_month}

    # revisions
    def add_revision(self, proposal: dict, note: str = "") -> dict:
        rid = new_id()
        with transaction() as conn:
            conn.execute(
                "INSERT INTO proposal_revisions (id, proposal_id, version, note, inputs, doc, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (rid, proposal["id"], proposal.get("version", "1.0"), note, _dumps(proposal.get("inputs", {})),
                 _dumps(proposal.get("doc", {})), now_iso()),
            )
        return {"id": rid}

    def revisions(self, proposal_id: str) -> list[dict]:
        rows = get_connection().execute(
            "SELECT id, version, note, created_at FROM proposal_revisions WHERE proposal_id = ? ORDER BY created_at DESC",
            (proposal_id,)).fetchall()
        return [dict(r) for r in rows]

    def get_revision(self, revision_id: str) -> dict | None:
        row = get_connection().execute("SELECT * FROM proposal_revisions WHERE id = ?", (revision_id,)).fetchone()
        if not row:
            return None
        d = dict(row)
        d["inputs"], d["doc"] = _loads(d["inputs"], {}), _loads(d["doc"], {})
        return d


# --------------------------------------------------------------------------- library
class LibraryRepo:
    KINDS = ("services", "deliverables", "methodologies", "kpis", "intro_templates", "conclusion_templates",
             "roles", "past_projects", "sectors")

    def _decode(self, row) -> dict:
        d = dict(row)
        d["data"] = _loads(d.get("data"), {})
        d["active"] = bool(d.get("active"))
        d["is_demo"] = bool(d.get("is_demo"))
        return d

    def list(self, kind: str, include_inactive: bool = True) -> list[dict]:
        sql = "SELECT * FROM library_items WHERE kind = ?"
        if not include_inactive:
            sql += " AND active = 1"
        rows = get_connection().execute(sql + " ORDER BY sort, created_at", (kind,)).fetchall()
        return [self._decode(r) for r in rows]

    def all_active(self) -> dict[str, list[dict]]:
        rows = get_connection().execute(
            "SELECT * FROM library_items WHERE active = 1 ORDER BY kind, sort, created_at").fetchall()
        out: dict[str, list[dict]] = {k: [] for k in self.KINDS}
        for r in rows:
            out.setdefault(r["kind"], []).append(self._decode(r))
        return out

    def counts(self) -> dict[str, int]:
        rows = get_connection().execute("SELECT kind, COUNT(*) AS n FROM library_items GROUP BY kind").fetchall()
        return {r["kind"]: r["n"] for r in rows}

    def get(self, item_id: str) -> dict | None:
        row = get_connection().execute("SELECT * FROM library_items WHERE id = ?", (item_id,)).fetchone()
        return self._decode(row) if row else None

    def create(self, kind: str, title: str, data: dict, key: str | None = None, sort: int | None = None,
               is_demo: bool = False, active: bool = True) -> dict:
        iid = new_id()
        ts = now_iso()
        if sort is None:
            sort = get_connection().execute(
                "SELECT COALESCE(MAX(sort), 0) + 1 AS s FROM library_items WHERE kind = ?", (kind,)).fetchone()["s"]
        with transaction() as conn:
            conn.execute(
                "INSERT INTO library_items (id, kind, key, title, data, sort, active, is_demo, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (iid, kind, key or iid, title, _dumps(data), sort, int(active), int(is_demo), ts, ts),
            )
        return self.get(iid)

    def update(self, item_id: str, changes: dict) -> dict | None:
        sets, params = [], []
        for key in ("title", "data", "sort", "active", "key"):
            if key in changes:
                value = changes[key]
                if key == "data":
                    value = _dumps(value)
                if key == "active":
                    value = int(bool(value))
                sets.append(f"{key} = ?")
                params.append(value)
        if sets:
            sets.append("updated_at = ?")
            params += [now_iso(), item_id]
            with transaction() as conn:
                conn.execute(f"UPDATE library_items SET {', '.join(sets)} WHERE id = ?", params)
        return self.get(item_id)

    def delete(self, item_id: str) -> None:
        with transaction() as conn:
            conn.execute("DELETE FROM library_items WHERE id = ?", (item_id,))

    def delete_demo(self) -> None:
        with transaction() as conn:
            conn.execute("DELETE FROM library_items WHERE is_demo = 1")

    def is_empty(self) -> bool:
        return get_connection().execute("SELECT COUNT(*) AS n FROM library_items").fetchone()["n"] == 0


# --------------------------------------------------------------------------- templates
class TemplateRepo:
    def _decode(self, row) -> dict:
        d = dict(row)
        d["inputs"] = _loads(d.get("inputs"), {})
        d["is_builtin"] = bool(d.get("is_builtin"))
        return d

    def list(self) -> list[dict]:
        rows = get_connection().execute("SELECT * FROM templates ORDER BY is_builtin DESC, updated_at DESC").fetchall()
        return [self._decode(r) for r in rows]

    def get(self, tid: str) -> dict | None:
        row = get_connection().execute("SELECT * FROM templates WHERE id = ?", (tid,)).fetchone()
        return self._decode(row) if row else None

    def create(self, name: str, description: str, project_type: str, inputs: dict, is_builtin: bool = False) -> dict:
        tid = new_id()
        ts = now_iso()
        with transaction() as conn:
            conn.execute(
                "INSERT INTO templates (id, name, description, project_type, inputs, is_builtin, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (tid, name, description, project_type, _dumps(inputs), int(is_builtin), ts, ts),
            )
        return self.get(tid)

    def update(self, tid: str, changes: dict) -> dict | None:
        sets, params = [], []
        for key in ("name", "description", "project_type", "inputs"):
            if key in changes:
                value = _dumps(changes[key]) if key == "inputs" else changes[key]
                sets.append(f"{key} = ?")
                params.append(value)
        if sets:
            sets.append("updated_at = ?")
            params += [now_iso(), tid]
            with transaction() as conn:
                conn.execute(f"UPDATE templates SET {', '.join(sets)} WHERE id = ?", params)
        return self.get(tid)

    def delete(self, tid: str) -> None:
        with transaction() as conn:
            conn.execute("DELETE FROM templates WHERE id = ?", (tid,))

    def delete_builtin(self) -> None:
        with transaction() as conn:
            conn.execute("DELETE FROM templates WHERE is_builtin = 1")


# --------------------------------------------------------------------------- settings
class SettingsRepo:
    def get_all(self) -> dict:
        rows = get_connection().execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: _loads(r["value"], None) for r in rows}

    def get(self, key: str, default: Any = None) -> Any:
        row = get_connection().execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return _loads(row["value"], default) if row else default

    def set_many(self, values: dict) -> dict:
        with transaction() as conn:
            for key, value in values.items():
                conn.execute(
                    "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                    (key, _dumps(value)),
                )
        return self.get_all()

    def next_proposal_number(self) -> str:
        prefix = self.get("proposal_prefix", "AHD")
        seq = int(self.get("proposal_seq", 1) or 1)
        self.set_many({"proposal_seq": seq + 1})
        year = now_iso()[:4]
        return f"{prefix}-{year}-{seq:03d}"


# --------------------------------------------------------------------------- uploads
class UploadRepo:
    def create(self, filename: str, mime: str, size: int, stored_name: str) -> dict:
        uid = stored_name.split(".")[0]
        with transaction() as conn:
            conn.execute(
                "INSERT INTO uploads (id, filename, mime, size, stored_name, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (uid, filename, mime, size, stored_name, now_iso()),
            )
        return {"id": uid, "url": f"/files/{stored_name}", "filename": filename}

    def get(self, uid: str) -> dict | None:
        return _row(get_connection().execute("SELECT * FROM uploads WHERE id = ?", (uid,)).fetchone())


clients = ClientRepo()
proposals = ProposalRepo()
library = LibraryRepo()
templates = TemplateRepo()
settings = SettingsRepo()
uploads = UploadRepo()
