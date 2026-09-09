#!/usr/bin/env python3
"""Tiny zero-dependency HTTP server: serves the web UI + JSON API over SQLite."""
import json, os, sqlite3
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import db

ROOT = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(ROOT, "web")

# Starting node for the explorer (Wikidata QID). Falls back to the highest-degree node.
START_QID = "Q8272"  # The Epic of Gilgamesh

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, path):
        path = os.path.normpath(os.path.join(WEB, path.lstrip("/")))
        if not path.startswith(WEB): return self._json({"error": "forbidden"}, 403)
        if not os.path.isfile(path): return self._json({"error": "not found"}, 404)
        ctype = "text/html" if path.endswith(".html") else \
                "application/javascript" if path.endswith(".js") else \
                "text/css" if path.endswith(".css") else "application/octet-stream"
        body = open(path, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        con = db.connect()
        if u.path == "/" or u.path == "/index.html":
            return self._file("index.html")
        if u.path == "/data.json":
            return self._file("data.json")
        if u.path.startswith("/web/"):
            return self._file(u.path[5:])
        if u.path == "/api/graph":
            return self._json(db.export(con))
        if u.path == "/api/stats":
            return self._json(db.stats(con))
        if u.path == "/api/names":
            names = [r["name"] for r in con.execute("SELECT name FROM nodes ORDER BY name")]
            return self._json({"names": names})
        if u.path == "/api/start":
            row = None
            if START_QID:
                row = con.execute("SELECT name FROM nodes WHERE qid=?", (START_QID,)).fetchone()
            if not row:
                row = con.execute("""
                    SELECT n.name FROM nodes n
                    LEFT JOIN edges e ON e.source_id=n.id OR e.target_id=n.id
                    GROUP BY n.id ORDER BY COUNT(e.id) DESC LIMIT 1""").fetchone()
            name = row["name"]
            return self._json({"node": dict(db.get_node(con, name)),
                               "neighbors": [dict(r) for r in db.neighbors(con, name)]})
        if u.path == "/api/node":
            q = parse_qs(u.query)
            name = q.get("name", [""])[0]
            return self._json({"node": dict(db.get_node(con, name)) if db.get_node(con, name) else None,
                               "neighbors": [dict(r) for r in db.neighbors(con, name)]})
        if u.path == "/api/path":
            q = parse_qs(u.query)
            a, b = q.get("from", [""])[0], q.get("to", [""])[0]
            return self._json({"path": _bfs(con, a, b)})
        return self._json({"error": "not found"}, 404)

def _bfs(con, a, b):
    from collections import deque
    start = db.get_node(con, a); goal = db.get_node(con, b)
    if not start or not goal: return None
    prev = {start["id"]: None}; rel = {}
    dq = deque([start["id"]])
    while dq:
        cur = dq.popleft()
        if cur == goal["id"]: break
        nm = con.execute("SELECT name FROM nodes WHERE id=?", (cur,)).fetchone()["name"]
        for r in db.neighbors(con, nm):
            if r["id"] not in prev:
                prev[r["id"]] = cur; rel[r["id"]] = r["relation"]; dq.append(r["id"])
    if goal["id"] not in prev: return None
    path = []; cur = goal["id"]
    while cur is not None: path.append(cur); cur = prev[cur]
    path.reverse()
    return [{"id": nid, "name": con.execute("SELECT name FROM nodes WHERE id=?", (nid,)).fetchone()["name"],
             "relation": rel.get(nid)} for nid in path]

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"allofculture explorer -> http://localhost:{port}")
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()
