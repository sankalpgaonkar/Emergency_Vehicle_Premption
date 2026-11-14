# Copyright (c) 2026 Sankalp Gaonkar

"""Near-duplicate-filtered re-split of the Roboflow 'Emergency vehicle' dataset.
Groups near-duplicate images (difference-hash, 256 bits) with union-find and
assigns whole groups to train/val/test so no near-duplicate crosses splits."""
import sys, json, random, shutil
from pathlib import Path
import numpy as np
from PIL import Image
SRC = Path(sys.argv[1]); OUT = Path(sys.argv[2]); THR = int(sys.argv[3]) if len(sys.argv) > 3 else 20
def dhash(p, n=16):
    im = Image.open(p).convert("L").resize((n + 1, n), Image.BILINEAR)
    a = np.asarray(im, dtype=np.int16)
    return (a[:, 1:] > a[:, :-1]).flatten()
items = []
for split in ("train", "valid", "test"):
    for img in sorted((SRC / split / "images").glob("*")):
        lab = SRC / split / "labels" / (img.stem + ".txt")
        cls = set()
        if lab.exists():
            for line in lab.read_text().splitlines():
                if line.strip():
                    cls.add(int(line.split()[0]))
        items.append({"img": img, "lab": lab, "orig": split, "cls": sorted(cls)})
H = np.stack([dhash(it["img"]) for it in items])
n = len(items)
par = list(range(n))
def f(x):
    while par[x] != x:
        par[x] = par[par[x]]; x = par[x]
    return x
D = (H[:, None, :] != H[None, :, :]).sum(-1)
pairs = np.argwhere(np.triu(D <= THR, 1))
for i, j in pairs:
    a, b = f(i), f(j)
    if a != b: par[a] = b
groups = {}
for i in range(n): groups.setdefault(f(i), []).append(i)
# cross-split leakage in the ORIGINAL split
orig_leak = {"test_with_train_dup": 0, "valid_with_train_dup": 0}
tr = [i for i in range(n) if items[i]["orig"] == "train"]
for i in range(n):
    if items[i]["orig"] in ("test", "valid"):
        if D[i, tr].min() <= THR:
            orig_leak[("test" if items[i]["orig"] == "test" else "valid") + "_with_train_dup"] += 1
G = list(groups.values())
rng = random.Random(42)
rng.shuffle(G)
G.sort(key=lambda g: -len(g))     # place big groups first (greedy balancing)
target = {"train": 0.70, "val": 0.15, "test": 0.15}
cnt = {k: 0 for k in target}; ccls = {k: [0, 0, 0] for k in target}
tot_cls = [0, 0, 0]
for it in items:
    for c in it["cls"]: tot_cls[c] += 1
assign = {}
for g in G:
    gcls = [0, 0, 0]
    for i in g:
        for c in items[i]["cls"]: gcls[c] += 1
    # choose split with the largest deficit (images + rare-class instances)
    def deficit(k):
        d = target[k] * n - cnt[k]
        for c in (1, 2):
            if gcls[c]: d += 3 * (target[k] * tot_cls[c] - ccls[k][c])
        return d
    k = max(target, key=deficit)
    for i in g:
        assign[i] = k; cnt[k] += 1
        for c in items[i]["cls"]: ccls[k][c] += 1
if OUT.exists(): shutil.rmtree(OUT)
for k in target:
    (OUT / k / "images").mkdir(parents=True); (OUT / k / "labels").mkdir(parents=True)
for i, it in enumerate(items):
    k = assign[i]
    shutil.copy2(it["img"], OUT / k / "images" / it["img"].name)
    if it["lab"].exists(): shutil.copy2(it["lab"], OUT / k / "labels" / it["lab"].name)
(OUT / "data.yaml").write_text(f"path: {OUT.resolve()}\ntrain: train/images\nval: val/images\ntest: test/images\nnc: 3\nnames: ['ambulance', 'fire brigade', 'police']\n")
# check new split leakage
idx = {k: [i for i in range(n) if assign[i] == k] for k in target}
new_leak = int(sum(1 for i in idx["test"] if D[i, idx["train"]].min() <= THR)) if idx["test"] else 0
rep = {"images": n, "threshold_bits": THR, "hash": "dHash 16x16 (256 bits)", "groups": len(G),
       "largest_groups": sorted([len(g) for g in G], reverse=True)[:10],
       "original_split": {s: sum(1 for it in items if it["orig"] == s) for s in ("train", "valid", "test")},
       "original_leakage": orig_leak,
       "new_split_images": cnt, "new_split_instances_by_class_images": ccls,
       "new_test_images_with_train_near_duplicate": new_leak,
       "class_images_total": tot_cls, "seed": 42,
       "assignment": {items[i]["img"].name: assign[i] for i in range(n)}}
(OUT / "split_report.json").write_text(json.dumps(rep, indent=1))
print(json.dumps({k: v for k, v in rep.items() if k != "assignment"}, indent=1))
