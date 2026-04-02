import json
import os
from pathlib import Path

from agents.maesd import MAESDPipeline, MAESDSettings, run_maesd_in_environment
from agents.maesd.adapters.registry import (
    build_generation_backend,
    build_refinement_backend,
    build_structure_backend,
)
from agents.maesd.adapters.external import ExternalAlphaFold2Adapter, ExternalProteinMPNNAdapter
from agents.maesd.config import BackendConfig
from agents.maesd.pipeline import DecisionExpert, DesignCandidate, IntentRecognitionAgent, ScreeningScores
from agents.maesd.schema import DesignConstraints, DomainConstraint
from agents.maesd.adapters.base import RefinementRequest, StructurePredictionRequest
from agents.maesd.structure_analysis import analyze_structure_file, compute_sghfs_details, aggregate_sghfs


def test_ira_extracts_constraints_from_prompt():
    os.environ["MAESD_DISABLE_RETRIEVAL"] = "1"
    ira = IntentRecognitionAgent()
    constraints = ira.parse(
        "Design a thermostable membrane hydrolase with zinc binding activity and catalytic triad support."
    )

    assert constraints.target_length >= 180
    assert any(term.identifier.startswith("GO:") for term in constraints.go_terms)
    assert any(domain.accession == "IPR020635" for domain in constraints.domains)
    assert constraints.motifs
    assert constraints.metadata["metal_constraints"]
    assert constraints.metadata["catalytic_constraints"]
    assert constraints.metadata["semantic_trace"]
    assert "semantic-reasoning" in constraints.metadata["translation_strategy"]


def test_ira_performs_deeper_semantic_reasoning():
    os.environ["MAESD_DISABLE_RETRIEVAL"] = "1"
    ira = IntentRecognitionAgent()
    constraints = ira.parse("Design a heat-stable zinc hydrolase for membrane-associated hydrolysis with strong binding.")

    assert any(term.identifier == "GO:0016787" for term in constraints.go_terms)
    assert any(term.identifier == "EC 3.-.-.-" for term in constraints.ec_numbers)
    assert any(term.identifier == "GO:0003824" for term in constraints.go_terms)
    assert any(domain.accession == "IPR013087" for domain in constraints.domains)
    assert constraints.metadata["cross_library_links"]
    assert constraints.metadata["go_ancestor_terms"]
    assert constraints.metadata["ec_ancestor_terms"]
    assert any("prefer metal-binding interpretation" in hint for hint in constraints.metadata["external_translation_hints"])


def test_ira_supports_configurable_ontology_file(tmp_path):
    os.environ["MAESD_DISABLE_RETRIEVAL"] = "1"
    ontology_path = tmp_path / "custom_ontology.yaml"
    ontology_path.write_text(
        "\n".join(
            [
                "term_synonyms:",
                "  scaffoldase:",
                "    - scaffoldase",
                "    - scaffold hydrolase",
                "go_library:",
                "  scaffoldase:",
                "    go: GO:1234567",
                "    description: scaffoldase activity",
                "ec_library:",
                "  scaffoldase:",
                "    ec: EC 3.9.9.-",
                "    description: scaffoldase enzyme family",
                "domain_library:",
                "  scaffold:",
                "    name: scaffold interaction domain",
                "    accession: IPR999998",
                "motif_library:",
                "  scaffoldase: GXSQG",
                "go_hierarchy:",
                "  GO:1234567:",
                "    - id: GO:0003824",
                "      name: catalytic activity",
                "ec_hierarchy:",
                "  EC 3.9.9.-:",
                "    - id: EC 3.-.-.-",
                "      name: hydrolases",
                "cross_library_alignments:",
                "  scaffoldase:",
                "    go: GO:1234567",
                "    ec: EC 3.9.9.-",
                "    domain: IPR999998",
                "disambiguation_rules:",
                "  binding:",
                "    scaffold:",
                "      boost:",
                '        "domain:IPR999998": 0.55',
                "      translation_hint: prefer scaffold-binding interpretation",
                "      goal: scaffold_targeting",
                "      motif: GXSQG",
            ]
        ),
        encoding="utf-8",
    )

    ira = IntentRecognitionAgent(ontology_path=str(ontology_path))
    constraints = ira.parse("Design a scaffoldase with scaffold binding activity.")

    assert any(term.identifier == "GO:1234567" for term in constraints.go_terms)
    assert any(term.identifier == "EC 3.9.9.-" for term in constraints.ec_numbers)
    assert any(term.identifier == "GO:0003824" for term in constraints.go_terms)
    assert any(domain.accession == "IPR999998" for domain in constraints.domains)
    assert "GXSQG" in constraints.motifs
    assert "scaffold_targeting" in constraints.optimization_goals
    assert any(link.get("canonical_term") == "scaffoldase" for link in constraints.metadata["cross_library_links"])
    assert any("prefer scaffold-binding interpretation" in hint for hint in constraints.metadata["external_translation_hints"])
    assert constraints.metadata["ontology_summary"]["uses_external_ontology"] is True
    assert constraints.metadata["ontology_summary"]["source_path"].endswith("custom_ontology.yaml")
    assert "ontology-config" in constraints.metadata["translation_strategy"]


