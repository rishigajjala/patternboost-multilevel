from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from multilevel.canonical import attach_certificate_hash, load_json, write_json
from multilevel.scorers import epsilon_net, graph_separation, guillotine, misr, unit_square
from multilevel.summary import collect_summaries


SCHEMA_VERIFY = {
    "misr_certificate_v1": misr.verify_certificate,
    "unit_square_stab_certificate_v1": unit_square.verify_certificate,
    "guillotine_certificate_v1": guillotine.verify_certificate,
    "graph_separation_certificate_v1": graph_separation.verify_certificate,
    "epsilon_net_certificate_v1": epsilon_net.verify_certificate,
}


def _float_equal(a: Any, b: Any, *, tolerance: float = 1e-8) -> bool:
    if a in (None, "") or b in (None, ""):
        return a in (None, "") and b in (None, "")
    try:
        return abs(float(a) - float(b)) <= tolerance
    except Exception:
        return False


def read_summary_rows(summary_csv: str | Path) -> list[dict[str, Any]]:
    with Path(summary_csv).open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def audit_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        cert_path_raw = row.get("best_certificate_path")
        result = {
            "row": index,
            "run_id": row.get("run_id"),
            "problem": row.get("problem"),
            "summary_path": row.get("summary_path"),
            "certificate_path": cert_path_raw,
            "certificate_exists": False,
            "schema": "",
            "hash_ok": False,
            "verify_ok": False,
            "summary_hash_ok": False,
            "summary_score_ok": False,
            "status": "failed",
            "error": "",
        }
        if not cert_path_raw:
            result["error"] = "summary has no best_certificate_path"
            results.append(result)
            continue
        cert_path = Path(str(cert_path_raw))
        if not cert_path.exists():
            result["error"] = "certificate path does not exist"
            results.append(result)
            continue
        result["certificate_exists"] = True
        try:
            cert = load_json(cert_path)
            schema = str(cert.get("schema", ""))
            result["schema"] = schema
            stored_hash = cert.get("certificate_hash")
            result["hash_ok"] = bool(stored_hash) and attach_certificate_hash(cert).get("certificate_hash") == stored_hash
            verifier = SCHEMA_VERIFY.get(schema)
            if verifier is None:
                result["error"] = f"unknown certificate schema: {schema!r}"
                results.append(result)
                continue
            result["verify_ok"] = bool(verifier(cert))
            result["summary_hash_ok"] = row.get("best_certificate_hash") in (None, "", stored_hash)
            result["summary_score_ok"] = _float_equal(row.get("best_exact_score"), cert.get("score"))
            if result["hash_ok"] and result["verify_ok"] and result["summary_hash_ok"] and result["summary_score_ok"]:
                result["status"] = "passed"
        except Exception as exc:
            result["error"] = repr(exc)
        results.append(result)
    return results


def audit_summary_csv(summary_csv: str | Path) -> list[dict[str, Any]]:
    return audit_rows(read_summary_rows(summary_csv))


def audit_summary_root(root: str | Path) -> list[dict[str, Any]]:
    rows = collect_summaries(root)
    return audit_rows(rows)


def write_audit_outputs(results: list[dict[str, Any]], json_path: str | Path, csv_path: str | Path | None = None) -> dict[str, Any]:
    passed = sum(1 for row in results if row.get("status") == "passed")
    report = {
        "schema": "certificate_audit_report_v1",
        "rows": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }
    write_json(json_path, report)
    if csv_path is not None:
        target = Path(csv_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fields = [
            "row",
            "status",
            "problem",
            "run_id",
            "schema",
            "certificate_path",
            "certificate_exists",
            "hash_ok",
            "verify_ok",
            "summary_hash_ok",
            "summary_score_ok",
            "error",
            "summary_path",
        ]
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for row in results:
                writer.writerow({field: row.get(field, "") for field in fields})
    return report
