#!/usr/bin/env python3
"""Export the SQLite graph to web/data.json for static (serverless) deployment.

The whole graph is ~1 MB, so the frontend loads it once and does everything
client-side (expand, path-finding, search). Run after any DB change:
    python3 export_static.py
"""
import json, os
import db

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(ROOT, "web", "data.json")

con = db.connect()
data = db.export(con)
data["stats"] = db.stats(con)

with open(OUT, "w") as f:
    json.dump(data, f, separators=(",", ":"))
print(f"wrote {OUT} ({os.path.getsize(OUT)/1024:.0f} KB, "
      f"{len(data['nodes'])} nodes, {len(data['edges'])} edges)")
