#!/usr/bin/env python3
"""Build a clean, reproducible project archive from Git-tracked files."""

from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT.parent / "FootballMatchPrediction-clean.zip"
ARCHIVE_ROOT = "FootballMatchPrediction"

EXCLUDED_FILES = {
    ".env",
    "events_cache.json",
    "live_prediction_cache",
    "live_prediction_cache.json",
    "matches.db",
    "model.pkl",  # Empty legacy placeholder; real models are best_models.pkl files.
    "prediction_cache.json",
    "upcoming_fixtures_cache.json",
}
EXCLUDED_PARTS = {".claude", ".git", ".venv", "__pycache__", "xcuserdata"}
SENSITIVE_NAME_RE = re.compile(r"(^|/)(\.env($|\.)|.*credentials?.*|.*secrets?.*)", re.I)
SENSITIVE_ASSIGNMENT_RE = re.compile(
    rb"(?m)^\s*(?:API_FOOTBALL_KEY|FOOTBALL_DATA_TOKEN|DATABASE_URL)\s*=\s*(.+)$"
)
SAFE_ASSIGNMENT_MARKERS = (
    b"os.environ",
    b"getenv(",
    b"DATABASE_URL.replace(",
    b"replace-",
    b"your-",
    b"postgresql://postgres.PROJECT_REF",
    b"sqlite:///matches.db",
    b"${{",
)


def contains_possible_credential(content: bytes) -> bool:
    for match in SENSITIVE_ASSIGNMENT_RE.finditer(content):
        value = match.group(1).strip().strip(b"`\"").strip(b"'")
        if not value:
            continue
        if any(marker in value for marker in SAFE_ASSIGNMENT_MARKERS):
            continue
        return True
    return False


def tracked_files() -> list[PurePosixPath]:
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    )
    paths = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        path = PurePosixPath(raw.decode("utf-8"))
        if path.as_posix() in EXCLUDED_FILES:
            continue
        if any(part in EXCLUDED_PARTS for part in path.parts):
            continue
        if path.as_posix() != ".env.example" and SENSITIVE_NAME_RE.search(path.as_posix()):
            continue
        paths.append(path)
    return sorted(paths, key=lambda item: item.as_posix())


def build_archive(output: Path) -> tuple[int, int]:
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    files = tracked_files()
    if not files:
        raise RuntimeError("No Git-tracked project files were found")

    total_bytes = 0
    checksums = []
    with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for relative in files:
            source = ROOT / relative.as_posix()
            if not source.is_file():
                raise FileNotFoundError(source)
            content = source.read_bytes()
            if relative.as_posix() != ".env.example" and contains_possible_credential(content):
                raise RuntimeError(f"Possible credential found in {relative}")
            info = ZipInfo(f"{ARCHIVE_ROOT}/{relative.as_posix()}")
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.external_attr = (0o755 if source.stat().st_mode & 0o111 else 0o644) << 16
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, content, compress_type=ZIP_DEFLATED, compresslevel=9)
            checksums.append(f"{hashlib.sha256(content).hexdigest()}  {relative.as_posix()}")
            total_bytes += len(content)

        manifest = ("\n".join(checksums) + "\n").encode("utf-8")
        manifest_info = ZipInfo(f"{ARCHIVE_ROOT}/RELEASE_MANIFEST.sha256")
        manifest_info.date_time = (2026, 1, 1, 0, 0, 0)
        manifest_info.external_attr = 0o644 << 16
        manifest_info.compress_type = ZIP_DEFLATED
        archive.writestr(
            manifest_info, manifest, compress_type=ZIP_DEFLATED, compresslevel=9
        )

    with ZipFile(output) as archive:
        bad = archive.testzip()
        if bad:
            raise RuntimeError(f"Archive CRC verification failed at {bad}")
        if any(
            not name.endswith("/.env.example") and SENSITIVE_NAME_RE.search(name)
            for name in archive.namelist()
        ):
            raise RuntimeError("Sensitive filename was included in the archive")
    return len(files), total_bytes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    count, source_bytes = build_archive(args.output)
    output = args.output.resolve()
    print(f"Created: {output}")
    print(f"Files: {count}")
    print(f"Source bytes: {source_bytes}")
    print(f"ZIP bytes: {output.stat().st_size}")


if __name__ == "__main__":
    main()
