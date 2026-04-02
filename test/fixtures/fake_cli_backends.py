from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    mode = sys.argv[1]
    if mode == "proteinmpnn":
        return run_fake_proteinmpnn(sys.argv[2:])
    if mode == "colabfold":
        return run_fake_colabfold(sys.argv[2:])
    if mode == "fpocket":
        return run_fake_fpocket(sys.argv[2:])
    if mode == "dssp":
        return run_fake_dssp(sys.argv[2:])
    if mode == "hbonds":
        return run_fake_hbonds(sys.argv[2:])
    if mode == "energy":
        return run_fake_energy(sys.argv[2:])
    if mode == "ira_connector":
        return run_fake_ira_connector(sys.argv[2:])
    if mode == "expert_tool":
        return run_fake_expert_tool(sys.argv[2:])
    if mode == "expert_tool_file":
        return run_fake_expert_tool_file(sys.argv[2:])
    raise SystemExit(f"Unknown mode: {mode}")


def run_fake_proteinmpnn(args: list[str]) -> int:
    parsed = _parse_pairs(args)
    pdb_path = Path(parsed["--pdb_path"])
    out_folder = Path(parsed["--out_folder"])
    num = int(parsed.get("--num_seq_per_target", "1"))
    seq_dir = out_folder / "seqs"
    seq_dir.mkdir(parents=True, exist_ok=True)
    fasta_path = seq_dir / f"{pdb_path.stem}.fa"

    base = "ACDEFGHIKLMNPQRSTVWY"
    with fasta_path.open("w", encoding="utf-8") as handle:
        for idx in range(num):
            handle.write(f">sample_{idx}\n")
            handle.write((base * 3)[idx : idx + 20] + "\n")
    return 0


def run_fake_colabfold(args: list[str]) -> int:
    fasta_path = Path(args[0])
    output_dir = Path(args[1])
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = fasta_path.stem

    (output_dir / f"{stem}_unrelaxed_rank_001_model_1.pdb").write_text(
        "\n".join(
            [
                "ATOM      1  N   ALA A   1      11.104  13.207   9.242  1.00 90.00           N",
                "ATOM      2  CA  ALA A   1      12.004  12.300   8.500  1.00 90.00           C",
                "ATOM      3  O   ALA A   1      12.900  11.800   9.100  1.00 88.00           O",
                "ATOM      4  N   SER A   2      12.200  11.700   7.200  1.00 86.00           N",
                "ATOM      5  CA  SER A   2      13.100  10.850   6.420  1.00 86.00           C",
                "ATOM      6  OG  SER A   2      12.650   9.560   6.010  1.00 84.00           O",
                "ATOM      7  N   HIS A   3      14.380  11.200   6.210  1.00 87.00           N",
                "ATOM      8  CA  HIS A   3      15.290  10.400   5.420  1.00 87.00           C",
                "ATOM      9  ND1 HIS A   3      16.250   9.550   6.050  1.00 83.00           N",
                "ATOM     10  N   LEU A   4      15.000   9.600   4.180  1.00 85.00           N",
                "ATOM     11  CA  LEU A   4      15.820   8.760   3.320  1.00 85.00           C",
                "ATOM     12  N   TYR A   5      17.120   9.120   3.180  1.00 82.00           N",
                "ATOM     13  CA  TYR A   5      18.010   8.320   2.380  1.00 82.00           C",
                "ATOM     14  OH  TYR A   5      18.950   7.650   3.050  1.00 80.00           O",
                "TER",
            ]
        ),
        encoding="utf-8",
    )
    (output_dir / "ranking_debug.json").write_text(
        json.dumps({"plddts": {"model_1": 88.5}}),
        encoding="utf-8",
    )
    (output_dir / f"{stem}_scores_rank_001_model_1.json").write_text(
        json.dumps({"mean_plddt": 88.5, "ptm": 0.72, "iptm": 0.68}),
        encoding="utf-8",
    )
    return 0


def run_fake_fpocket(args: list[str]) -> int:
    parsed = _parse_pairs(args)
    pdb_path = Path(parsed["-f"])
    output_dir = pdb_path.parent / f"{pdb_path.stem}_out" / "pockets"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "pocket1_info.txt").write_text("Score : 72.5\nVolume : 145.0\n", encoding="utf-8")
    (output_dir / "pocket1_atm.pdb").write_text(
        "\n".join(
            [
                "ATOM      1  CA  HIS A   3      15.290  10.400   5.420  1.00 87.00           C",
                "ATOM      2  CA  TYR A   5      18.010   8.320   2.380  1.00 82.00           C",
                "TER",
            ]
        ),
        encoding="utf-8",
    )
    return 0


