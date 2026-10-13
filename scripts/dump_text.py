"""Render proposals in the smoke DB as plain text for proofreading."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.data import repositories as repo

def render(doc):
    L = []
    c = doc["cover"]; L.append(f"# {c['title']} | {c['client']} | {c['subtitle']} | {c['date']}")
    for s in doc["sections"]:
        L.append(f"\n## {s['title']} — {s['subtitle']}")
        for b in s["blocks"]:
            t = b["type"]
            if t in ("paragraph", "lead"): L.append(f"[{t}] {b['text']}")
            elif t == "callout": L.append(f"[callout:{b['label']}] {b['text']}")
            elif t in ("cards",): L += [f"  * {i['title']}: {i['text']}" for i in b["items"]]
            elif t == "list": L.append(f"  [list {b.get('title','')}]"); L += [f"  - {i}" for i in b["items"]]
            elif t == "objectives": L += [f"  ◎ {i['title']} → {i['text']} | قياس: {i['measure']} | مستهدف: {i['target']}" for i in b["items"]]
            elif t == "services":
                for g in b["groups"]: L.append(f"  [{g['title']}] " + " / ".join(i['title'] for i in g['items']))
            elif t == "phases":
                for i in b["items"]: L.append(f"  ▸ {i['title']} ({i['period']}): {i['goal']} | " + "؛ ".join(i['activities']))
            elif t == "deliverables": L += [f"  ▪ {r['title']} | {r['description']} | {r['qty']} {r['unit']} | {r['timing']}" for r in b["rows"]]
            elif t == "timeline": L += [f"  ⏱ {r['phase']} | {r['activity']} | +{r['offset']}d {r['days']}d | {r['owner']}" for r in b["rows"]]; L.append("  milestones: " + ", ".join(f"{m['label']}@{m['offset']}" for m in b["milestones"]))
            elif t == "team": L += [f"  👤 {m['role']} ({m['role_en']}) x{m['count']}: " + "؛ ".join(m['responsibilities']) for m in b["members"]]
            elif t == "kpis": L += [f"  📈 {k['name']} ({k['name_en']}) | {k['target']} | {k['frequency']}" for k in b["items"]]
            elif t == "risks": L += [f"  ⚠ {r['risk']} | {r['likelihood']}/{r['impact']} | {r['mitigation']}" for r in b["rows"]]
            elif t == "table": L += [f"  ▤ " + " | ".join(str(r.get(c['key'],'')) for c in b['columns']) for r in b["rows"]]
            elif t == "steps": L += [f"  {n+1}. {i['title']}: {i['text']}" for n, i in enumerate(b["items"])]
            elif t == "stats": L.append("  " + " · ".join(f"{i['value']} {i['label']}" for i in b["items"]))
            else: L.append(f"  [{t}]")
    return "\n".join(L)

out = []
for p in repo.proposals.list():
    full = repo.proposals.get(p["id"])
    out.append(render(full["doc"]) + "\n\nMISSING: " + ", ".join(m["label"] for m in full["meta"]["missing"]))
Path(sys.argv[1]).write_text("\n\n==========================\n\n".join(out), encoding="utf-8")
print("written")
