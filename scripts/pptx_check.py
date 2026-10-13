"""Dev helper: build the PPTX for a proposal straight from the database (no server)."""
import os, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from app.data import repositories as repo
from app.exporters.pptx_export import build_pptx
match, out = sys.argv[1], pathlib.Path(sys.argv[2])
p = next(x for x in repo.proposals.list() if match in x["project_name"])
full = repo.proposals.get(p["id"])
out.write_bytes(build_pptx(full, repo.settings.get_all()))
print("written", out, out.stat().st_size)
