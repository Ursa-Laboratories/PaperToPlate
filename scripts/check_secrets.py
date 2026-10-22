"""Inspect the exact staged blobs without printing credential values.

Run from the repository root with the app's Python environment. Known private
values are read only from the local, ignored .env. Also checks common credential
formats and text inside gzip, Office ZIP and PDF files. This is a precaution,
not a guarantee against every possible secret format.
"""
import gzip
import io
import json
import logging
import re
import subprocess
import zipfile
from pathlib import Path

from dotenv import dotenv_values
from pypdf import PdfReader

logging.getLogger("pypdf").setLevel(logging.ERROR)


PATTERNS = {
    "private key": rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    "OpenAI-style key": rb"\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}",
    "GitHub token": rb"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})",
    "AWS access key": rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    "Google API key": rb"\bAIza[A-Za-z0-9_-]{30,}",
    "JWT": rb"\beyJ[A-Za-z0-9_-]{15,}\.eyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{20,}",
    "literal bearer token": rb"\bBearer [A-Za-z0-9._-]{30,}",
}


def payloads(name, data):
    yield name, data
    if name.endswith(".gz"):
        yield name + " (expanded)", gzip.decompress(data)
    elif name.endswith((".xlsx", ".docx", ".pptx", ".zip")):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            for item in archive.infolist():
                if not item.is_dir() and item.file_size < 100_000_000:
                    yield name + ":" + item.filename, archive.read(item)
    elif name.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(data))
        yield name + " (PDF text)", "\n".join(p.extract_text() or "" for p in reader.pages).encode()


def main():
    local = dotenv_values(".env") if Path(".env").exists() else {}
    private = [v.encode() for k, v in local.items() if v and len(v) >= 8 and re.search(r"key|token|secret|password", k, re.I)]
    names = subprocess.check_output(["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z"]).decode().split("\0")
    names = [name for name in names if name]
    if not names:
        raise SystemExit("No staged files to inspect.")
    findings = []
    for name in names:
        path = Path(name)
        if path.name.startswith(".env") and path.name != ".env.example":
            findings.append({"file": name, "reason": "private environment file"})
        if name.startswith(("data/", ".venv/", "frontend/node_modules/")):
            findings.append({"file": name, "reason": "private or generated directory"})
        data = subprocess.check_output(["git", "show", ":" + name])
        for label, content in payloads(name, data):
            if any(value in content for value in private):
                findings.append({"file": label, "reason": "matches private configuration value"})
            for kind, pattern in PATTERNS.items():
                if re.search(pattern, content):
                    findings.append({"file": label, "reason": kind})
    print(json.dumps({"staged_files_scanned": len(names), "findings": findings}, indent=2))
    raise SystemExit(1 if findings else 0)


if __name__ == "__main__":
    main()
