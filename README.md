# MAESD: Multi-Agent Evolutionary Protein Design

![figure1](./picture/figure%201.png)

This repository provides a modular implementation scaffold for the MAESD paper:

1. `IntentRecognitionAgent` translates natural-language requirements into GO, EC, domain, motif, and optimization constraints.
2. `EvolutionaryLoop` runs generation, structure prediction, SGHFS-style screening, and Pareto-based selection.
3. Model backends are pluggable, with reserved interfaces for `ProGen2`, `ProteinMPNN`, and `AlphaFold2`.

## Project Structure

```text
agents/maesd/
  adapters/
    base.py
    mock.py
    external.py
    registry.py
  config.py
  ira.py
  screening.py
  decision.py
  orchestrator.py
  schema.py
```

## Installation

```bash
pip install -r requirements.txt
python setup.py install
```

## Quick Start

Run the default mock workflow:

```bash
python main.py --input "Design a thermostable membrane hydrolase with zinc binding activity" --output result.json
```

Run with explicit settings:

```bash
python main.py --config config/maesd.example.yaml --input "Create a salt-tolerant esterase with membrane compatibility and length 220 aa." --loops 4 --population 12
```

Use a real reference structure for ProteinMPNN-driven refinement:

```bash
python main.py --config config/maesd.real-backends.example.yaml --reference-structure path\to\target_backbone.pdb --input "Design a zinc-binding hydrolase with thermostability"
```

## Backend Integration

The system runs out of the box with mock adapters, and already reserves integration points for real tools:

- `generation.provider: mock | progen2`
- `refinement.provider: mock | proteinmpnn`
- `structure.provider: mock | alphafold2`

To connect a real model, implement the corresponding adapter in [agents/maesd/adapters/external.py](/G:/MAESD-main/agents/maesd/adapters/external.py). The orchestration layer is already separated, so you only need to return:

- generated `DesignCandidate` objects for ProGen2
- refined `DesignCandidate` objects for ProteinMPNN
- `StructureEvaluation` objects for AlphaFold2

The command-line bridges already support two integration styles:

- Default command builders for ProteinMPNN, AlphaFold2, and ColabFold
- Full command override with `extra.command`, using placeholders such as `{reference_structure_path}`, `{input_fasta}`, `{output_dir}`, and `{population_size}`

Example files:

- [config/maesd.example.yaml](/G:/MAESD-main/config/maesd.example.yaml)
- [config/maesd.real-backends.example.yaml](/G:/MAESD-main/config/maesd.real-backends.example.yaml)
- [config/maesd.machine-detected.yaml](/G:/MAESD-main/config/maesd.machine-detected.yaml)

## IRA External Knowledge Connectors

`IntentRecognitionAgent` now supports user-provided external knowledge sources for terminology translation, intent hints, motif hints, and custom GO/EC/domain mappings.

Set `MAESD_IRA_CONNECTORS` to a JSON/YAML connector config, or pass `connector_config_path=...` when constructing the agent.

Supported connector kinds:

- `file`: read a local `.json`, `.yaml`, `.csv`, or `.tsv` dataset
- `command`: run an external script or wrapper that returns JSON records on stdout

Connector config example:

```yaml
connectors:
  - name: local-terms
    kind: file
    path: C:/data/ira_terms.json
  - name: remote-wrapper
    kind: command
    command:
      - python
      - C:/tools/query_ira_terms.py
      - "{query}"
```

External record schema example:

```json
[
  {
    "id": "ext-esterase",
    "label": "custom esterase scaffold",
    "description": "Custom terminology mapping",
    "aliases": ["beta propeller esterase"],
    "go_terms": [{"id": "GO:0004091", "name": "carboxylesterase activity"}],
    "ec_numbers": [{"id": "EC 3.1.1.1", "name": "carboxylesterase"}],
    "domains": [{"id": "IPR999999", "name": "Beta-propeller esterase scaffold"}],
    "motifs": ["GXSXG"],
    "goals": ["thermostability"],
    "intent_hints": ["Use beta-propeller esterase terminology"],
    "translation_hints": ["Translate beta propeller esterase to carboxylesterase scaffold"],
    "metal_constraints": [{"ion": "ZN", "coordinating_residues": ["H", "E"]}],
    "catalytic_constraints": [{"type": "triad", "residues": ["S", "H", "D"]}]
  }
]
```

## IRA Ontology Files

