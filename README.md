# allofculture

An explorable relational database of culture. Nodes are cultural artifacts and
actors; **edges are attributed claims** about how they relate — references,
sampling, collage, covers, remixes, parody, influence, membership, and more.

## Run it
```bash
python3 server.py 8000     # open http://localhost:8000
```

## Deploy to GitHub Pages (free, static)
The explorer is fully client-side — it loads the whole graph from `web/data.json`
once, so it needs no server. To publish:

1. Create a GitHub repo and add it as `origin`:
   ```bash
   git remote add origin git@github.com:USER/REPO.git
   ```
2. Push the code, then deploy the static site:
   ```bash
   git push -u origin master
   ./deploy_pages.sh
   ```
3. In the repo's **Settings → Pages**, set the source to branch `gh-pages`.

After any DB change, re-run `./deploy_pages.sh` to refresh the live site.
(`python3 export_static.py` alone just regenerates `web/data.json` locally.)

## CLI
```bash
python3 cli.py stats
python3 cli.py neighbors "Funky Drummer"
python3 cli.py path "James Brown" "Drum and bass"
python3 cli.py add-node work "My Song" --year 2024 --desc "..."
python3 cli.py add-edge "My Song" "Funky Drummer" samples --src https://... --src-type wikidata --conf 0.9 --verified
python3 cli.py export > graph.json
```

## Schema
- `nodes` — `type` (work/person/band/movement/genre/place/concept/medium), name, year, description, meta.
- `edges` — a **claim**: `source_id → target_id` with `relation`, plus attribution:
  `source` (URL/citation), `source_type`, `confidence` (0–1), `verified` (0/1).

## Sourcing strategy (hybrid)
1. **Automated ingestion** from citable APIs — Wikidata (has `based on`, `inspired by`,
   `sampled from`, `derivative work`), MusicBrainz (covers/remixes/samples), Discogs,
   WhoSampled, Wikipedia. Each claim carries its source URL.
2. **Human curation** for fuzzy relations (collage, parody, conceptual references),
   added with a citation.
3. **Confidence + verification** distinguish machine-extracted, human-cited, and
   unverified claims. Unverified claims are still stored but flagged.

## Files
- `schema.sql` — DB schema
- `db.py` — core library
- `cli.py` — command-line interface
- `seed.py` — illustrative seed cluster (hip-hop sampling + visual collage)
- `server.py` — zero-dependency HTTP server (JSON API + static UI)
- `web/index.html` — vis.js graph explorer