def test_ira_supports_external_file_connector(tmp_path):
    dataset_path = tmp_path / "external_terms.json"
    config_path = tmp_path / "ira_connectors.yaml"
    dataset_path.write_text(
        json.dumps(
            [
                {
                    "id": "ext-esterase",
                    "label": "custom esterase scaffold",
                    "description": "Local dataset term mapping for a beta-propeller esterase scaffold with zinc support.",
                    "aliases": ["beta propeller esterase", "custom esterase"],
                    "go_terms": [{"id": "GO:0004091", "name": "carboxylesterase activity", "description": "Hydrolyzes carboxylic esters."}],
                    "ec_numbers": [{"id": "EC 3.1.1.1", "name": "carboxylesterase", "description": "Classic esterase annotation."}],
                    "domains": [{"id": "IPR999999", "name": "Beta-propeller esterase scaffold", "description": "External dataset domain"}],
                    "motifs": ["GXSXG"],
                    "goals": ["thermostability"],
                    "intent_hints": ["Use beta-propeller esterase terminology"],
                    "translation_hints": ["Translate beta propeller esterase to carboxylesterase scaffold"],
                    "metal_constraints": [{"ion": "ZN", "coordinating_residues": ["H", "E"], "preferred_geometry": "tetrahedral"}],
                    "catalytic_constraints": [{"type": "triad", "residues": ["S", "H", "D"]}],
                }
            ]
        ),
        encoding="utf-8",
    )
    config_path.write_text(
        "connectors:\n  - name: local-dataset\n    kind: file\n    path: " + str(dataset_path).replace("\\", "/") + "\n",
        encoding="utf-8",
    )

    ira = IntentRecognitionAgent(connector_config_path=str(config_path))
    constraints = ira.parse("Design a beta propeller esterase with zinc binding activity.")

    assert any(term.identifier == "GO:0004091" for term in constraints.go_terms)
    assert any(term.identifier == "EC 3.1.1.1" for term in constraints.ec_numbers)
    assert any(domain.accession == "IPR999999" for domain in constraints.domains)
    assert "GXSXG" in constraints.motifs
    assert "thermostability" in constraints.optimization_goals
    assert constraints.metadata["external_connectors"] == ["local-dataset"]
    assert constraints.metadata["external_knowledge_hits"]


