from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from formulaboost import __version__
from formulaboost.axplorer_adapter import export_family_program_seeds, import_axplorer_examples
from formulaboost.core.evaluator import FamilyEvaluator
from formulaboost.core.family import FamilyProgram
from formulaboost.core.random import seeded_rng
from formulaboost.core.registry import get_domain
from formulaboost.core.serialization import (
    read_json,
    read_jsonl,
    read_math_objects,
    write_json,
    write_jsonl,
    write_math_objects,
)
from formulaboost.core.objects import MathObject
from formulaboost.dsl.ast import AstNode
from formulaboost.dsl.interpreter import evaluate_modular_set
from formulaboost.dsl.pretty import pretty as pretty_ast
from formulaboost.dsl.semantic_hash import semantic_hash
from formulaboost.miners import ResidueFrequencyMiner
from formulaboost.reporting import write_results_report
from formulaboost.search import assign_pareto_ranks


DOMAINS = ["c4_free_circulant", "modular_sidon"]

DEFAULT_SPLITS = {
    "train_params": [{"n": 17}, {"n": 19}, {"n": 23}],
    "val_params": [{"n": 29}, {"n": 31}],
    "test_params": [{"n": 37}, {"n": 41}],
}


def _parse_json_object(text: str | None) -> dict[str, Any]:
    if not text:
        return {}
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise argparse.ArgumentTypeError("expected a JSON object")
    return parsed


def _load_splits(config: str | None) -> dict[str, list[dict[str, Any]]]:
    if not config:
        return {key: list(value) for key, value in DEFAULT_SPLITS.items()}
    path = Path(config)
    if not path.exists():
        raise FileNotFoundError(f"config file does not exist: {config}")
    if path.suffix.lower() != ".json":
        raise ValueError("FormulaBoost MVP config loader accepts JSON configs; omit --config for defaults")
    payload = read_json(path)
    return {
        "train_params": list(payload.get("train_params") or DEFAULT_SPLITS["train_params"]),
        "val_params": list(payload.get("val_params") or DEFAULT_SPLITS["val_params"]),
        "test_params": list(payload.get("test_params") or DEFAULT_SPLITS["test_params"]),
    }


def cmd_generate_examples(args: argparse.Namespace) -> int:
    domain = get_domain(args.domain)
    params = _parse_json_object(args.params)
    if args.n is not None:
        params["n"] = args.n
    if "n" not in params:
        raise SystemExit("generate-examples requires --params '{\"n\": ...}' or --n")
    rng = seeded_rng(args.seed)
    objects = []
    for index in range(args.count):
        if args.method == "random":
            obj = domain.random_object(params, rng)
        elif args.method == "greedy":
            obj = domain.greedy_object(params, rng)
        elif args.method == "greedy_local":
            start = domain.greedy_object(params, rng)
            obj = domain.local_repair(start, args.repair_budget, rng)
        else:  # pragma: no cover - argparse choices prevent this
            raise ValueError(args.method)
        metadata = dict(obj.metadata)
        metadata.update({"seed": args.seed, "index": index, "method": args.method})
        obj = type(obj)(
            domain=obj.domain,
            params=obj.params,
            data=obj.data,
            canonical=obj.canonical,
            score=obj.score,
            valid=obj.valid,
            source=obj.source,
            metadata=metadata,
        )
        objects.append(obj)
    target = write_math_objects(args.out, objects)
    print(f"wrote {len(objects)} {args.domain} examples to {target}")
    return 0


