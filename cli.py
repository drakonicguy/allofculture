#!/usr/bin/env python3
"""allofculture CLI. Usage:
  python3 cli.py add-node <type> <name> [--year N] [--desc "..."]
  python3 cli.py add-edge <source> <target> <relation> [--note "..."] [--src URL] [--src-type T] [--conf 0..1] [--verified]
  python3 cli.py neighbors <name> [--relation R]
  python3 cli.py path <from> <to>
  python3 cli.py stats
  python3 cli.py export [out.json]
  python3 cli.py serve [port]
"""
import sys, json, argparse
import db

def bfs(con, a, b):
    from collections import deque
    start = db.get_node(con, a); goal = db.get_node(con, b)
    if not start or not goal: return None
    prev = {start["id"]: None}; rel = {}
    dq = deque([start["id"]])
    while dq:
        cur = dq.popleft()
        if cur == goal["id"]: break
        for r in db.neighbors(con, con.execute("SELECT name FROM nodes WHERE id=?", (cur,)).fetchone()["name"]):
            if r["id"] not in prev:
                prev[r["id"]] = cur; rel[r["id"]] = r["relation"]; dq.append(r["id"])
    if goal["id"] not in prev: return None
    path = []; cur = goal["id"]
    while cur is not None:
        path.append(cur); cur = prev[cur]
    path.reverse()
    out = []
    for i, nid in enumerate(path):
        nm = con.execute("SELECT name FROM nodes WHERE id=?", (nid,)).fetchone()["name"]
        out.append(nm)
        if i < len(path)-1:
            out.append(f"  --{rel[path[i+1]]}--> ")
    return "".join(out)

def main():
    p = argparse.ArgumentParser(prog="cli.py")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add-node"); a.add_argument("type"); a.add_argument("name")
    a.add_argument("--year", type=int); a.add_argument("--desc")
    b = sub.add_parser("add-edge"); b.add_argument("source"); b.add_argument("target"); b.add_argument("relation")
    b.add_argument("--note"); b.add_argument("--src"); b.add_argument("--src-type")
    b.add_argument("--conf", type=float, default=0.5); b.add_argument("--verified", action="store_true")
    c = sub.add_parser("neighbors"); c.add_argument("name"); c.add_argument("--relation")
    d = sub.add_parser("path"); d.add_argument("from", metavar="FROM"); d.add_argument("to")
    sub.add_parser("stats"); sub.add_parser("export")
    args = p.parse_args()
    con = db.connect()
    if args.cmd == "add-node":
        nid = db.add_node(con, args.type, args.name, args.year, args.desc); con.commit()
        print(f"added node #{nid}: {args.name}")
    elif args.cmd == "add-edge":
        db.add_edge(con, args.source, args.target, args.relation, note=args.note,
                    source_url=args.src, source_type=args.src_type,
                    confidence=args.conf, verified=1 if args.verified else 0)
        con.commit()
        print(f"added edge: {args.source} --{args.relation}--> {args.target}")
    elif args.cmd == "neighbors":
        for r in db.neighbors(con, args.name, args.relation):
            v = "✓" if r["verified"] else "·"
            print(f"{v} {r['name']}  [{r['relation']}]  conf={r['confidence']}  {r['note'] or ''}")
            if r["source"]: print(f"      src: {r['source']} ({r['source_type']})")
    elif args.cmd == "path":
        print(bfs(con, getattr(args, "from"), args.to) or "no path found")
    elif args.cmd == "stats":
        print(json.dumps(db.stats(con), indent=2))
    elif args.cmd == "export":
        print(json.dumps(db.export(con), indent=2))

if __name__ == "__main__":
    main()
