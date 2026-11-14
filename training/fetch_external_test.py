# Copyright (c) 2026 Sankalp Gaonkar
"""Download the 152 external test photos listed in external_test_manifest.json (Wikimedia Commons, CC licences;
authors and licences are in the manifest) into external_test/.
Usage: python training/fetch_external_test.py [external_test]
"""
import json, os, sys, time, urllib.request
out = sys.argv[1] if len(sys.argv) > 1 else "external_test"
items = json.load(open(os.path.join(os.path.dirname(__file__), "external_test_manifest.json")))
for it in items:
    dst = os.path.join(out, it["file"])
    if os.path.exists(dst):
        continue
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    req = urllib.request.Request(it["download"], headers={"User-Agent": "EVP-demo-eval/1.0 (student project)"})
    with urllib.request.urlopen(req, timeout=60) as r, open(dst, "wb") as f:
        f.write(r.read())
    time.sleep(0.5)
print("done:", len(items), "photos in", out)