def cmd_search_families(args: argparse.Namespace) -> int:
    domain = get_domain(args.domain)
    examples = []
    for path in args.examples or []:
        examples.extend(read_math_objects(path))
    examples = [obj for obj in examples if obj.domain == args.domain]

    splits = _load_splits(args.config)
    run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_formulaboost")
    run_dir = Path(args.out_root) / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    rng = seeded_rng(args.seed)
    miner = ResidueFrequencyMiner(max_modulus=args.max_modulus, threshold=args.threshold)
    programs = miner.propose(examples, domain, budget=args.budget, rng=rng)
    programs = _dedupe_programs_by_semantics(programs, [*splits["train_params"], *splits["val_params"]])
    programs = [program.with_id(f"fb_{index:06d}") for index, program in enumerate(programs, start=1)]

    evaluator = FamilyEvaluator()
    family_rows: list[dict[str, Any]] = []
    objects: list[dict[str, Any]] = []
    for program in programs:
        result = evaluator.evaluate(
            program,
            domain,
            splits["train_params"],
            splits["val_params"],
            splits["test_params"],
        )
        row = program.to_dict()
        row["evaluation"] = result.to_dict()
        family_rows.append(row)
        for evaluation in result.evaluations:
            objects.append(
                {
                    "program_id": program.program_id,
                    "split": evaluation["split"],
                    "params": evaluation["params"],
                    "object": evaluation["object"],
                    "valid": evaluation["valid"],
                    "raw_score": evaluation["raw_score"],
                    "normalized_score": evaluation["normalized_score"],
                    "canonical": evaluation["canonical"],
                }
            )

    assign_pareto_ranks(family_rows)
    family_rows.sort(
        key=lambda row: (
            row["evaluation"]["invalid_rate"],
            row["evaluation"].get("pareto_rank", 999),
            -row["evaluation"]["val_mean_score"],
            row["complexity"],
        )
    )
    manifest = {
        "schema": "formulaboost_run_manifest_v1",
        "run_id": run_id,
        "tool_version": __version__,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "domain": args.domain,
        "seed": args.seed,
        "train_params": splits["train_params"],
        "val_params": splits["val_params"],
        "test_params": splits["test_params"],
        "config": {
            "max_modulus": args.max_modulus,
            "threshold": args.threshold,
            "budget": args.budget,
            "examples": [str(path) for path in args.examples or []],
        },
    }
    write_json(run_dir / "manifest.json", manifest)
    write_jsonl(run_dir / "families.jsonl", family_rows)
    write_jsonl(run_dir / "objects.jsonl", objects)
    _write_metrics_csv(run_dir / "metrics.csv", family_rows)
    if family_rows:
        write_json(run_dir / "top_family.json", family_rows[0])
    write_results_report(run_dir / "results.md", manifest, family_rows, examples_loaded=len(examples))
    write_results_report(run_dir / "top_families.md", manifest, family_rows, examples_loaded=len(examples))
    print(f"wrote FormulaBoost run to {run_dir}")
    if family_rows:
        top = family_rows[0]
        print(
            "top family {pid}: val={val:.3f} test={test:.3f} program={program}".format(
                pid=top["program_id"],
                val=top["evaluation"]["val_mean_score"],
                test=top["evaluation"]["test_mean_score"],
                program=top["pretty"],
            )
        )
    return 0


def cmd_evaluate_family(args: argparse.Namespace) -> int:
    domain = get_domain(args.domain)
    row = read_json(args.program)
    program = FamilyProgram.from_dict(row)
    splits = _load_splits(args.config)
    result = FamilyEvaluator().evaluate(
        program,
        domain,
        splits["train_params"],
        splits["val_params"],
        splits["test_params"],
    )
    payload = row | {"evaluation": result.to_dict()}
    if args.out:
        write_json(args.out, payload)
        print(f"wrote evaluation to {args.out}")
    else:
        print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.invalid_count == 0 else 1


def cmd_report(args: argparse.Namespace) -> int:
    run_dir = Path(args.run)
    manifest = read_json(run_dir / "manifest.json")
    family_rows = read_jsonl(run_dir / "families.jsonl")
    target = write_results_report(args.out or run_dir / "results.md", manifest, family_rows, examples_loaded=-1)
    print(f"wrote report to {target}")
    return 0


def cmd_export_seeds(args: argparse.Namespace) -> int:
    params = _parse_json_object(args.params)
    if "n" not in params:
        raise SystemExit("export-seeds requires --params '{\"n\": ...}'")
    rows = read_jsonl(args.families)
    objects = []
    for row in rows:
        if args.domain and row.get("domain") != args.domain:
            continue
        program = FamilyProgram.from_dict(row)
        obj = program.evaluate(params)
        objects.append(obj)
        if len(objects) >= args.top_k:
            break
    target = write_math_objects(args.out, objects)
    print(f"exported {len(objects)} family-generated seeds to {target}")
    return 0


def cmd_import_axplorer_examples(args: argparse.Namespace) -> int:
    objects = import_axplorer_examples(args.input, args.out, domain=args.domain)
    print(f"imported {len(objects)} Axplorer examples to {args.out}")
    return 0


def cmd_export_axplorer_seeds(args: argparse.Namespace) -> int:
    params = _parse_json_object(args.params)
    if "n" not in params:
        raise SystemExit("export-axplorer-seeds requires --params '{\"n\": ...}'")
    rows = read_jsonl(args.families)
    objects = export_family_program_seeds(
        rows,
        params,
        args.out,
        domain=args.domain,
        top_k=args.top_k,
        env_name=args.env_name,
    )
    print(f"exported {len(objects)} Axplorer seed rows to {args.out}")
    return 0