def test_ira_supports_external_command_connector(tmp_path):
    script = Path("G:/MAESD-main/test/fixtures/fake_cli_backends.py")
    config_path = tmp_path / "ira_command_connectors.json"
    config_path.write_text(
        json.dumps(
            {
                "connectors": [
                    {
                        "name": "command-dataset",
                        "kind": "command",
                        "command": ["python", str(script), "ira_connector", "{query}"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    ira = IntentRecognitionAgent(connector_config_path=str(config_path))
    constraints = ira.parse("Design a zinc membrane hydrolase for hydrolysis.")

    assert any(domain.accession == "IPR036322" for domain in constraints.domains)
    assert "HXXH" in constraints.motifs
    assert any(entry.get("label") == "zinc membrane hydrolase" for entry in constraints.metadata["external_knowledge_hits"])
    assert any(item.get("ion") == "ZN" for item in constraints.metadata["metal_constraints"])


def test_decision_expert_returns_non_dominated_front():
    decider = DecisionExpert()
    strong = DesignCandidate(
        sequence="AAAA",
        origin="test",
        iteration=0,
        scores=ScreeningScores(0.8, 0.8, 0.8, 0.8, 0.8, 0.8),
    )
    dominated = DesignCandidate(
        sequence="BBBB",
        origin="test",
        iteration=0,
        scores=ScreeningScores(0.7, 0.7, 0.7, 0.7, 0.7, 0.7),
    )

    front = decider.pareto_front([strong, dominated])

    assert strong in front
    assert dominated not in front


def test_decision_expert_generates_multi_round_feedback():
    decider = DecisionExpert(review_rounds=2)
    constraints = DesignConstraints(
        original_prompt="design",
        intents=["design"],
        go_terms=[],
        ec_numbers=[],
        domains=[],
        motifs=["HXXH"],
        target_length=4,
        optimization_goals=["binding_affinity"],
        metadata={"metal_constraints": [{"ion": "ZN", "coordinating_residues": ["H", "D", "E"]}]},
    )
    candidate = DesignCandidate(
        sequence="AHDH",
        origin="test",
        iteration=0,
        scores=ScreeningScores(
            structural_score=0.78,
            energy_score=0.71,
            functional_score=0.82,
            fsm=0.8,
            smr=0.75,
            gci=0.78,
            backend_metrics={"normalized_energy": 0.74, "clash_score": 0.03},
            detailed_metrics={
                "global_reference_agreement": 0.76,
                "global_compactness": 0.74,
                "core_site_match": 0.9,
                "catalytic_site_geometry": 0.73,
                "pocket_score": 0.7,
                "motif_pocket_overlap": 0.8,
                "metal_binding_geometry": 0.69,
            },
        ),
    )

    reviewed = decider.review_candidates([candidate], constraints)

    assert reviewed[0].consensus_score > 0.0
    assert len(candidate.expert_feedback) == 8
    assert len(reviewed[0].rounds) == 2
    assert candidate.metadata["feedback_actions"]
    assert candidate.metadata["decision_lead_expert"]


def test_decision_expert_uses_tool_augmented_experts():
    script = Path("G:/MAESD-main/test/fixtures/fake_cli_backends.py")
    env_keys = {
        "MAESD_STRUCTURAL_EXPERT_TOOL_CMD": os.environ.get("MAESD_STRUCTURAL_EXPERT_TOOL_CMD"),
        "MAESD_FUNCTION_EXPERT_TOOL_CMD": os.environ.get("MAESD_FUNCTION_EXPERT_TOOL_CMD"),
        "MAESD_DEVELOPABILITY_EXPERT_TOOL_CMD": os.environ.get("MAESD_DEVELOPABILITY_EXPERT_TOOL_CMD"),
        "MAESD_BINDING_EXPERT_TOOL_CMD": os.environ.get("MAESD_BINDING_EXPERT_TOOL_CMD"),
    }
    os.environ["MAESD_STRUCTURAL_EXPERT_TOOL_CMD"] = f"python {script} expert_tool structural_expert"
    os.environ["MAESD_FUNCTION_EXPERT_TOOL_CMD"] = f"python {script} expert_tool function_expert"
    os.environ["MAESD_DEVELOPABILITY_EXPERT_TOOL_CMD"] = f"python {script} expert_tool developability_expert"
    os.environ["MAESD_BINDING_EXPERT_TOOL_CMD"] = f"python {script} expert_tool binding_expert"
    try:
        decider = DecisionExpert(review_rounds=1)
        constraints = DesignConstraints(
            original_prompt="design",
            intents=["design"],
            go_terms=[],
            ec_numbers=[],
            domains=[],
            motifs=["HXXH"],
            target_length=4,
            optimization_goals=["binding_affinity"],
            metadata={"metal_constraints": [{"ion": "ZN", "coordinating_residues": ["H", "D", "E"]}]},
        )
        candidate = DesignCandidate(
            sequence="AHDH",
            origin="test",
            iteration=0,
            scores=ScreeningScores(
                structural_score=0.65,
                energy_score=0.62,
                functional_score=0.66,
                fsm=0.66,
                smr=0.64,
                gci=0.63,
                backend_metrics={"normalized_energy": 0.61, "clash_score": 0.05},
                detailed_metrics={
                    "global_reference_agreement": 0.6,
                    "global_compactness": 0.62,
                    "core_site_match": 0.7,
                    "catalytic_site_geometry": 0.58,
                    "pocket_score": 0.61,
                    "motif_pocket_overlap": 0.59,
                    "metal_binding_geometry": 0.57,
                },
            ),
        )

        reviewed = decider.review_candidates([candidate], constraints)
    finally:
        for key, value in env_keys.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    assert reviewed[0].consensus_score > 0.7
    assert any("fold_confidence" in feedback.focus_metrics for feedback in candidate.expert_feedback)
    assert any("site_probability" in feedback.focus_metrics for feedback in candidate.expert_feedback)
    assert any("solubility_score" in feedback.focus_metrics for feedback in candidate.expert_feedback)
    assert any("docking_score" in feedback.focus_metrics for feedback in candidate.expert_feedback)
    assert any("Tool source:" in feedback.rationale for feedback in candidate.expert_feedback)


def test_decision_expert_supports_file_based_bioinformatics_tool_protocol():
    script = Path("G:/MAESD-main/test/fixtures/fake_cli_backends.py")
    env_keys = {
        "MAESD_STRUCTURAL_EXPERT_TOOL_CMD": os.environ.get("MAESD_STRUCTURAL_EXPERT_TOOL_CMD"),
        "MAESD_FUNCTION_EXPERT_TOOL_CMD": os.environ.get("MAESD_FUNCTION_EXPERT_TOOL_CMD"),
        "MAESD_DEVELOPABILITY_EXPERT_TOOL_CMD": os.environ.get("MAESD_DEVELOPABILITY_EXPERT_TOOL_CMD"),
        "MAESD_BINDING_EXPERT_TOOL_CMD": os.environ.get("MAESD_BINDING_EXPERT_TOOL_CMD"),
    }
    os.environ["MAESD_STRUCTURAL_EXPERT_TOOL_CMD"] = f"python {script} expert_tool_file structural_expert {{output_json}}"
    os.environ["MAESD_FUNCTION_EXPERT_TOOL_CMD"] = f"python {script} expert_tool_file function_expert {{output_json}}"
    os.environ["MAESD_DEVELOPABILITY_EXPERT_TOOL_CMD"] = f"python {script} expert_tool_file developability_expert {{output_json}}"
    os.environ["MAESD_BINDING_EXPERT_TOOL_CMD"] = f"python {script} expert_tool_file binding_expert {{output_json}}"
    try:
        decider = DecisionExpert(review_rounds=1)
        constraints = DesignConstraints(
            original_prompt="design",
            intents=["design"],
            go_terms=[],
            ec_numbers=[],
            domains=[],
            motifs=["HXXH"],
            target_length=4,
            optimization_goals=["binding_affinity"],
            metadata={"metal_constraints": [{"ion": "ZN", "coordinating_residues": ["H", "D", "E"]}]},
        )
        candidate = DesignCandidate(
            sequence="AHDH",
            origin="test",
            iteration=0,
            scores=ScreeningScores(
                structural_score=0.61,
                energy_score=0.59,
                functional_score=0.63,
                fsm=0.62,
                smr=0.6,
                gci=0.59,
                backend_metrics={"normalized_energy": 0.6, "clash_score": 0.05},
                detailed_metrics={
                    "global_reference_agreement": 0.58,
                    "global_compactness": 0.57,
                    "core_site_match": 0.66,
                    "catalytic_site_geometry": 0.55,
                    "pocket_score": 0.62,
                    "motif_pocket_overlap": 0.57,
                    "metal_binding_geometry": 0.54,
                },
            ),
        )
        reviewed = decider.review_candidates([candidate], constraints)
    finally:
        for key, value in env_keys.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    assert reviewed[0].consensus_score > 0.65
    assert any("tool_version=1.2" in feedback.rationale for feedback in candidate.expert_feedback)
    assert any(feedback.focus_metrics.get("site_probability", 0.0) >= 0.8 for feedback in candidate.expert_feedback)
    assert any(feedback.focus_metrics.get("solubility_score", 0.0) >= 0.7 for feedback in candidate.expert_feedback)
    assert any(feedback.focus_metrics.get("docking_score", 0.0) >= 0.75 for feedback in candidate.expert_feedback)


def test_pipeline_returns_json_serializable_report():
    os.environ["MAESD_DISABLE_RETRIEVAL"] = "1"
    settings = MAESDSettings.from_dict(
        {
            "generation": {"provider": "mock", "model_name": "progen2-mock"},
            "refinement": {"provider": "mock", "model_name": "proteinmpnn-mock"},
            "structure": {"provider": "mock", "model_name": "alphafold2-mock"},
            "seed": 11,
        }
    )
    pipeline = MAESDPipeline(settings=settings)
    report = pipeline.run(
        "Create a salt-tolerant enzyme with esterase activity, membrane compatibility, and length 220 aa.",
        max_iterations=3,
        population_size=10,
    )

    payload = json.loads(report.to_json())
    assert payload["constraints"]["target_length"] == 220
    assert payload["best_candidates"]
    assert payload["all_iterations"]
    assert payload["backend_summary"]["generation"] == "progen2-mock"
    assert "consensus_score" in payload["all_iterations"][0]
    assert "expert_rounds" in payload["all_iterations"][0]
    assert payload["best_candidates"][0]["expert_feedback"]


def test_environment_bridge_runs_maesd_pipeline():
    os.environ["MAESD_DISABLE_RETRIEVAL"] = "1"
    settings = MAESDSettings.from_dict(
        {
            "generation": {"provider": "mock", "model_name": "progen2-mock"},
            "refinement": {"provider": "mock", "model_name": "proteinmpnn-mock"},
            "structure": {"provider": "mock", "model_name": "alphafold2-mock"},
            "seed": 5,
        }
    )

    payload = run_maesd_in_environment(
        prompt="Design a zinc-binding hydrolase with membrane compatibility and catalytic triad support.",
        settings=settings,
        max_iterations=2,
        population_size=6,
        stagnation_limit=1,
    )

    assert payload["constraints"]["target_length"] >= 180
    assert payload["best_candidates"]
    assert payload["all_iterations"]
    assert payload["best_candidates"][0]["sequence"]


def test_backend_registry_builds_mock_adapters():
    settings = MAESDSettings()
    generation = build_generation_backend(settings.generation)
    refinement = build_refinement_backend(settings.refinement)
    structure = build_structure_backend(settings.structure)

    assert generation.name == "progen2"
    assert refinement.name == "proteinmpnn"
    assert structure.name == "alphafold2"


def test_external_proteinmpnn_adapter_executes_cli(tmp_path):
    pdb_path = tmp_path / "target.pdb"
    pdb_path.write_text("ATOM\n", encoding="utf-8")
    script = Path("G:/MAESD-main/test/fixtures/fake_cli_backends.py")
    adapter = ExternalProteinMPNNAdapter(
        BackendConfig(
            provider="proteinmpnn",
            model_name="proteinmpnn-cli",
            extra={
                "command": [
                    "python",
                    str(script),
                    "proteinmpnn",
                    "--pdb_path",
                    "{reference_structure_path}",
                    "--out_folder",
                    "{output_dir}",
                    "--num_seq_per_target",
                    "{population_size}",
                ]
            },
        )
    )
    constraints = DesignConstraints(
        original_prompt="design",
        intents=["design"],
        go_terms=[],
        ec_numbers=[],
        domains=[DomainConstraint(name="test", accession="IPR0", evidence="unit")],
        motifs=[],
        target_length=20,
        optimization_goals=["general_function_preservation"],
        reference_structure_path=str(pdb_path),
    )
    request = RefinementRequest(constraints=constraints, parents=[], population_size=3, iteration=1, seed=7)

    candidates = adapter.refine(request)

    assert len(candidates) == 3
    assert all(candidate.origin == "proteinmpnn-cli" for candidate in candidates)


def test_external_alphafold_adapter_executes_cli(tmp_path):
    script = Path("G:/MAESD-main/test/fixtures/fake_cli_backends.py")
    adapter = ExternalAlphaFold2Adapter(
        BackendConfig(
            provider="alphafold2",
            model_name="colabfold-cli",
            extra={
                "command": [
                    "python",
                    str(script),
                    "colabfold",
                    "{input_fasta}",
                    "{output_dir}",
                ]
            },
        )
    )
    candidate = DesignCandidate(sequence="ACDEFGHIKLMNPQRSTVWY", origin="test", iteration=0)
    constraints = DesignConstraints(
        original_prompt="predict",
        intents=["predict"],
        go_terms=[],
        ec_numbers=[],
        domains=[],
        motifs=[],
        target_length=20,
        optimization_goals=["general_function_preservation"],
    )

    result = adapter.predict(StructurePredictionRequest(constraints=constraints, candidate=candidate, iteration=0))

    assert result.source in {"alphafold2", "colabfold_batch"}
    assert result.confidence > 0.8
    assert "pdb_path" in result.artifacts


def test_structure_analysis_extracts_contact_hbond_and_pocket_metrics(tmp_path):
    pdb_path = tmp_path / "mini.pdb"
    pdb_path.write_text(
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
    features = analyze_structure_file(str(pdb_path), "ASHLY")
    details = compute_sghfs_details("ASHLY", ["HXXH"], features)
    aggregated = aggregate_sghfs(details)

    assert features is not None
    assert features.hbond_density >= 0.0
    assert features.salt_bridge_density >= 0.0
    assert features.residue_contact_ratio >= 0.0
    assert "microenvironment_pocket_support" in details
    assert "microenvironment_salt_bridge_support" in details
    assert "global_residue_contact_ratio" in details
    assert set(aggregated) == {"fsm", "smr", "gci"}


def test_structure_analysis_uses_external_fpocket_dssp_and_hbond_tools(tmp_path):
    script = Path("G:/MAESD-main/test/fixtures/fake_cli_backends.py")
    pdb_path = tmp_path / "tool_backed.pdb"
    pdb_path.write_text(
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

    original_env = {
        "MAESD_FPOCKET_CMD": os.environ.get("MAESD_FPOCKET_CMD"),
        "MAESD_DSSP_CMD": os.environ.get("MAESD_DSSP_CMD"),
        "MAESD_HBOND_CMD": os.environ.get("MAESD_HBOND_CMD"),
    }
    os.environ["MAESD_FPOCKET_CMD"] = f'python {script} fpocket -f {{pdb_path}}'
    os.environ["MAESD_DSSP_CMD"] = f'python {script} dssp -i {{pdb_path}}'
    os.environ["MAESD_HBOND_CMD"] = f'python {script} hbonds {{pdb_path}}'
    try:
        features = analyze_structure_file(str(pdb_path), "ASHLY")
        details = compute_sghfs_details("ASHLY", ["HXY"], features)
        aggregated = aggregate_sghfs(details)
    finally:
        for key, value in original_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    assert features is not None
    assert features.secondary_structure_source == "dssp"
    assert features.pocket_score > 0.7
    assert features.pocket_residue_indices
    assert features.hbond_density >= 1.25
    assert features.salt_bridge_density >= 0.33
    assert details["motif_pocket_overlap"] > 0.0
    assert details["microenvironment_salt_bridge_support"] > 0.0
    assert details["global_secondary_structure_agreement"] > 0.0
    assert aggregated["smr"] > 0.0


def test_structure_analysis_uses_energy_tool_and_active_site_constraints(tmp_path):
    script = Path("G:/MAESD-main/test/fixtures/fake_cli_backends.py")
    pdb_path = tmp_path / "active_site.pdb"
    pdb_path.write_text(
        "\n".join(
            [
                "ATOM      1  N   ASP A   1      10.000  10.000  10.000  1.00 85.00           N",
                "ATOM      2  CA  ASP A   1      11.200  10.000  10.000  1.00 85.00           C",
                "ATOM      3  OD1 ASP A   1      11.900   8.900  10.200  1.00 84.00           O",
                "ATOM      4  N   HIS A   2      12.100  11.000   9.600  1.00 86.00           N",
                "ATOM      5  CA  HIS A   2      13.300  11.100   9.400  1.00 86.00           C",
                "ATOM      6  ND1 HIS A   2      13.800  10.000   8.700  1.00 84.00           N",
                "ATOM      7  N   SER A   3      14.000  12.200   9.900  1.00 87.00           N",
                "ATOM      8  CA  SER A   3      15.200  12.400   9.700  1.00 87.00           C",
                "ATOM      9  OG  SER A   3      15.600  11.400   8.900  1.00 86.00           O",
                "ATOM     10  N   HIS A   4      16.000  13.300  10.300  1.00 86.00           N",
                "ATOM     11  CA  HIS A   4      17.200  13.500  10.100  1.00 86.00           C",
                "ATOM     12  NE2 HIS A   4      17.400  12.300   9.400  1.00 84.00           N",
                "HETATM   13 ZN   ZN  A 101      14.800  10.500   9.200  1.00 70.00          ZN",
                "TER",
            ]
        ),
        encoding="utf-8",
    )
    metadata = {
        "metal_constraints": [{"ion": "ZN", "coordinating_residues": ["H", "D", "H"], "preferred_geometry": "tetrahedral"}],
        "catalytic_constraints": [{"type": "triad", "residues": ["S", "H", "D"]}],
    }
    original_env = {"MAESD_ENERGY_CMD": os.environ.get("MAESD_ENERGY_CMD")}
    os.environ["MAESD_ENERGY_CMD"] = f'python {script} energy {{pdb_path}}'
    try:
        features = analyze_structure_file(str(pdb_path), "DHSH", metadata)
        details = compute_sghfs_details("DHSH", ["H"], features, constraint_metadata=metadata)
        aggregated = aggregate_sghfs(details)
    finally:
        if original_env["MAESD_ENERGY_CMD"] is None:
            os.environ.pop("MAESD_ENERGY_CMD", None)
        else:
            os.environ["MAESD_ENERGY_CMD"] = original_env["MAESD_ENERGY_CMD"]

    assert features is not None
    assert features.energy_source == "rosetta-cli"
    assert features.normalized_energy >= 0.86
    assert details["metal_binding_site_presence"] > 0.0
    assert details["metal_binding_geometry"] > 0.0
    assert details["catalytic_site_presence"] > 0.0
    assert details["catalytic_site_geometry"] > 0.0
    assert details["global_energy_favorability"] > 0.0
    assert aggregated["gci"] > 0.0
