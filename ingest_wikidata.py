#!/usr/bin/env python3
"""Populate the graph from Wikidata (attributed, citable).

Usage:
  python3 ingest_wikidata.py "James Brown" [--depth 1] [--limit 200]
  python3 ingest_wikidata.py Q26963 [--depth 1]

Every claim is stamped source=<wikidata item URL>, source_type=wikidata.
"""
import json, sys, time, urllib.parse, urllib.request
import db

UA = {"User-Agent": "allofculture/0.1 (personal research graph; contact: local)"}
SPARQL = "https://query.wikidata.org/sparql"
SEARCH = "https://www.wikidata.org/w/api.php"
REQUEST_DELAY = 5  # seconds between requests to Wikidata (user cap: 1 req/5s)


def _throttle():
    time.sleep(REQUEST_DELAY)


def _retry(fn, tries=5):
    for i in range(tries):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code < 500 and e.code != 429:
                raise
            time.sleep(1.5 * (i + 1))
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1.5 * (i + 1))
    raise RuntimeError("wikidata unreachable after retries")

# Wikidata property (bare number) -> our relation name (edge: QID --relation--> value)
PROPS = {
    "P144":  "based_on",        # based on
    "P941":  "inspired_by",     # inspired by
    "P4969": "has_derivative",  # derivative work
    "P155":  "follows",
    "P156":  "followed_by",
    "P361":  "part_of",
    "P50":   "authored_by",
    "P170":  "created_by",
    "P175":  "performed_by",
    "P463":  "member_of",
    "P279":  "subclass_of",
}

# Reverse direction: things that point AT this node. property -> our relation name
REVERSE_PROPS = {
    "P144":  "is_basis_for",     # X based_on this  -> this is the basis of X
    "P941":  "inspired",         # X inspired_by this
    "P4969": "is_derivative_of", # X is a derivative of this
    "P155":  "followed_by",      # X follows this
    "P156":  "follows",          # X followed_by this
    "P361":  "has_part",         # X part_of this
    "P50":   "authored",         # X authored_by this
    "P170":  "created",          # X created_by this
    "P175":  "performed",        # X performed_by this
    "P463":  "has_member",       # X member_of this
    "P279":  "has_subclass",     # X subclass_of this
}

# relation -> its opposite phrasing, so we don't store the same claim twice
# (e.g. "authored_by" and "authored" are two phrasings of one fact)
REVERSE_REL = {}
for _p, _fwd in PROPS.items():
    _rev = REVERSE_PROPS[_p]
    REVERSE_REL[_fwd] = _rev
    REVERSE_REL[_rev] = _fwd

# instance-of (P31) QID -> our node type
TYPES = {
    "Q5": "person", "Q1886349": "band", "Q215380": "band",
    "Q43229": "organization", "Q4830453": "organization",
    "Q6256": "place", "Q515": "place", "Q486972": "place",
    "Q8502": "place", "Q23413": "place", "Q34442": "place",
    "Q33506": "place", "Q3918": "place", "Q35127": "place",
    "Q16970": "place", "Q811979": "place", "Q41176": "place",
    "Q1656682": "event", "Q1190554": "event",
    "Q571": "work", "Q7725634": "work", "Q13442814": "work",
    "Q11424": "work", "Q386724": "work", "Q7397": "work",
    "Q3305213": "work", "Q838948": "work", "Q15416": "work",
    "Q134556": "work", "Q2188189": "work", "Q207628": "work",
    "Q16521": "concept", "Q11173": "concept", "Q12136": "concept",
    "Q7187": "concept", "Q1013526": "concept",
    "Q4167410": None, "Q4167836": None, "Q13406463": None,  # skip
}

def _get(url, params=None):
    if params: url += "?" + urllib.parse.urlencode(params)
    def go():
        req = urllib.request.Request(url, headers=UA)
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode())
    out = _retry(go)
    _throttle()
    return out

