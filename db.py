"""allofculture: core library over SQLite."""
import json, sqlite3, os

DB = os.path.join(os.path.dirname(__file__), "allofculture.db")

def connect(path=DB):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA busy_timeout = 5000")  # wait for locks instead of failing immediately
    return con

def add_node(con, type_, name, year=None, description=None, meta=None, qid=None):
    cur = con.execute(
        "INSERT INTO nodes(type,name,year,description,meta,qid) VALUES(?,?,?,?,?,?)",
        (type_, name, year, description, json.dumps(meta) if meta else None, qid))
    return cur.lastrowid

def get_node(con, name):
    return con.execute("SELECT * FROM nodes WHERE name=?", (name,)).fetchone()

def get_node_by_qid(con, qid):
    return con.execute("SELECT * FROM nodes WHERE qid=?", (qid,)).fetchone()

def add_edge(con, source, target, relation, weight=1.0, note=None,
             source_url=None, source_type=None, confidence=0.5, verified=0):
    """source/target may be node ids or names. Every edge is an attributed claim."""
    def resolve(x):
        if isinstance(x, int): return x
        row = get_node(con, x)
        if not row: raise ValueError(f"unknown node: {x}")
        return row["id"]
    s, t = resolve(source), resolve(target)
    con.execute(
        "INSERT OR IGNORE INTO edges(source_id,target_id,relation,weight,note,"
        "source,source_type,confidence,verified) VALUES(?,?,?,?,?,?,?,?,?)",
        (s, t, relation, weight, note, source_url, source_type, confidence, verified))

def neighbors(con, name, relation=None, direction="both"):
    n = get_node(con, name)
    if not n: return []
    q = ("SELECT n.*, e.source_id, e.target_id, e.relation, e.weight, e.note, e.source, e.source_type, "
         "e.confidence, e.verified FROM edges e "
         "JOIN nodes n ON n.id = e.target_id WHERE e.source_id=?")
    p = [n["id"]]
    if direction in ("both", "in"):
        q += " UNION ALL SELECT n.*, e.source_id, e.target_id, e.relation, e.weight, e.note, e.source, e.source_type, e.confidence, e.verified FROM edges e JOIN nodes n ON n.id=e.source_id WHERE e.target_id=?"
        p.append(n["id"])
    rows = con.execute(q, p).fetchall()
    if relation:
        rows = [r for r in rows if r["relation"] == relation]
    return rows

def export(con):
    nodes = [dict(r) for r in con.execute("SELECT * FROM nodes ORDER BY id")]
    edges = [dict(r) for r in con.execute("SELECT * FROM edges ORDER BY id")]
    return {"nodes": nodes, "edges": edges}

def stats(con):
    return {
        "nodes": con.execute("SELECT COUNT(*) c FROM nodes").fetchone()["c"],
        "edges": con.execute("SELECT COUNT(*) c FROM edges").fetchone()["c"],
        "verified": con.execute("SELECT COUNT(*) c FROM edges WHERE verified=1").fetchone()["c"],
        "relations": [r["relation"] for r in con.execute(
            "SELECT relation, COUNT(*) c FROM edges GROUP BY relation ORDER BY c DESC")],
    }
