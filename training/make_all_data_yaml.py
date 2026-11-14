# Copyright (c) 2026 Sankalp Gaonkar
"""Build datasets_all/: every image of the filtered split in 'train' (for the deployment model, run C).
'val' repeats the filtered val images only so Ultralytics can run; its scores are NOT an evaluation.
Usage: python training/make_all_data_yaml.py datasets_clean datasets_all
"""
import os, shutil, sys
src, dst = sys.argv[1], sys.argv[2]
for sub in ("train/images", "train/labels", "val/images", "val/labels"):
    os.makedirs(os.path.join(dst, sub), exist_ok=True)
for split in ("train", "val", "test"):
    for kind in ("images", "labels"):
        d = os.path.join(src, split, kind)
        for f in os.listdir(d):
            shutil.copy(os.path.join(d, f), os.path.join(dst, "train", kind, f))
            if split == "val":
                shutil.copy(os.path.join(d, f), os.path.join(dst, "val", kind, f))
open(os.path.join(dst, "data.yaml"), "w").write(f"path: {os.path.abspath(dst)}\ntrain: train/images\nval: val/images\nnc: 3\n"
                                                "names: ['ambulance', 'fire brigade', 'police']\n")
print("done", dst)