def _sparql(q):
    data = urllib.parse.urlencode({"query": q, "format": "json"}).encode()
    def go():
        req = urllib.request.Request(SPARQL, data=data, headers={**UA, "Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    j = _retry(go)
    _throttle()
    return [b for b in j["results"]["bindings"]]

def resolve_qid(name):
    j = _get(SEARCH, {"action": "wbsearchentities", "search": name, "language": "en",
                      "format": "json", "limit": 8})
    hits = j.get("search", [])
    if not hits: return None
    # Prefer hits whose description suggests a cultural work (play/film/painting/...)
    WORK_HINTS = ("play", "film", "movie", "painting", "song", "book", "novel",
                  "album", "work", "tragedy", "comedy", "poem", "series", "band",
                  "artist", "musician", "painter", "writer", "director")
    for h in hits:
        desc = (h.get("description") or "").lower()
        if any(w in desc for w in WORK_HINTS):
            return h["id"]
    return hits[0]["id"]

def fetch_node(qid):
    q = f"""SELECT ?type ?typeLabel ?label ?desc WHERE {{
      wd:{qid} wdt:P31 ?type .
      wd:{qid} rdfs:label ?label .
      OPTIONAL {{ wd:{qid} schema:description ?desc . }}
      FILTER(lang(?label)="en") FILTER(lang(?desc)="en")
    }}"""
    rows = _sparql(q)
    if not rows: return None
    r = rows[0]
    types = [b["type"]["value"].split("/")[-1] for b in rows]
    ntype = next((TYPES[t] for t in types if TYPES.get(t)), "work")
    if ntype is None: return None  # skip disambig/category/list
    return {"name": r["label"]["value"], "type": ntype,
            "desc": r.get("desc", {}).get("value")}

def fetch_relations(qid):
    plist = " ".join("wdt:" + p for p in PROPS)
    q = f"""SELECT ?prop ?value ?valueLabel WHERE {{
      VALUES ?prop {{ {plist} }}
      wd:{qid} ?prop ?value .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}"""
    out = []
    for b in _sparql(q):
        prop = b["prop"]["value"].split("/")[-1]          # e.g. P144
        rel = PROPS.get(prop)
        if not rel: continue
        val = b["value"]["value"]
        if not val.startswith("http://www.wikidata.org/entity/Q"): continue
        out.append({"qid": val.split("/")[-1], "relation": rel,
                    "label": b.get("valueLabel", {}).get("value", "")})
    return out

def fetch_reverse_relations(qid):
    plist = " ".join("wdt:" + p for p in REVERSE_PROPS)
    q = f"""SELECT ?prop ?value ?valueLabel WHERE {{
      VALUES ?prop {{ {plist} }}
      ?value ?prop wd:{qid} .
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}"""
    out = []
    for b in _sparql(q):
        prop = b["prop"]["value"].split("/")[-1]
        rel = REVERSE_PROPS.get(prop)
        if not rel: continue
        val = b["value"]["value"]
        if not val.startswith("http://www.wikidata.org/entity/Q"): continue
        out.append({"qid": val.split("/")[-1], "relation": rel,
                    "label": b.get("valueLabel", {}).get("value", "")})
    return out

def ingest(con, qid, depth=0, limit=200, seen=None, count=None, qid_to_id=None):
    seen = seen or set()
    count = count or [0]
    qid_to_id = qid_to_id or {}
    if qid in seen or count[0] >= limit: return
    seen.add(qid)
    info = fetch_node(qid)
    if not info: return
    existing = db.get_node_by_qid(con, qid)
    if existing:
        nid = existing["id"]
    else:
        # Dedup against qid-less nodes (e.g. seed data): if a node with the same
        # name already exists and has no qid, backfill the qid instead of duplicating.
        by_name = db.get_node(con, info["name"])
        if by_name and by_name["qid"] is None:
            con.execute("UPDATE nodes SET qid=? WHERE id=?", (qid, by_name["id"]))
            nid = by_name["id"]
            print(f"  [backfill] {info['name']} -> {qid} (node #{nid})")
        else:
            nid = db.add_node(con, info["type"], info["name"], description=info["desc"], qid=qid)
            count[0] += 1
            print(f"  [{count[0]}/{limit}] {info['name']} ({info['type']})")
    qid_to_id[qid] = nid
    for r in fetch_relations(qid) + fetch_reverse_relations(qid):
        if depth > 0:
            ingest(con, r["qid"], depth-1, limit, seen, count, qid_to_id)
        if r["qid"] in qid_to_id:
            t = qid_to_id[r["qid"]]
            rev = REVERSE_REL.get(r["relation"])
            if rev and con.execute("SELECT 1 FROM edges WHERE source_id=? AND target_id=? AND relation=?",
                                   (t, nid, rev)).fetchone():
                continue  # the reverse phrasing of this claim is already stored
            db.add_edge(con, nid, t, r["relation"],
                        source_url=f"https://www.wikidata.org/wiki/{qid}",
                        source_type="wikidata", confidence=0.7, verified=0)
    return nid

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("seed", help="name or QID to start from")
    p.add_argument("--depth", type=int, default=1)
    p.add_argument("--limit", type=int, default=200)
    args = p.parse_args()
    qid = args.seed if args.seed.startswith("Q") else resolve_qid(args.seed)
    if not qid:
        print("could not resolve seed"); sys.exit(1)
    print(f"seeding from {qid}")
    con = db.connect()
    ingest(con, qid, args.depth, args.limit)
    con.commit()
    print("done:", db.stats(con))

if __name__ == "__main__":
    main()
