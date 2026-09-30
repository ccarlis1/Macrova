"""Diff two compare.py outputs and map every disagreement to a root-cause cluster.

Usage (from repo root):
    .venv/bin/python evaluation/harness/diff_results.py [--base REF_OR_PATH] [--new PATH]

--base  a git ref (default HEAD) whose committed results/compare.json is the baseline,
        or a path to a saved compare.json
--new   the fresh compare.json (default evaluation/harness/results/compare.json)

Clusters come from the "### C<n>" sections of evaluation/reports/benchmark_failure_analysis.md
(their "**Scenarios:**" line; "**Status:** fixed" marks a closed cluster).
Exits 1 if any scenario regressed, a disagreement maps to no cluster, or a
fixed cluster still has disagreements; otherwise 0.
"""
import argparse, json, re, subprocess, sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REL = "evaluation/harness/results/compare.json"
REPORT = REPO / "evaluation/reports/benchmark_failure_analysis.md"
AGREE = {"MATCH", "ACCEPTABLE"}


def load(src):
    p = Path(src)
    if p.is_file():
        return json.load(open(p))
    out = subprocess.check_output(["git", "show", f"{src}:{REL}"], cwd=REPO)
    return json.loads(out)


def clusters():
    """{cluster: (set of scenario ids, fixed?)} parsed from the failure-analysis report."""
    res, cur = {}, None
    for line in REPORT.read_text().splitlines():
        m = re.match(r"^### (C\w+)\.", line)
        if m:
            cur = m.group(1); res[cur] = [set(), False]; continue
        if line.startswith("## "):
            cur = None
        if not cur:
            continue
        if "**Status:** fixed" in line:
            res[cur][1] = True
        m = re.search(r"\*\*Scenarios?:\*\*(.*)", line)
        if m:
            ids = res[cur][0]
            text = m.group(1)
            for a, b in re.findall(r"\b(\d{3})[–-](\d{3})\b", text):
                ids.update(f"MB-{n:03d}" for n in range(int(a), int(b) + 1))
            text = re.sub(r"\b\d{3}[–-]\d{3}\b", "", text)
            ids.update(f"MB-{n}" for n in re.findall(r"(?:MB-|\b|/)(\d{3})\b", text))
    return {k: (v[0], v[1]) for k, v in res.items()}


def summary(rows):
    c = Counter(r["status"] for r in rows)
    return c["MATCH"], c["ACCEPTABLE"], sum(v for k, v in c.items() if k not in AGREE), len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="HEAD")
    ap.add_argument("--new", default=str(REPO / REL))
    a = ap.parse_args()
    old, new = load(a.base), load(a.new)
    O, N = {r["id"]: r for r in old}, {r["id"]: r for r in new}

    (om, oa, od, on), (nm, na, nd, nn) = summary(old), summary(new)
    print(f"Scorecard ({a.base} -> new)")
    print(f"  exact        {om} -> {nm}")
    print(f"  acceptable   {oa} -> {na}")
    print(f"  disagreement {od} -> {nd}")
    print(f"  scenarios    {on} -> {nn}")

    fixed, regressed, changed = [], [], []
    for sid in sorted(set(O) | set(N)):
        o, n = O.get(sid), N.get(sid)
        if not o:
            changed.append(f"{sid}: NEW  got={n['got']} ({n['status']})"); continue
        if not n:
            changed.append(f"{sid}: REMOVED"); continue
        if (o["status"], o["got"]) == (n["status"], n["got"]):
            continue
        line = f"{sid}: {o['got']} ({o['status']}) -> {n['got']} ({n['status']})  exp={n['expected']}"
        if o["status"] not in AGREE and n["status"] in AGREE:
            fixed.append(line)
        elif o["status"] in AGREE and n["status"] not in AGREE:
            regressed.append(line)
        else:
            changed.append(line)
    for title, items in (("Fixed", fixed), ("REGRESSED", regressed), ("Other changes", changed)):
        print(f"\n{title}: {len(items)}")
        for x in items:
            print("  " + x)

    cl = clusters()
    by, unmapped, stale = {}, [], []
    for r in new:
        if r["status"] in AGREE:
            continue
        hit = [k for k, (ids, _) in cl.items() if r["id"] in ids]
        if not hit:
            unmapped.append(r); continue
        for k in hit:
            by.setdefault(k, []).append(r["id"])
            if cl[k][1]:
                stale.append(f"{r['id']} ({k} is marked fixed)")
    print("\nOpen disagreements by cluster:")
    for k in cl:
        ids = by.get(k, [])
        tag = " [fixed]" if cl[k][1] else ""
        print(f"  {k}{tag}: {len(ids)}" + (f"  {', '.join(ids)}" if ids else ""))
    print(f"\nUnmapped disagreements: {len(unmapped)}")
    for r in unmapped:
        print(f"  {r['id']} exp={r['expected']} got={r['got']} {r['status']}")
        for v in r["viol"][:3]:
            print(f"      V: {v}")
    if stale:
        print(f"\nDisagreements in fixed clusters: {len(stale)}")
        for s in stale:
            print("  " + s)

    return 1 if (regressed or unmapped or stale) else 0


if __name__ == "__main__":
    sys.exit(main())
