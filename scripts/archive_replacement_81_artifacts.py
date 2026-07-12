#!/usr/bin/env python3
"""Build a portable archive of the final replacement-matrix artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Iterable


REQUIRED_FIELDS = {
    "config_id",
    "best_certificate_path",
    "best_rendering_path",
    "certificate_hash",
}
MAPPING_FIELDS = (
    "config_id",
    "certificate_path",
    "rendering_path",
    "certificate_hash",
)


class ArchiveError(RuntimeError):
    """Raised when source or archive validation fails."""


@dataclass(frozen=True)
class MetricRow:
    config_id: str
    config_parts: tuple[str, ...]
    certificate_name: str
    rendering_name: str
    certificate_hash: str


@dataclass(frozen=True)
class ResolvedPair:
    metric: MetricRow
    source_root: Path
    certificate: Path
    rendering: Path


def _asset_name(recorded_path: str, suffix: str, field: str, line_number: int) -> str:
    value = recorded_path.strip().replace("\\", "/")
    name = PurePosixPath(value).name
    if not name or name in {".", ".."} or not name.lower().endswith(suffix):
        raise ArchiveError(f"line {line_number}: invalid {field}: {recorded_path!r}")
    return name


def _config_parts(config_id: str, line_number: int) -> tuple[str, ...]:
    value = config_id.strip()
    path = PurePosixPath(value)
    if (
        not value
        or "\\" in value
        or path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ArchiveError(f"line {line_number}: unsafe config_id: {config_id!r}")
    return path.parts


def read_metrics(path: Path, expected_count: int | None) -> list[MetricRow]:
    if not path.is_file():
        raise ArchiveError(f"row metrics file does not exist: {path}")

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        missing = sorted(REQUIRED_FIELDS - fields)
        if missing:
            raise ArchiveError(f"row metrics is missing required columns: {missing}")

        rows: list[MetricRow] = []
        for line_number, raw in enumerate(reader, start=2):
            certificate_hash = raw["certificate_hash"].strip()
            if not re.fullmatch(r"[0-9a-f]{64}", certificate_hash):
                raise ArchiveError(
                    f"line {line_number}: invalid certificate_hash: {certificate_hash!r}"
                )
            config_id = raw["config_id"].strip()
            rows.append(
                MetricRow(
                    config_id=config_id,
                    config_parts=_config_parts(config_id, line_number),
                    certificate_name=_asset_name(
                        raw["best_certificate_path"],
                        ".json",
                        "best_certificate_path",
                        line_number,
                    ),
                    rendering_name=_asset_name(
                        raw["best_rendering_path"],
                        ".svg",
                        "best_rendering_path",
                        line_number,
                    ),
                    certificate_hash=certificate_hash,
                )
            )

    duplicates = sorted(
        config_id
        for config_id, count in Counter(row.config_id for row in rows).items()
        if count != 1
    )
    if duplicates:
        raise ArchiveError(f"duplicate config_id values: {duplicates}")
    if expected_count is not None and len(rows) != expected_count:
        raise ArchiveError(f"expected {expected_count} metric rows, found {len(rows)}")
    return rows


def _source_roots(paths: Iterable[Path]) -> list[Path]:
    roots: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        root = path.expanduser().resolve()
        if root in seen:
            continue
        if not root.is_dir():
            raise ArchiveError(f"source root does not exist or is not a directory: {path}")
        roots.append(root)
        seen.add(root)
    if not roots:
        raise ArchiveError("at least one --source-root is required")
    return roots


def _layout_bases(root: Path) -> tuple[Path, ...]:
    """Accept config trees directly or below one run-group directory."""
    children = sorted((path for path in root.iterdir() if path.is_dir()), key=lambda p: p.name)
    return (root, *children)


def validate_certificate(path: Path, expected_hash: str) -> None:
    try:
        with path.open(encoding="utf-8") as handle:
            certificate = json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ArchiveError(f"cannot parse certificate {path}: {exc}") from exc
    if not isinstance(certificate, dict):
        raise ArchiveError(f"certificate is not a JSON object: {path}")
    actual_hash = certificate.get("certificate_hash")
    if actual_hash != expected_hash:
        raise ArchiveError(
            f"certificate hash mismatch for {path}: expected {expected_hash}, got {actual_hash}"
        )


def validate_svg(path: Path) -> None:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ArchiveError(f"cannot parse SVG {path}: {exc}") from exc
    local_name = root.tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1].lower()
    if local_name != "svg":
        raise ArchiveError(f"rendering root element is not <svg>: {path}")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def resolve_pair(
    metric: MetricRow,
    layouts: list[tuple[Path, tuple[Path, ...]]],
) -> ResolvedPair:
    candidates: list[ResolvedPair] = []
    invalid: list[str] = []
    seen: set[tuple[Path, Path]] = set()
    checked_bases = 0

    for source_root, bases in layouts:
        for base in bases:
            checked_bases += 1
            config_dir = base.joinpath(*metric.config_parts)
            certificate = config_dir / "certificates" / metric.certificate_name
            rendering = config_dir / "renderings" / metric.rendering_name
            if not (certificate.is_file() and rendering.is_file()):
                continue
            key = (certificate.resolve(), rendering.resolve())
            if key in seen:
                continue
            seen.add(key)
            try:
                validate_certificate(certificate, metric.certificate_hash)
                validate_svg(rendering)
            except ArchiveError as exc:
                invalid.append(str(exc))
                continue
            candidates.append(
                ResolvedPair(
                    metric=metric,
                    source_root=source_root,
                    certificate=certificate,
                    rendering=rendering,
                )
            )

    if not candidates:
        detail = f"; invalid candidates: {'; '.join(invalid)}" if invalid else ""
        raise ArchiveError(
            f"could not resolve a valid pair for {metric.config_id}; "
            f"checked {checked_bases} layout bases{detail}"
        )
    if len(candidates) == 1:
        return candidates[0]

    fingerprints = {
        (_sha256(candidate.certificate), _sha256(candidate.rendering))
        for candidate in candidates
    }
    if len(fingerprints) == 1:
        return candidates[0]
    locations = [str(candidate.certificate.parent.parent) for candidate in candidates]
    raise ArchiveError(f"conflicting source pairs for {metric.config_id}: {locations}")


def _portable_paths(metric: MetricRow) -> tuple[PurePosixPath, PurePosixPath]:
    base = PurePosixPath(*metric.config_parts)
    return (
        base / "certificates" / metric.certificate_name,
        base / "renderings" / metric.rendering_name,
    )


def _copy_pair(pair: ResolvedPair, stage: Path) -> dict[str, str]:
    certificate_rel, rendering_rel = _portable_paths(pair.metric)
    certificate_out = stage.joinpath(*certificate_rel.parts)
    rendering_out = stage.joinpath(*rendering_rel.parts)
    certificate_out.parent.mkdir(parents=True, exist_ok=True)
    rendering_out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pair.certificate, certificate_out)
    shutil.copy2(pair.rendering, rendering_out)

    if _sha256(pair.certificate) != _sha256(certificate_out):
        raise ArchiveError(f"certificate copy verification failed: {certificate_out}")
    if _sha256(pair.rendering) != _sha256(rendering_out):
        raise ArchiveError(f"rendering copy verification failed: {rendering_out}")
    validate_certificate(certificate_out, pair.metric.certificate_hash)
    validate_svg(rendering_out)

    return {
        "config_id": pair.metric.config_id,
        "certificate_path": certificate_rel.as_posix(),
        "rendering_path": rendering_rel.as_posix(),
        "certificate_hash": pair.metric.certificate_hash,
    }


def _write_mapping(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MAPPING_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _validate_staged_archive(
    stage: Path,
    mapping_rows: list[dict[str, str]],
) -> None:
    mapping_path = stage / "artifact_mapping.csv"
    with mapping_path.open(newline="", encoding="utf-8") as handle:
        parsed = list(csv.DictReader(handle))
    if parsed != mapping_rows:
        raise ArchiveError("artifact_mapping.csv did not round-trip exactly")

    for row in parsed:
        for field in ("certificate_path", "rendering_path"):
            relative = PurePosixPath(row[field])
            if relative.is_absolute() or ".." in relative.parts:
                raise ArchiveError(f"mapping contains a non-portable path: {row[field]}")
            if not stage.joinpath(*relative.parts).is_file():
                raise ArchiveError(f"mapping target does not exist: {row[field]}")

    files = [path for path in stage.rglob("*") if path.is_file()]
    expected_files = len(mapping_rows) * 2 + 1
    if len(files) != expected_files:
        raise ArchiveError(f"expected {expected_files} staged files, found {len(files)}")


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _promote(stage: Path, archive_dir: Path) -> None:
    for child in archive_dir.iterdir():
        if child != stage:
            _remove_path(child)
    for child in sorted(stage.iterdir(), key=lambda path: path.name):
        child.replace(archive_dir / child.name)
    stage.rmdir()


def archive_artifacts(
    row_metrics: Path,
    source_roots: list[Path],
    archive_dir: Path,
    expected_count: int | None,
) -> dict[str, object]:
    metrics = read_metrics(row_metrics.expanduser().resolve(), expected_count)
    roots = _source_roots(source_roots)
    archive = archive_dir.expanduser().resolve()
    for root in roots:
        if archive == root or archive.is_relative_to(root) or root.is_relative_to(archive):
            raise ArchiveError(f"archive directory overlaps source root: {root}")

    layouts = [(root, _layout_bases(root)) for root in roots]
    pairs = [resolve_pair(metric, layouts) for metric in metrics]
    pairs.sort(key=lambda pair: pair.metric.config_id)

    if archive.exists() and not archive.is_dir():
        raise ArchiveError(f"archive path exists and is not a directory: {archive}")
    archive.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".archive-staging-", dir=archive))
    try:
        mapping_rows = [_copy_pair(pair, stage) for pair in pairs]
        _write_mapping(stage / "artifact_mapping.csv", mapping_rows)
        _validate_staged_archive(stage, mapping_rows)
        _promote(stage, archive)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise

    source_usage = Counter(str(pair.source_root) for pair in pairs)
    return {
        "archive_dir": str(archive),
        "archive_files": len(pairs) * 2 + 1,
        "byte_copies_verified": len(pairs) * 2,
        "certificate_hashes_validated": len(pairs),
        "mapping_csv": str(archive / "artifact_mapping.csv"),
        "mapping_rows": len(mapping_rows),
        "pairs_archived": len(pairs),
        "source_root_usage": dict(sorted(source_usage.items())),
        "svg_renderings_parsed": len(pairs),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--row-metrics", type=Path, required=True)
    parser.add_argument(
        "--source-root",
        type=Path,
        action="append",
        required=True,
        help="Artifact tree root; repeat for each retained or replacement source.",
    )
    parser.add_argument(
        "--archive-dir",
        type=Path,
        required=True,
        help="Destination replaced with the validated portable archive.",
    )
    parser.add_argument(
        "--expected-count",
        type=int,
        default=81,
        help="Required row count (default: 81).",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    if args.expected_count <= 0:
        parser.error("--expected-count must be positive")
    try:
        summary = archive_artifacts(
            row_metrics=args.row_metrics,
            source_roots=args.source_root,
            archive_dir=args.archive_dir,
            expected_count=args.expected_count,
        )
    except ArchiveError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