def cmd_synthetic_recovery(args: argparse.Namespace) -> int:
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    train_params = [{"n": n} for n in args.train_n]
    check_params = [{"n": n} for n in args.check_n]
    hidden_programs = [
        ("mod5_1_4", AstNode("residue_classes", {"modulus": 5, "residues": [1, 4]})),
        ("mod7_0_2_3", AstNode("residue_classes", {"modulus": 7, "residues": [0, 2, 3]})),
        ("mod4_1", AstNode("residue_classes", {"modulus": 4, "residues": [1]})),
    ]
    miner = ResidueFrequencyMiner(max_modulus=args.max_modulus, threshold=args.threshold)
    domain = get_domain("modular_sidon")
    results = []
    for name, hidden in hidden_programs:
        examples = [
            MathObject(
                domain="modular_sidon",
                params=params,
                data={"elements": sorted(evaluate_modular_set(hidden, params))},
                source="synthetic_hidden_program",
                metadata={"hidden_program": name},
            )
            for params in train_params
        ]
        candidates = miner.propose(examples, domain, budget=args.budget, rng=seeded_rng(args.seed))
        match = None
        for candidate in candidates:
            base = _candidate_base_ast(candidate.ast)
            if base is None:
                continue
            if _same_semantics(hidden, base, check_params):
                match = candidate
                break
        results.append(
            {
                "hidden_name": name,
                "hidden_pretty": pretty_ast(hidden),
                "recovered": match is not None,
                "matched_pretty": None if match is None else pretty_ast(_candidate_base_ast(match.ast) or match.ast),
                "candidate_count": len(candidates),
            }
        )
    recovered = sum(1 for row in results if row["recovered"])
    payload = {
        "schema": "formulaboost_synthetic_recovery_v1",
        "seed": args.seed,
        "train_params": train_params,
        "check_params": check_params,
        "recovered": recovered,
        "total": len(results),
        "recovery_rate": recovered / max(1, len(results)),
        "results": results,
    }
    write_json(out_dir / "synthetic_recovery.json", payload)
    _write_synthetic_markdown(out_dir / "synthetic_recovery.md", payload)
    print(f"synthetic recovery: {recovered}/{len(results)} recovered; wrote {out_dir}")
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    run_root = Path(args.out)
    examples = run_root / "examples" / f"{args.domain}_n{args.n}.jsonl"
    cmd_generate_examples(
        argparse.Namespace(
            domain=args.domain,
            params=json.dumps({"n": args.n}),
            n=None,
            count=args.count,
            method="greedy_local",
            seed=args.seed,
            repair_budget=50,
            out=examples,
        )
    )
    return cmd_search_families(
        argparse.Namespace(
            domain=args.domain,
            examples=[examples],
            config=None,
            run_id=args.run_id or f"demo_{args.domain}",
            out_root=run_root / "runs",
            seed=args.seed,
            max_modulus=10,
            threshold=1.05,
            budget=30,
        )
    )


def _candidate_base_ast(ast: AstNode) -> AstNode | None:
    if ast.op == "greedy_complete":
        base = ast.args.get("base")
        return base if isinstance(base, AstNode) else None
    return ast


def _same_semantics(left: AstNode, right: AstNode, params_list: list[dict[str, Any]]) -> bool:
    return all(evaluate_modular_set(left, params) == evaluate_modular_set(right, params) for params in params_list)


def _dedupe_programs_by_semantics(
    programs: list[FamilyProgram], params_list: list[dict[str, Any]]
) -> list[FamilyProgram]:
    best_by_hash: dict[str, FamilyProgram] = {}
    for program in programs:
        try:
            key = f"{program.domain}:{semantic_hash(program.ast, params_list)}"
        except Exception:
            key = f"{program.domain}:{program.ast.stable_json()}"
        current = best_by_hash.get(key)
        if current is None or program.complexity() < current.complexity():
            best_by_hash[key] = program
    return list(best_by_hash.values())