`IntentRecognitionAgent` and `SemanticReasoner` now support ontology-driven semantic reasoning. By default they use the built-in ontology from [agents/maesd/knowledge.py](/G:/MAESD-main/agents/maesd/knowledge.py), and you can extend or override it with a JSON/YAML ontology file.

Set `MAESD_ONTOLOGY_PATH` to a JSON/YAML ontology file, or pass `ontology_path=...` when constructing `IntentRecognitionAgent`.

Supported ontology sections:

- `term_synonyms`
- `go_library`
- `ec_library`
- `domain_library`
- `motif_library`
- `go_hierarchy`
- `ec_hierarchy`
- `cross_library_alignments`
- `disambiguation_rules`

Ontology file example:

```yaml
term_synonyms:
  scaffoldase:
    - scaffoldase
    - scaffold hydrolase
go_library:
  scaffoldase:
    go: GO:1234567
    description: scaffoldase activity
ec_library:
  scaffoldase:
    ec: EC 3.9.9.-
    description: scaffoldase enzyme family
domain_library:
  scaffold:
    name: scaffold interaction domain
    accession: IPR999998
motif_library:
  scaffoldase: GXSQG
go_hierarchy:
  GO:1234567:
    - id: GO:0003824
      name: catalytic activity
ec_hierarchy:
  EC 3.9.9.-:
    - id: EC 3.-.-.-
      name: hydrolases
cross_library_alignments:
  scaffoldase:
    go: GO:1234567
    ec: EC 3.9.9.-
    domain: IPR999998
disambiguation_rules:
  binding:
    scaffold:
      boost:
        "domain:IPR999998": 0.55
      translation_hint: prefer scaffold-binding interpretation
      goal: scaffold_targeting
      motif: GXSQG
```

External ontology content is merged with the built-in defaults, so you can ship a small project-specific ontology instead of rewriting the whole knowledge base.

## Expert Tool Protocols

Decision-layer experts can now consume tool-augmented signals through per-expert command hooks:

- `MAESD_STRUCTURAL_EXPERT_TOOL_CMD`
- `MAESD_FUNCTION_EXPERT_TOOL_CMD`
- `MAESD_DEVELOPABILITY_EXPERT_TOOL_CMD`
- `MAESD_BINDING_EXPERT_TOOL_CMD`

Available placeholders in each command:

- `{sequence}`
- `{prompt}`
- `{pdb_path}`
- `{candidate_origin}`
- `{iteration}`
- `{output_dir}`
- `{output_json}`
- `{expert_name}`

The loader supports two common bioinformatics integration styles:

1. Print a JSON payload to stdout
2. Write a JSON result file to `{output_json}` or another JSON file under `{output_dir}`

Stdout/file payloads may use either a flat `metrics` block or tool-like nested sections.

Structural expert example:

```json
{
  "source": "foldmason",
  "summary": {"fold_confidence": 0.83, "topology_score": 0.79, "tool_version": "1.2"},
  "qa": {"global_score": 0.83},
  "notes": ["result emitted as file payload"]
}
```

Function expert example:

```json
{
  "source": "p2rank-like-site-detector",
  "sites": {"active_site_probability": 0.81},
  "motifs": {"retention": 0.88},
  "summary": {"site_probability": 0.81}
}
```

Developability expert example:

```json
{
  "source": "camSol-like-tool",
  "developability": {
    "solubility_score": 0.77,
    "aggregation_risk": 0.18
  }
}
```

Binding expert example:

```json
{
  "source": "vina-like-docking",
  "docking": {"normalized_score": 0.80, "pose_agreement": 0.76},
  "cofactor": {"fit_score": 0.82}
}
```

## Machine Detection Notes

On the current machine, auto-detection found local Python installations and Conda environments, but did not find runnable `ProteinMPNN`, `colabfold_batch`, or `run_alphafold.py` entrypoints. A machine-local template with detected paths is provided in [config/maesd.machine-detected.yaml](/G:/MAESD-main/config/maesd.machine-detected.yaml).

## Notes

- The current SGHFS logic is a lightweight local approximation for development and integration testing.
- The mock backends are suitable for project scaffolding, interface validation, and dry-run experiments.
- Real biological deployment should replace mock scoring with validated structure, energy, and function pipelines.

## Acknowledgements

The [system](https://github.com/nnnnnnz/MAESD/tree/master/agents/system), [action_bank](https://github.com/nnnnnnz/MAESD/tree/master/agents/actions/action_bank), and [role_bank](https://github.com/nnnnnnz/MAESD/tree/master/agents/roles/role_bank) of this code base are built using [MetaGPT](https://github.com/geekan/MetaGPT).
