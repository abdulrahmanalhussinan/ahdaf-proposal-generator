"""Quick smoke run of the generator against a fresh database (prints a compact summary)."""
import json, os, sys, tempfile
from pathlib import Path
os.environ["AHDAF_DATA_DIR"] = tempfile.mkdtemp(prefix="ahdaf-smoke-")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.data import seed
from app.data import repositories as repo
seed.ensure_seeded(with_demo=True)
out = []
for p in repo.proposals.list():
    full = repo.proposals.get(p["id"])
    out.append({"number": p["number"], "client": p["client_name"], "project": p["project_name"], "type": p["type_label"],
                "missing": [m["label"] for m in full["meta"]["missing"]],
                "sections": [(s["title"], [b["type"] for b in s["blocks"]]) for s in full["doc"]["sections"]]})
Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
first = repo.proposals.get(repo.proposals.list()[-1]["id"])
Path(sys.argv[2]).write_text(json.dumps(first["doc"], ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", len(out))
import subprocess
