"""Resumable public Crossref metadata harvest; no browser challenge bypass."""

import gzip
import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode


ROOT = Path(__file__).resolve().parent
RAW = ROOT / "raw_crossref"
CUTOFF = "2026-10-21"
BASE = "https://api.crossref.org/prefixes/10.26434/works"
FIELDS = "DOI,title,abstract,author,posted,created,published,resource,link,relation,license,publisher,type"


def request(url):
    for attempt in range(6):
        proc = subprocess.run(
            ["curl", "-L", "--fail-with-body", "--max-time", "60", "-sS",
             "-H", "User-Agent: ChemRxivWorkflowCatalogue/1.0 (public metadata research)", url],
            capture_output=True,
        )
        if proc.returncode == 0:
            return json.loads(proc.stdout)
        message = (proc.stderr + proc.stdout[:500]).decode(errors="replace")
        if b'"validation-failure"' in proc.stdout:
            raise RuntimeError(proc.stdout.decode(errors="replace"))
        print(f"Request retry {attempt + 1}: {message[:500]}", flush=True)
        if attempt == 5:
            raise RuntimeError(message)
        time.sleep(min(2 ** (attempt + 1), 30))


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    cursor, page, count = "*", 0, 0
    started = datetime.now(timezone.utc).isoformat()
    reported = None
    while True:
        path = RAW / f"page_{page:04d}.json.gz"
        if path.exists():
            with gzip.open(path, "rt") as stream:
                response = json.load(stream)
        else:
            params = {
                "filter": f"type:posted-content,until-pub-date:{CUTOFF}",
                "rows": 1000,
                "cursor": cursor,
                "select": FIELDS,
            }
            url = BASE + "?" + urlencode(params)
            response = request(url)
            with gzip.open(path, "wt") as stream:
                json.dump(response, stream, ensure_ascii=False)
            time.sleep(1)
        message = response["message"]
        reported = message["total-results"]
        items = message["items"]
        count += len(items)
        progress = {
            "source": BASE, "filter": f"type:posted-content,until-pub-date:{CUTOFF}",
            "snapshot_date": CUTOFF, "started_at_utc": started,
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "reported_total_latest_page": reported, "retrieved_records": count,
            "pages_with_items": page + bool(items), "complete": not items,
        }
        (ROOT / "harvest_manifest.json").write_text(json.dumps(progress, indent=2) + "\n")
        print(f"page={page} rows={len(items)} retrieved={count} reported={reported}", flush=True)
        if not items:
            break
        next_cursor = message.get("next-cursor")
        if not next_cursor:
            raise RuntimeError("Nonempty page has no continuation cursor")
        if next_cursor == cursor:
            raise RuntimeError("Cursor repeated before an empty page; inspect incomplete harvest")
        cursor = next_cursor
        page += 1
    print("HARVEST COMPLETE", flush=True)


if __name__ == "__main__":
    main()
