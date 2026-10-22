"""Download deposited public PDF URLs, stopping requests to blocked hosts.

Run again later to retry an accessible site; completed PDFs are retained.
No credentials, CAPTCHA bypass, browser impersonation or proxy rotation.
"""
import hashlib
import json
import subprocess
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent


def main():
    pdfdir = ROOT / "pdfs"
    pdfdir.mkdir(exist_ok=True)
    urls = (ROOT / "workflow_latest_pdf_links.txt").read_text().splitlines()
    failures = Counter()
    statuses = []
    for url in urls:
        host = urlparse(url).hostname
        if failures[host] >= 3:
            statuses.append({"url": url, "status": "not_attempted_host_blocked_after_3_denials"})
            continue
        filename = hashlib.sha256(url.encode()).hexdigest()[:20] + ".pdf"
        path = pdfdir / filename
        if path.exists() and path.read_bytes()[:5] == b"%PDF-":
            statuses.append({"url": url, "status": "already_downloaded", "path": str(path.relative_to(ROOT))})
            continue
        temp = pdfdir / (filename + ".part")
        response = subprocess.run([
            "curl", "-L", "--max-time", "45", "-sS", "-o", str(temp),
            "-w", "%{http_code} %{content_type}", url,
        ], capture_output=True, text=True)
        code = response.stdout.split(" ", 1)[0]
        valid = response.returncode == 0 and code == "200" and temp.exists() and temp.read_bytes()[:5] == b"%PDF-"
        entry = {"url": url, "http": code, "content_type": response.stdout.partition(" ")[2], "retrieved_at_utc": datetime.now(timezone.utc).isoformat()}
        if valid:
            temp.rename(path)
            entry.update(status="downloaded", path=str(path.relative_to(ROOT)), bytes=path.stat().st_size)
        else:
            entry["status"] = "access_denied" if code in ("401", "403", "429") else "not_a_downloadable_pdf"
            if code in ("401", "403", "429"):
                failures[host] += 1
            if temp.exists():
                temp.unlink()
        statuses.append(entry)
        print(entry["status"], code, url, flush=True)
        time.sleep(1)
    (ROOT / "pdf_download_status.jsonl").write_text("".join(json.dumps(x) + "\n" for x in statuses))
    counts = dict(Counter(x["status"] for x in statuses))
    (ROOT / "pdf_download_manifest.json").write_text(json.dumps({"total_links": len(urls), "counts": counts, "policy": "Stop after 3 access denials per host; do not bypass restrictions"}, indent=2) + "\n")
    print(json.dumps(counts), flush=True)


if __name__ == "__main__":
    main()
