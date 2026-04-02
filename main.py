#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
from pathlib import Path

from agents.maesd import MAESDPipeline, MAESDSettings, run_maesd_in_environment


def main() -> None:
    parser = argparse.ArgumentParser(description="MAESD protein design pipeline")
    parser.add_argument("--input", "--idea", dest="idea", required=True, help="Natural-language protein design request")
    parser.add_argument("--output", type=str, default=None, help="Optional path for the JSON report")
    parser.add_argument("--config", type=str, default=None, help="Optional YAML config with backend settings")
    parser.add_argument("--loops", type=int, default=None, help="Maximum evolutionary iterations")
    parser.add_argument("--population", type=int, default=None, help="Population size per iteration")
    parser.add_argument("--stagnation-limit", type=int, default=None, help="Early-stop patience for non-improving rounds")
    parser.add_argument("--seed", type=int, default=None, help="Random seed")
    parser.add_argument(
        "--use-environment",
        action="store_true",
        help="Run the MAESD pipeline through the Environment/Role bridge instead of calling the pipeline directly",
    )
    parser.add_argument(
        "--reference-structure",
        type=str,
        default=None,
        help="Optional PDB/CIF structure path used by ProteinMPNN or structure-guided refinement",
    )
    args = parser.parse_args()

    settings = MAESDSettings.from_yaml(args.config) if args.config else MAESDSettings()
    if args.use_environment:
        payload = run_maesd_in_environment(
            prompt=args.idea,
            settings=settings,
            seed=args.seed,
            max_iterations=args.loops,
            population_size=args.population,
            stagnation_limit=args.stagnation_limit,
            reference_structure_path=args.reference_structure,
        )
        payload = __import__("json").dumps(payload, ensure_ascii=False, indent=2)
    else:
        pipeline = MAESDPipeline(settings=settings, seed=args.seed)
        report = pipeline.run(
            args.idea,
            max_iterations=args.loops,
            population_size=args.population,
            stagnation_limit=args.stagnation_limit,
            reference_structure_path=args.reference_structure,
        )
        payload = report.to_json()

    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