def _write_synthetic_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# FormulaBoost Synthetic DSL Recovery",
        "",
        f"- Recovered: {payload['recovered']} / {payload['total']}",
        f"- Recovery rate: {payload['recovery_rate']:.3f}",
        "",
        "| hidden | recovered | matched | candidates |",
        "|---|---:|---|---:|",
    ]
    for row in payload["results"]:
        lines.append(
            "| `{hidden}` | {recovered} | `{matched}` | {count} |".format(
                hidden=row["hidden_pretty"],
                recovered="yes" if row["recovered"] else "no",
                matched=row["matched_pretty"] or "",
                count=row["candidate_count"],
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_metrics_csv(path: Path, family_rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "program_id",
                "complexity",
                "train_mean_score",
                "val_mean_score",
                "test_mean_score",
                "invalid_rate",
                "pareto_rank",
                "mean_runtime_sec",
                "pretty",
            ],
        )
        writer.writeheader()
        for row in family_rows:
            ev = row["evaluation"]
            writer.writerow(
                {
                    "program_id": row["program_id"],
                    "complexity": row["complexity"],
                    "train_mean_score": ev["train_mean_score"],
                    "val_mean_score": ev["val_mean_score"],
                    "test_mean_score": ev["test_mean_score"],
                    "invalid_rate": ev["invalid_rate"],
                    "pareto_rank": ev.get("pareto_rank", ""),
                    "mean_runtime_sec": ev["mean_runtime_sec"],
                    "pretty": row["pretty"],
                }
            )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="formulaboost")
    sub = parser.add_subparsers(dest="command", required=True)

    gen = sub.add_parser("generate-examples", help="generate finite examples for a FormulaBoost domain")
    gen.add_argument("--domain", default="modular_sidon", choices=DOMAINS)
    gen.add_argument("--params", default=None, help="JSON object such as '{\"n\":31}'")
    gen.add_argument("--n", type=int, default=None)
    gen.add_argument("--count", type=int, default=100)
    gen.add_argument("--method", choices=["random", "greedy", "greedy_local"], default="greedy_local")
    gen.add_argument("--repair-budget", type=int, default=100)
    gen.add_argument("--seed", type=int, default=0)
    gen.add_argument("--out", required=True)
    gen.set_defaults(func=cmd_generate_examples)

    search = sub.add_parser("search-families", help="mine and evaluate candidate family programs")
    search.add_argument("--domain", default="modular_sidon", choices=DOMAINS)
    search.add_argument("--examples", action="append", default=None)
    search.add_argument("--config", default=None, help="optional JSON config with train/val/test params")
    search.add_argument("--run-id", default=None)
    search.add_argument("--out-root", default="runs")
    search.add_argument("--seed", type=int, default=0)
    search.add_argument("--max-modulus", type=int, default=12)
    search.add_argument("--threshold", type=float, default=1.15)
    search.add_argument("--budget", type=int, default=50)
    search.set_defaults(func=cmd_search_families)

    evaluate = sub.add_parser("evaluate-family", help="evaluate one serialized family program")
    evaluate.add_argument("--domain", default="modular_sidon", choices=DOMAINS)
    evaluate.add_argument("--program", required=True)
    evaluate.add_argument("--config", default=None)
    evaluate.add_argument("--out", default=None)
    evaluate.set_defaults(func=cmd_evaluate_family)

    report = sub.add_parser("report", help="regenerate a FormulaBoost markdown report")
    report.add_argument("--run", required=True)
    report.add_argument("--out", default=None)
    report.set_defaults(func=cmd_report)

    export = sub.add_parser("export-seeds", help="export family-generated objects as JSONL seeds")
    export.add_argument("--families", required=True)
    export.add_argument("--domain", default=None, choices=DOMAINS)
    export.add_argument("--params", required=True, help="JSON object such as '{\"n\":101}'")
    export.add_argument("--top-k", type=int, default=10)
    export.add_argument("--out", required=True)
    export.set_defaults(func=cmd_export_seeds)

    import_ax = sub.add_parser("import-axplorer-examples", help="convert Axplorer-style examples to FormulaBoost JSONL")
    import_ax.add_argument("--input", required=True)
    import_ax.add_argument("--out", required=True)
    import_ax.add_argument("--domain", default=None, choices=DOMAINS)
    import_ax.set_defaults(func=cmd_import_axplorer_examples)

    export_ax = sub.add_parser("export-axplorer-seeds", help="export family-generated objects as Axplorer JSONL seeds")
    export_ax.add_argument("--families", required=True)
    export_ax.add_argument("--domain", default=None, choices=DOMAINS)
    export_ax.add_argument("--params", required=True, help="JSON object such as '{\"n\":101}'")
    export_ax.add_argument("--top-k", type=int, default=10)
    export_ax.add_argument("--env-name", default=None)
    export_ax.add_argument("--out", required=True)
    export_ax.set_defaults(func=cmd_export_axplorer_seeds)

    synthetic = sub.add_parser("synthetic-recovery", help="run a small synthetic DSL recovery benchmark")
    synthetic.add_argument("--out", default="runs/formulaboost_synthetic")
    synthetic.add_argument("--seed", type=int, default=0)
    synthetic.add_argument("--train-n", type=int, nargs="+", default=[31, 37, 41])
    synthetic.add_argument("--check-n", type=int, nargs="+", default=[43, 47, 53])
    synthetic.add_argument("--max-modulus", type=int, default=10)
    synthetic.add_argument("--threshold", type=float, default=1.05)
    synthetic.add_argument("--budget", type=int, default=50)
    synthetic.set_defaults(func=cmd_synthetic_recovery)

    demo = sub.add_parser("demo", help="run a FormulaBoost domain demo end to end")
    demo.add_argument("--domain", default="modular_sidon", choices=DOMAINS)
    demo.add_argument("--out", default="runs/formulaboost_demo")
    demo.add_argument("--run-id", default=None)
    demo.add_argument("--n", type=int, default=31)
    demo.add_argument("--count", type=int, default=80)
    demo.add_argument("--seed", type=int, default=0)
    demo.set_defaults(func=cmd_demo)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
