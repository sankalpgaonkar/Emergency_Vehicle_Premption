# Copyright (c) 2026 Sankalp Gaonkar
"""Dataset audit: where do the images come from, and how similar is the test split to the training split?

Usage: python training/dataset_audit.py project/datasets/emergency_vehicles datasets_clean
Prints JSON: images per source family (from Roboflow file names) and class, and for each split the distribution of
the Hamming distance (256-bit dHash) from every test image to its nearest training image.
"""
import collections, glob, json, os, re, sys
import numpy as np
from PIL import Image

FAMILY_RE = re.compile(r"[-_ ]?\(?\d+\)?-?$")


def dhash(p, n=16):
    a = np.asarray(Image.open(p).convert("L").resize((n + 1, n), Image.BILINEAR), dtype=np.int16)
    return np.packbits((a[:, 1:] > a[:, :-1]).flatten())


def stem(p):
    return re.sub(r"_(jpg|jpeg|png)\.rf\..*", "", os.path.basename(p))


def family(p):
    f = FAMILY_RE.sub("", stem(p))
    return f


def classes(img):
    lab = img.replace("/images/", "/labels/").rsplit(".", 1)[0] + ".txt"
    out = set()
    if os.path.exists(lab):
        for line in open(lab):
            if line.strip():
                out.add(int(line.split()[0]))
    return out


def nearest(test_dir, train_dir):
    te = sorted(glob.glob(test_dir + "/*.*")); tr = sorted(glob.glob(train_dir + "/*.*"))
    hte = np.array([dhash(f) for f in te]); htr = np.array([dhash(f) for f in tr])
    d = np.unpackbits(hte[:, None, :] ^ htr[None, :, :], axis=2).sum(2).min(1)
    return {"test_images": len(te), "percentiles_bits": dict(zip(["min", "p10", "p25", "median", "p75"],
                                                                 [float(x) for x in np.percentile(d, [0, 10, 25, 50, 75])])),
            "within_bits": {str(t): int((d <= t).sum()) for t in (20, 30, 40, 50, 60)}}


def main():
    src = sys.argv[1]
    names = ["ambulance", "fire brigade", "police"]
    imgs = sorted(glob.glob(src + "/*/images/*"))
    fam = collections.defaultdict(collections.Counter)
    for p in imgs:
        f = family(p)
        key = f if sum(1 for q in imgs if family(q) == f) >= 20 else "(single web images)"
        fam[key]["images"] += 1
        for c in classes(p):
            fam[key][names[c]] += 1
    rep = {"images": len(imgs), "source_families": {k: dict(v) for k, v in sorted(fam.items(), key=lambda kv: -kv[1]["images"])}}
    rep["original_split_test_vs_train"] = nearest(src + "/test/images", src + "/train/images")
    if len(sys.argv) > 2:
        rep["clean_split_test_vs_train"] = nearest(sys.argv[2] + "/test/images", sys.argv[2] + "/train/images")
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
