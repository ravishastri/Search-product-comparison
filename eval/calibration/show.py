import json, re, sys
from pathlib import Path
sample = json.load(open("eval/calibration/sample.json"))
lo, hi = int(sys.argv[1]), int(sys.argv[2])
STOP = set("the a an and or of to in on for with is are was be by at as from that this it its their linear plan plans".split())
for s in sample[lo:hi]:
    print(f"\n### {s['id']}. {s['claim']}\n  judge: {s['judge_verdict']} | evidence: {s['judge_evidence'][:140]}")
    terms = [w for w in re.findall(r"\$?\d[\d,.]*|[A-Za-z][A-Za-z\-]{3,}", s['claim']) if w.lower() not in STOP][:6]
    for f in s['cache_files'][:2]:
        t = Path(f).read_text()
        hits = [m.start() for m in re.finditer(re.escape(terms[0]), t, re.I)] if terms else []
        best = max(range(len(terms)), key=lambda k: len(re.findall(re.escape(terms[k]), t, re.I))) if terms else None
        pos = [m.start() for m in re.finditer(re.escape(terms[best]), t, re.I)] if best is not None else []
        print(f"  [{Path(f).name[:8]}] len={len(t)} terms={terms[:4]}")
        for p in pos[:2]:
            print("    ...", " ".join(t[max(0,p-160):p+200].split()), "...")
        if not pos: print("    (no term match in this page)")
