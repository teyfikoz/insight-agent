"""Build a source-only distribution, never a snapshot of the developer machine."""
import argparse
import hashlib
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = {"main.py", "README.md", "requirements.txt", "launch.command", "launch.bat", "LICENSE"}
DIRECTORIES = {"agents", "scanner", "reporter", "dashboard", "skills", "scripts"}
SUFFIXES = {".py", ".html", ".js", ".css", ".md", ".txt"}
SECRET = re.compile(rb"(?:gsk_[A-Za-z0-9]{20,}|hf_[A-Za-z0-9]{20,}|nvapi-[A-Za-z0-9_-]{20,}|AIza[A-Za-z0-9_-]{30,}|gh[pousr]_[A-Za-z0-9]{20,}|-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----)")


def build(output: Path):
    members = []
    for path in sorted(ROOT.rglob("*")):
        rel = path.relative_to(ROOT)
        if any(part.startswith(".") or part == "__pycache__" for part in rel.parts):
            continue
        if not path.is_file() or path.is_symlink():
            continue
        if rel.as_posix() not in FILES and not (rel.parts[0] in DIRECTORIES and path.suffix in SUFFIXES):
            continue
        data = path.read_bytes()
        if SECRET.search(data):
            raise SystemExit(f"Credential pattern detected in {rel}; release refused (value not displayed).")
        members.append((path, rel))
    if not members:
        raise SystemExit("No distribution files found")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents accidental replacement of an existing release.
    with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as archive:
        for path, rel in members:
            archive.write(path, "InsightAgent-v2.0/" + rel.as_posix())
    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
    checksum = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(f"{checksum}  {output.name}\n")
    print(f"Release: {output}; {len(members)} files; {output.stat().st_size} bytes; SHA256 {checksum}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)