def run_fake_dssp(args: list[str]) -> int:
    parsed = _parse_pairs(args)
    output = Path(parsed.get("-o", "fake.dssp"))
    text = "\n".join(
        [
            "  #  RESIDUE AA STRUCTURE",
            "    1    1 A A              ",
            "    2    2 A S  H           ",
            "    3    3 A H  H           ",
            "    4    4 A L  E           ",
            "    5    5 A Y  E           ",
        ]
    )
    output.write_text(text, encoding="utf-8")
    print(text)
    return 0


def run_fake_hbonds(args: list[str]) -> int:
    print(json.dumps({"hbond_density": 1.25, "salt_bridge_density": 0.33}))
    return 0


def run_fake_energy(args: list[str]) -> int:
    print(json.dumps({"total_score": -18.6, "clash_score": 0.04, "normalized_energy": 0.86, "energy_source": "rosetta-cli"}))
    return 0


def run_fake_ira_connector(args: list[str]) -> int:
    print(
        json.dumps(
            {
                "records": [
                    {
                        "id": "cmd-zinc-hydrolase",
                        "label": "zinc membrane hydrolase",
                        "description": "Command-backed external terminology mapping for zinc-binding membrane hydrolases.",
                        "aliases": ["zn hydrolase", "membrane hydrolase"],
                        "go_terms": [{"id": "GO:0016787", "name": "hydrolase activity", "description": "Acts on chemical bonds."}],
                        "domains": [{"id": "IPR036322", "name": "Custom membrane scaffold", "description": "Command provided scaffold"}],
                        "motifs": ["HXXH"],
                        "goals": ["binding_affinity"],
                        "intent_hints": ["Preserve zinc-assisted hydrolysis"],
                        "translation_hints": ["translate zn hydrolase to zinc membrane hydrolase"],
                        "metal_constraints": [{"ion": "ZN", "coordinating_residues": ["H", "D", "E"], "preferred_geometry": "tetrahedral"}],
                    }
                ]
            }
        )
    )
    return 0


def run_fake_expert_tool(args: list[str]) -> int:
    expert = args[0] if args else "generic"
    payload = {
        "structural_expert": {
            "source": "foldseek-like-tool",
            "metrics": {"fold_confidence": 0.91, "topology_score": 0.87},
            "notes": ["external structural QA matched a high-confidence fold"],
        },
        "function_expert": {
            "source": "active-site-tool",
            "metrics": {"site_probability": 0.89, "motif_retention": 0.93},
            "notes": ["functional-site detector preserved catalytic motif"],
        },
        "developability_expert": {
            "source": "developability-tool",
            "metrics": {"solubility_score": 0.81, "aggregation_risk": 0.12},
            "notes": ["low aggregation risk predicted"],
        },
        "binding_expert": {
            "source": "docking-tool",
            "metrics": {"docking_score": 0.88, "pose_agreement": 0.84, "cofactor_fit": 0.9},
            "notes": ["binding pose agrees with annotated pocket"],
        },
    }
    print(json.dumps(payload.get(expert, {"source": "generic-tool", "metrics": {}, "notes": []})))
    return 0


def run_fake_expert_tool_file(args: list[str]) -> int:
    expert = args[0] if args else "generic"
    output_json = Path(args[1]) if len(args) > 1 else Path("result.json")
    payload = {
        "structural_expert": {
            "source": "foldmason",
            "summary": {"fold_confidence": 0.83, "topology_score": 0.79, "tool_version": "1.2"},
            "qa": {"global_score": 0.83},
            "notes": ["result emitted as file payload"],
        },
        "function_expert": {
            "source": "p2rank-like-site-detector",
            "summary": {"site_probability": 0.81, "tool_version": "2.0"},
            "sites": {"active_site_probability": 0.81},
            "motifs": {"retention": 0.88},
            "notes": ["site prediction stored in result file"],
        },
        "developability_expert": {
            "source": "camSol-like-tool",
            "summary": {"solubility": 0.77, "status": "ok"},
            "developability": {"solubility_score": 0.77, "aggregation_risk": 0.18},
        },
        "binding_expert": {
            "source": "vina-like-docking",
            "summary": {"docking_score": 0.8, "cofactor_fit": 0.82},
            "docking": {"normalized_score": 0.8, "pose_agreement": 0.76},
            "cofactor": {"fit_score": 0.82},
        },
    }
    output_json.write_text(json.dumps(payload.get(expert, {"source": "generic-file-tool", "summary": {}})), encoding="utf-8")
    return 0


def _parse_pairs(args: list[str]) -> dict[str, str]:
    parsed: dict[str, str] = {}
    idx = 0
    while idx < len(args):
        key = args[idx]
        value = args[idx + 1] if idx + 1 < len(args) else ""
        parsed[key] = value
        idx += 2
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
