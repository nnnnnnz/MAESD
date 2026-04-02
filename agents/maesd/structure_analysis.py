from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import tempfile
from dataclasses import dataclass
from math import exp, sqrt
from pathlib import Path
from typing import Dict, List, Sequence, Tuple


HYDROPHOBIC = set("AILMFWVY")
CHARGED = set("DEKRH")
POLAR = set("STNQCY")
DONOR_ACCEPTOR = set("DENQHSTYCKR")
NEGATIVE = set("DE")
POSITIVE = set("KRH")
METAL_ELEMENTS = {"ZN", "MG", "CA", "MN", "FE", "CU", "CO", "NI"}
BACKBONE_ATOMS = {"N", "CA", "C", "O"}
REACTIVE_ATOMS = {
    "S": ("OG",),
    "T": ("OG1",),
    "Y": ("OH",),
    "C": ("SG",),
    "H": ("ND1", "NE2", "NE", "ND"),
    "D": ("OD1", "OD2", "OE1", "OE2"),
    "E": ("OE1", "OE2", "OD1", "OD2"),
    "K": ("NZ",),
    "R": ("NH1", "NH2", "NE"),
    "N": ("ND2", "OD1"),
    "Q": ("NE2", "OE1"),
}


@dataclass
class ResiduePoint:
    index: int
    name: str
    coord: Tuple[float, float, float]
    b_factor: float


@dataclass
class AtomRecord:
    atom_name: str
    residue_name: str
    residue_label: str
    residue_index: int
    coord: Tuple[float, float, float]
    element: str
    b_factor: float
    record_type: str


@dataclass
class StructureFeatures:
    residues: List[ResiduePoint]
    atoms: List[AtomRecord]
    sequence: str
    contact_density: float
    radius_of_gyration: float
    compactness: float
    surface_fraction: float
    helix_like_fraction: float
    sheet_like_fraction: float
    residue_contact_ratio: float
    hbond_density: float
    salt_bridge_density: float
    pocket_score: float
    pocket_volume_hint: float
    motif_pocket_overlap: float
    pocket_residue_indices: List[int]
    secondary_structure_source: str
    normalized_energy: float
    raw_energy: float
    clash_score: float
    energy_source: str
    artifact_metrics: Dict[str, float]


def analyze_structure_file(
    path: str | None,
    expected_sequence: str = "",
    constraint_metadata: Dict[str, object] | None = None,
) -> StructureFeatures | None:
    if not path:
        return None
    pdb_path = Path(path)
    if not pdb_path.exists():
        return None
    residues, atoms = _read_atom_records(pdb_path)
    if not residues:
        return None
    sequence = "".join(res.name for res in residues)
    coords = [res.coord for res in residues]
    contact_density = _contact_density(coords, cutoff=8.0)
    residue_contact_ratio = _residue_contact_ratio(atoms)
    hbond_density, salt_bridge_density = _interaction_features(pdb_path, atoms)
    radius_of_gyration = _radius_of_gyration(coords)
    compactness = len(coords) / max(radius_of_gyration, 1e-6)
    surface_fraction = _surface_fraction(coords)
    helix_like_fraction, sheet_like_fraction, secondary_source = _secondary_structure_features(pdb_path, residues)
    pocket_score, pocket_volume_hint, pocket_residue_indices = _pocket_features(pdb_path, residues, atoms)
    normalized_energy, raw_energy, clash_score, energy_source = _energy_features(pdb_path, residues, atoms)
    artifact_metrics = {
        "residue_count": float(len(residues)),
        "mean_b_factor": sum(res.b_factor for res in residues) / len(residues),
    }
    if expected_sequence:
        artifact_metrics["sequence_coverage"] = _sequence_coverage(sequence, expected_sequence)
    if constraint_metadata:
        metal_constraints = constraint_metadata.get("metal_constraints", [])
        catalytic_constraints = constraint_metadata.get("catalytic_constraints", [])
        artifact_metrics["metal_constraint_count"] = float(len(metal_constraints)) if isinstance(metal_constraints, list) else 0.0
        artifact_metrics["catalytic_constraint_count"] = (
            float(len(catalytic_constraints)) if isinstance(catalytic_constraints, list) else 0.0
        )
    return StructureFeatures(
        residues=residues,
        atoms=atoms,
        sequence=sequence,
        contact_density=contact_density,
        radius_of_gyration=radius_of_gyration,
        compactness=compactness,
        surface_fraction=surface_fraction,
        helix_like_fraction=helix_like_fraction,
        sheet_like_fraction=sheet_like_fraction,
        residue_contact_ratio=residue_contact_ratio,
        hbond_density=hbond_density,
        salt_bridge_density=salt_bridge_density,
        pocket_score=pocket_score,
        pocket_volume_hint=pocket_volume_hint,
        motif_pocket_overlap=0.0,
        pocket_residue_indices=pocket_residue_indices,
        secondary_structure_source=secondary_source,
        normalized_energy=normalized_energy,
        raw_energy=raw_energy,
        clash_score=clash_score,
        energy_source=energy_source,
        artifact_metrics=artifact_metrics,
    )


def compute_sghfs_details(
    sequence: str,
    motifs: Sequence[str],
    structure: StructureFeatures | None,
    reference: StructureFeatures | None = None,
    optimization_goals: Sequence[str] | None = None,
    constraint_metadata: Dict[str, object] | None = None,
) -> Dict[str, float]:
    if structure is None:
        return {
            "core_site_match": 0.65 if motifs else 0.7,
            "core_site_accessibility": 0.5,
            "core_site_confidence": 0.5,
            "microenvironment_hydrophobic_balance": 0.5,
            "microenvironment_charge_balance": 0.5,
            "microenvironment_hbond_potential": 0.5,
            "microenvironment_salt_bridge_support": 0.5,
            "global_compactness": 0.5,
            "global_contact_order": 0.5,
            "global_reference_agreement": 0.5,
            "global_energy_favorability": 0.5,
            "metal_binding_site_presence": 0.5,
            "metal_binding_geometry": 0.5,
            "catalytic_site_presence": 0.5,
            "catalytic_site_geometry": 0.5,
        }

    motif_regions = _locate_motif_regions(sequence, motifs)
    site_scores = _site_level_metrics(sequence, structure, motif_regions)
    env_scores = _microenvironment_metrics(sequence, structure, motif_regions, optimization_goals or [])
    global_scores = _global_metrics(structure, reference)
    pocket_scores = _pocket_metrics(structure, motif_regions)
    active_site_scores = _active_site_metrics(sequence, structure, motif_regions, constraint_metadata or {})
    return {**site_scores, **env_scores, **global_scores, **pocket_scores, **active_site_scores}


def aggregate_sghfs(details: Dict[str, float]) -> Dict[str, float]:
    fsm = _mean(
        details.get("core_site_match", 0.0),
        details.get("core_site_accessibility", 0.0),
        details.get("core_site_confidence", 0.0),
        details.get("motif_pocket_overlap", 0.0),
        details.get("metal_binding_site_presence", 0.0),
        details.get("catalytic_site_presence", 0.0),
    )
    smr = _mean(
        details.get("microenvironment_hydrophobic_balance", 0.0),
        details.get("microenvironment_charge_balance", 0.0),
        details.get("microenvironment_hbond_potential", 0.0),
        details.get("microenvironment_salt_bridge_support", 0.0),
        details.get("microenvironment_pocket_support", 0.0),
        details.get("metal_binding_geometry", 0.0),
    )
    gci = _mean(
        details.get("global_compactness", 0.0),
        details.get("global_contact_order", 0.0),
        details.get("global_reference_agreement", 0.0),
        details.get("global_residue_contact_ratio", 0.0),
        details.get("global_secondary_structure_agreement", 0.0),
        details.get("global_energy_favorability", 0.0),
        details.get("catalytic_site_geometry", 0.0),
    )
    return {"fsm": fsm, "smr": smr, "gci": gci}


def _read_atom_records(path: Path) -> Tuple[List[ResiduePoint], List[AtomRecord]]:
    residues: List[ResiduePoint] = []
    atoms: List[AtomRecord] = []
    residue_lookup: Dict[Tuple[str, str, str], int] = {}
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        record_type = line[:6].strip().upper()
        if record_type not in {"ATOM", "HETATM"}:
            continue
        chain = line[21].strip() or "_"
        resseq = line[22:26].strip()
        icode = line[26].strip()
        residue_key = (chain, resseq, icode)
        try:
            x = float(line[30:38].strip())
            y = float(line[38:46].strip())
            z = float(line[46:54].strip())
            b = float(line[60:66].strip() or "0")
        except ValueError:
            continue
        residue_label = line[17:20].strip().upper()
        atom_name = line[12:16].strip()
        element = (line[76:78].strip() or atom_name[:1]).upper()
        if record_type == "ATOM" and residue_key not in residue_lookup:
            residue_lookup[residue_key] = len(residues)
            residues.append(ResiduePoint(index=len(residues), name=_three_to_one(residue_label), coord=(x, y, z), b_factor=b))
        residue_index = residue_lookup.get(residue_key, -1)
        if record_type == "ATOM" and atom_name == "CA" and residue_index >= 0:
            residues[residue_index] = ResiduePoint(index=residue_index, name=_three_to_one(residue_label), coord=(x, y, z), b_factor=b)
        atoms.append(
            AtomRecord(
                atom_name=atom_name,
                residue_name=_three_to_one(residue_label) if record_type == "ATOM" else residue_label,
                residue_label=residue_label,
                residue_index=residue_index,
                coord=(x, y, z),
                element=element,
                b_factor=b,
                record_type=record_type,
            )
        )
    return residues, atoms


def _locate_motif_regions(sequence: str, motifs: Sequence[str]) -> List[List[int]]:
    regions: List[List[int]] = []
    for motif in motifs:
        length = len(motif)
        for start in range(0, max(0, len(sequence) - length + 1)):
            if _motif_matches(sequence[start : start + length], motif):
                indices = [start + offset for offset, char in enumerate(motif) if char != "X"]
                if indices:
                    regions.append(indices)
                break
    return regions


def _motif_matches(window: str, motif: str) -> bool:
    if len(window) != len(motif):
        return False
    for observed, expected in zip(window, motif):
        if expected != "X" and observed != expected:
            return False
    return True


def _site_level_metrics(sequence: str, structure: StructureFeatures, motif_regions: Sequence[Sequence[int]]) -> Dict[str, float]:
    if not motif_regions:
        return {"core_site_match": 0.75, "core_site_accessibility": 0.65, "core_site_confidence": 0.7}
    matched = 0
    accessible = []
    confidences = []
    for region in motif_regions:
        present = [idx for idx in region if idx < len(structure.residues) and idx < len(sequence)]
        if len(present) == len(region):
            matched += 1
        for idx in present:
            density = _local_density(structure.residues, idx, cutoff=8.0)
            accessible.append(max(0.0, min(1.0, 1.0 - density / 18.0)))
            confidences.append(max(0.0, min(1.0, structure.residues[idx].b_factor / 100.0)))
    return {
        "core_site_match": matched / max(len(motif_regions), 1),
        "core_site_accessibility": _mean(*accessible) if accessible else 0.5,
        "core_site_confidence": _mean(*confidences) if confidences else 0.5,
    }


def _microenvironment_metrics(
    sequence: str,
    structure: StructureFeatures,
    motif_regions: Sequence[Sequence[int]],
    optimization_goals: Sequence[str],
) -> Dict[str, float]:
    if motif_regions:
        indices = sorted({idx for region in motif_regions for idx in region if idx < len(structure.residues)})
    else:
        center = len(structure.residues) // 2
        indices = [center] if structure.residues else []
    hydrophobic_scores = []
    charge_scores = []
    hbond_scores = []
    for idx in indices:
        neighbors = _neighbor_indices(structure.residues, idx, cutoff=8.0)
        residues = [sequence[n] for n in neighbors if n < len(sequence)]
        if not residues:
            continue
        hydro_ratio = sum(res in HYDROPHOBIC for res in residues) / len(residues)
        charge_ratio = sum(res in CHARGED for res in residues) / len(residues)
        hbond_ratio = sum(res in DONOR_ACCEPTOR for res in residues) / len(residues)
        desired_hydro = 0.48 if "membrane_localization" in optimization_goals else 0.34
        desired_charge = 0.18 if "binding_affinity" in optimization_goals else 0.14
        hydrophobic_scores.append(max(0.0, 1.0 - abs(hydro_ratio - desired_hydro) / 0.5))
        charge_scores.append(max(0.0, 1.0 - abs(charge_ratio - desired_charge) / 0.4))
        hbond_scores.append(max(0.0, min(1.0, hbond_ratio / 0.55)))
    return {
        "microenvironment_hydrophobic_balance": _mean(*hydrophobic_scores) if hydrophobic_scores else 0.5,
        "microenvironment_charge_balance": _mean(*charge_scores) if charge_scores else 0.5,
        "microenvironment_hbond_potential": max(
            _mean(*hbond_scores) if hbond_scores else 0.5,
            max(0.0, min(1.0, structure.hbond_density / 2.0)),
        ),
        "microenvironment_salt_bridge_support": max(0.0, min(1.0, structure.salt_bridge_density / 0.5)),
        "microenvironment_pocket_support": max(0.0, min(1.0, structure.pocket_score)),
    }


def _global_metrics(structure: StructureFeatures, reference: StructureFeatures | None) -> Dict[str, float]:
    compactness_score = max(0.0, min(1.0, structure.compactness / 8.0))
    contact_order = max(0.0, min(1.0, structure.contact_density / 20.0))
    if reference is None:
        reference_agreement = max(0.0, min(1.0, 1.0 - abs(structure.helix_like_fraction - 0.35) - abs(structure.sheet_like_fraction - 0.15) - abs(structure.surface_fraction - 0.45)))
        secondary_agreement = 1.0 if structure.secondary_structure_source != "proxy" else 0.7
    else:
        reference_agreement = max(
            0.0,
            min(
                1.0,
                1.0
                - abs(structure.compactness - reference.compactness) / max(reference.compactness, 1.0)
                - abs(structure.helix_like_fraction - reference.helix_like_fraction)
                - abs(structure.sheet_like_fraction - reference.sheet_like_fraction),
            ),
        )
        secondary_agreement = max(0.0, 1.0 - abs(structure.helix_like_fraction - reference.helix_like_fraction) - abs(structure.sheet_like_fraction - reference.sheet_like_fraction))
    return {
        "global_compactness": compactness_score,
        "global_contact_order": contact_order,
        "global_reference_agreement": reference_agreement,
        "global_residue_contact_ratio": max(0.0, min(1.0, structure.residue_contact_ratio)),
        "global_secondary_structure_agreement": max(0.0, min(1.0, secondary_agreement)),
        "global_energy_favorability": max(0.0, min(1.0, structure.normalized_energy)),
    }


def _pocket_metrics(structure: StructureFeatures, motif_regions: Sequence[Sequence[int]]) -> Dict[str, float]:
    overlap = structure.motif_pocket_overlap
    if motif_regions and overlap == 0.0:
        motif_indices = {idx for region in motif_regions for idx in region}
        overlap = _motif_pocket_overlap(structure, motif_indices)
    return {
        "pocket_score": max(0.0, min(1.0, structure.pocket_score)),
        "pocket_volume_hint": max(0.0, min(1.0, structure.pocket_volume_hint / 250.0)),
        "motif_pocket_overlap": max(0.0, min(1.0, overlap)),
    }


def _active_site_metrics(
    sequence: str,
    structure: StructureFeatures,
    motif_regions: Sequence[Sequence[int]],
    constraint_metadata: Dict[str, object],
) -> Dict[str, float]:
    metal_presence, metal_geometry = _metal_binding_metrics(sequence, structure, motif_regions, constraint_metadata)
    catalytic_presence, catalytic_geometry = _catalytic_site_metrics(sequence, structure, motif_regions, constraint_metadata)
    return {
        "metal_binding_site_presence": metal_presence,
        "metal_binding_geometry": metal_geometry,
        "catalytic_site_presence": catalytic_presence,
        "catalytic_site_geometry": catalytic_geometry,
    }


def _metal_binding_metrics(
    sequence: str,
    structure: StructureFeatures,
    motif_regions: Sequence[Sequence[int]],
    constraint_metadata: Dict[str, object],
) -> Tuple[float, float]:
    constraints = constraint_metadata.get("metal_constraints", [])
    if not isinstance(constraints, list) or not constraints:
        return (0.5, 0.5)
    metal_atoms = [atom for atom in structure.atoms if atom.element in METAL_ELEMENTS or atom.residue_label in METAL_ELEMENTS]
    candidate_pool = _active_site_residue_pool(sequence, structure, motif_regions)
    presence_scores = []
    geometry_scores = []
    for item in constraints:
        if not isinstance(item, dict):
            continue
        coordinating = [str(res)[0].upper() for res in item.get("coordinating_residues", []) if str(res)]
        coordinating = [res for res in coordinating if res.isalpha()]
        if not coordinating:
            continue
        matched_indices = [idx for idx in candidate_pool if idx < len(sequence) and sequence[idx] in coordinating]
        presence_scores.append(min(1.0, len(matched_indices) / max(len(coordinating), 1)))
        donor_atoms = [_best_reactive_atom(structure.atoms, idx, sequence[idx]) for idx in matched_indices]
        donor_atoms = [atom for atom in donor_atoms if atom is not None]
        ion = str(item.get("ion", "ZN")).upper()
        ideal_distance = {"ZN": 2.2, "MG": 2.1, "CA": 2.4, "MN": 2.2, "FE": 2.1, "CU": 2.1}.get(ion, 2.2)
        if metal_atoms and donor_atoms:
            scores = []
            for donor in donor_atoms[: len(coordinating)]:
                nearest = min(_distance(donor.coord, metal.coord) for metal in metal_atoms)
                scores.append(max(0.0, 1.0 - abs(nearest - ideal_distance) / 1.2))
            geometry_scores.append(_mean(*scores) if scores else 0.0)
        else:
            pairwise = []
            for i in range(len(donor_atoms)):
                for j in range(i + 1, len(donor_atoms)):
                    dist = _distance(donor_atoms[i].coord, donor_atoms[j].coord)
                    pairwise.append(max(0.0, 1.0 - abs(dist - 4.5) / 4.0))
            geometry_scores.append(_mean(*pairwise) if pairwise else 0.0)
    return _mean(*presence_scores) if presence_scores else 0.5, _mean(*geometry_scores) if geometry_scores else 0.5


def _catalytic_site_metrics(
    sequence: str,
    structure: StructureFeatures,
    motif_regions: Sequence[Sequence[int]],
    constraint_metadata: Dict[str, object],
) -> Tuple[float, float]:
    constraints = constraint_metadata.get("catalytic_constraints", [])
    if not isinstance(constraints, list) or not constraints:
        return (0.5, 0.5)
    candidate_pool = _active_site_residue_pool(sequence, structure, motif_regions)
    presence_scores = []
    geometry_scores = []
    for item in constraints:
        if not isinstance(item, dict):
            continue
        expected = [str(res)[0].upper() for res in item.get("residues", []) if str(res)]
        expected = [res for res in expected if res.isalpha()]
        if not expected:
            continue
        matched = {}
        for residue_name in expected:
            indices = [idx for idx in candidate_pool if idx < len(sequence) and sequence[idx] == residue_name]
            if indices:
                matched[residue_name] = indices
        presence_scores.append(len(matched) / max(len(set(expected)), 1))
        if len(matched) < len(set(expected)):
            geometry_scores.append(0.0)
            continue
        best_geometry = 0.0
        for combo in _enumerate_residue_combinations(expected, matched)[:50]:
            atoms = [_best_reactive_atom(structure.atoms, idx, sequence[idx]) for idx in combo]
            atoms = [atom for atom in atoms if atom is not None]
            if len(atoms) != len(combo):
                continue
            geometry = _score_catalytic_geometry(combo, atoms, [sequence[idx] for idx in combo])
            if geometry > best_geometry:
                best_geometry = geometry
        geometry_scores.append(best_geometry)
    return _mean(*presence_scores) if presence_scores else 0.5, _mean(*geometry_scores) if geometry_scores else 0.5


def _contact_density(coords: Sequence[Tuple[float, float, float]], cutoff: float) -> float:
    if len(coords) < 2:
        return 0.0
    contacts = 0
    for i in range(len(coords)):
        for j in range(i + 2, len(coords)):
            if _distance(coords[i], coords[j]) <= cutoff:
                contacts += 1
    return contacts / len(coords)


def _residue_contact_ratio(atoms: Sequence[AtomRecord], cutoff: float = 4.5) -> float:
    protein_atoms = [atom for atom in atoms if atom.record_type == "ATOM" and atom.residue_index >= 0]
    if not protein_atoms:
        return 0.0
    contacts = set()
    residue_ids = {atom.residue_index for atom in protein_atoms}
    for i, lhs in enumerate(protein_atoms):
        for rhs in protein_atoms[i + 1 :]:
            if lhs.residue_index == rhs.residue_index or abs(lhs.residue_index - rhs.residue_index) <= 1:
                continue
            if _distance(lhs.coord, rhs.coord) <= cutoff:
                contacts.add(tuple(sorted((lhs.residue_index, rhs.residue_index))))
    return len(contacts) / max(len(residue_ids), 1)


def _interaction_features(path: Path, atoms: Sequence[AtomRecord]) -> Tuple[float, float]:
    hbond_density = _hbond_density(atoms)
    salt_bridge_density = _salt_bridge_density(atoms)
    tool_result = _run_hbond_tool(path)
    if tool_result is None:
        return hbond_density, salt_bridge_density
    tool_hbond, tool_salt = tool_result
    return max(hbond_density, tool_hbond), max(salt_bridge_density, tool_salt)


def _hbond_density(atoms: Sequence[AtomRecord], cutoff: float = 3.5) -> float:
    protein_atoms = [atom for atom in atoms if atom.record_type == "ATOM" and atom.residue_name in DONOR_ACCEPTOR]
    if not protein_atoms:
        return 0.0
    donors = [atom for atom in protein_atoms if atom.element in {"N", "O", "S"}]
    hbonds = 0
    for donor in donors:
        for acceptor in donors:
            if donor.residue_index == acceptor.residue_index:
                continue
            if _distance(donor.coord, acceptor.coord) <= cutoff:
                hbonds += 1
    return hbonds / max(len({atom.residue_index for atom in protein_atoms}), 1)


def _salt_bridge_density(atoms: Sequence[AtomRecord], cutoff: float = 4.0) -> float:
    protein_atoms = [atom for atom in atoms if atom.record_type == "ATOM" and atom.residue_index >= 0]
    acidic = [atom for atom in protein_atoms if atom.residue_name in NEGATIVE and atom.element in {"O", "S"}]
    basic = [atom for atom in protein_atoms if atom.residue_name in POSITIVE and atom.element == "N"]
    bridges = set()
    for lhs in acidic:
        for rhs in basic:
            if lhs.residue_index == rhs.residue_index:
                continue
            if _distance(lhs.coord, rhs.coord) <= cutoff:
                bridges.add(tuple(sorted((lhs.residue_index, rhs.residue_index))))
    return len(bridges) / max(len({atom.residue_index for atom in protein_atoms}), 1)


def _secondary_structure_features(path: Path, residues: Sequence[ResiduePoint]) -> Tuple[float, float, str]:
    parsed = _run_dssp(path)
    if parsed is not None:
        helix_fraction, sheet_fraction = parsed
        return helix_fraction, sheet_fraction, "dssp"
    helix_like_fraction, sheet_like_fraction = _secondary_like_fractions([res.coord for res in residues])
    return helix_like_fraction, sheet_like_fraction, "proxy"


def _pocket_features(path: Path, residues: Sequence[ResiduePoint], atoms: Sequence[AtomRecord]) -> Tuple[float, float, List[int]]:
    parsed = _run_fpocket(path)
    if parsed is not None:
        return parsed
    if not residues:
        return 0.0, 0.0, []
    local_void_scores = []
    for residue in residues:
        ca_neighbors = sum(_distance(residue.coord, other.coord) <= 10.0 for other in residues if other.index != residue.index)
        local_void_scores.append(max(0.0, min(1.0, 1.0 - ca_neighbors / 20.0)))
    pocket_score = max(local_void_scores) if local_void_scores else 0.0
    pocket_volume_hint = pocket_score * len(residues) * 8.0
    candidate_indices = [res.index for res in residues if _local_density(residues, res.index, cutoff=10.0) <= 6]
    return pocket_score, pocket_volume_hint, candidate_indices


def _energy_features(path: Path, residues: Sequence[ResiduePoint], atoms: Sequence[AtomRecord]) -> Tuple[float, float, float, str]:
    external = _run_energy_tool(path)
    if external is not None:
        return external
    pyrosetta = _run_pyrosetta_energy(path, len(residues))
    if pyrosetta is not None:
        return pyrosetta
    return _proxy_energy_features(residues, atoms)


def _run_fpocket(path: Path) -> Tuple[float, float, List[int]] | None:
    executable = os.getenv("MAESD_FPOCKET_BIN", "").strip()
    template = os.getenv("MAESD_FPOCKET_CMD", "").strip()
    temp_dir = Path(tempfile.mkdtemp(prefix="maesd_fpocket_"))
    local_pdb = temp_dir / path.name
    local_pdb.write_text(path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    command = _resolve_tool_command(template, executable, {"pdb_path": str(local_pdb), "output_dir": str(temp_dir)}, ["-f", str(local_pdb)])
    if not command:
        return None
    result = subprocess.run(command, cwd=temp_dir, text=True, capture_output=True)
    if result.returncode != 0:
        return None
    info_files = list(temp_dir.glob("*_out/*_info.txt")) or list(temp_dir.glob("**/*_info.txt"))
    best_score = 0.0
    best_volume = 0.0
    best_indices: List[int] = []
    for info_file in info_files:
        text = info_file.read_text(encoding="utf-8", errors="ignore")
        score = _extract_numeric(text, "Score")
        volume = _extract_numeric(text, "Volume")
        if score > best_score:
            best_score = score
            best_volume = volume
            best_indices = _map_pocket_to_residues(path, info_file)
    if best_score == 0.0 and best_volume == 0.0:
        stdout_metrics = _parse_json_metrics(result.stdout)
        if stdout_metrics:
            return (
                max(0.0, min(1.0, float(stdout_metrics.get("pocket_score", 0.0)))),
                max(0.0, float(stdout_metrics.get("pocket_volume_hint", 0.0))),
                sorted(set(int(idx) for idx in stdout_metrics.get("pocket_residue_indices", []))),
            )
        return None
    normalized_score = max(0.0, min(1.0, best_score / 100.0 if best_score > 1 else best_score))
    return normalized_score, best_volume, best_indices


def _run_dssp(path: Path) -> Tuple[float, float] | None:
    executable = os.getenv("MAESD_DSSP_BIN", "").strip()
    template = os.getenv("MAESD_DSSP_CMD", "").strip()
    temp_dir = Path(tempfile.mkdtemp(prefix="maesd_dssp_"))
    local_pdb = temp_dir / path.name
    local_pdb.write_text(path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    command = _resolve_tool_command(template, executable, {"pdb_path": str(local_pdb), "output_dir": str(temp_dir)}, ["-i", str(local_pdb)])
    if not command:
        return None
    result = subprocess.run(command, cwd=temp_dir, text=True, capture_output=True)
    if result.returncode != 0:
        return None
    parsed = _parse_dssp_output(result.stdout)
    if parsed is not None:
        return parsed
    for dssp_file in list(temp_dir.glob("*.dssp")) + list(temp_dir.glob("**/*.dssp")):
        parsed = _parse_dssp_output(dssp_file.read_text(encoding="utf-8", errors="ignore"))
        if parsed is not None:
            return parsed
    metrics = _parse_json_metrics(result.stdout)
    if metrics:
        return max(0.0, min(1.0, float(metrics.get("helix_fraction", 0.0)))), max(0.0, min(1.0, float(metrics.get("sheet_fraction", 0.0))))
    return None


def _run_hbond_tool(path: Path) -> Tuple[float, float] | None:
    executable = os.getenv("MAESD_HBOND_BIN", "").strip()
    template = os.getenv("MAESD_HBOND_CMD", "").strip()
    temp_dir = Path(tempfile.mkdtemp(prefix="maesd_hbond_"))
    local_pdb = temp_dir / path.name
    local_pdb.write_text(path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    command = _resolve_tool_command(template, executable, {"pdb_path": str(local_pdb), "output_dir": str(temp_dir)}, [str(local_pdb)])
    if not command:
        return None
    result = subprocess.run(command, cwd=temp_dir, text=True, capture_output=True)
    if result.returncode != 0:
        return None
    metrics = _parse_json_metrics(result.stdout)
    if metrics:
        return max(0.0, float(metrics.get("hbond_density", 0.0))), max(0.0, float(metrics.get("salt_bridge_density", 0.0)))
    hbond = _extract_numeric(result.stdout, "hbond_density")
    salt = _extract_numeric(result.stdout, "salt_bridge_density")
    if hbond or salt:
        return hbond, salt
    return None


def _run_energy_tool(path: Path) -> Tuple[float, float, float, str] | None:
    executable = os.getenv("MAESD_ENERGY_BIN", "").strip() or os.getenv("MAESD_ROSETTA_SCORE_BIN", "").strip()
    template = os.getenv("MAESD_ENERGY_CMD", "").strip() or os.getenv("MAESD_ROSETTA_SCORE_CMD", "").strip()
    temp_dir = Path(tempfile.mkdtemp(prefix="maesd_energy_"))
    local_pdb = temp_dir / path.name
    local_pdb.write_text(path.read_text(encoding="utf-8", errors="ignore"), encoding="utf-8")
    command = _resolve_tool_command(template, executable, {"pdb_path": str(local_pdb), "output_dir": str(temp_dir)}, [str(local_pdb)])
    if not command:
        return None
    result = subprocess.run(command, cwd=temp_dir, text=True, capture_output=True)
    if result.returncode != 0:
        return None
    metrics = _parse_json_metrics(result.stdout)
    if metrics:
        raw = float(metrics.get("total_score", metrics.get("raw_energy", 0.0)))
        clash = max(0.0, float(metrics.get("clash_score", metrics.get("fa_rep", 0.0))))
        normalized = _normalize_energy(raw, int(metrics.get("residue_count", 0)) or None, clash)
        if "normalized_energy" in metrics:
            normalized = max(0.0, min(1.0, float(metrics["normalized_energy"])))
        return normalized, raw, clash, str(metrics.get("energy_source", "external-tool"))
    for score_file in list(temp_dir.glob("*.sc")) + list(temp_dir.glob("**/*.sc")):
        parsed = _parse_rosetta_score_file(score_file)
        if parsed is not None:
            raw, clash = parsed
            return _normalize_energy(raw, None, clash), raw, clash, "rosetta-score"
    return None


def _run_pyrosetta_energy(path: Path, residue_count: int) -> Tuple[float, float, float, str] | None:
    if os.getenv("MAESD_USE_PYROSETTA", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return None
    try:
        import pyrosetta  # type: ignore
    except Exception:
        return None
    try:
        pyrosetta.init("-mute all")
        pose = pyrosetta.pose_from_pdb(str(path))
        scorefxn = pyrosetta.get_fa_scorefxn()
        raw = float(scorefxn(pose))
        energies = pose.energies().total_energies()
        clash = float(energies[pyrosetta.rosetta.core.scoring.fa_rep])
        return _normalize_energy(raw, residue_count, clash), raw, clash, "pyrosetta"
    except Exception:
        return None


def _proxy_energy_features(residues: Sequence[ResiduePoint], atoms: Sequence[AtomRecord]) -> Tuple[float, float, float, str]:
    residue_count = max(len(residues), 1)
    hbonds = _hbond_density(atoms)
    salts = _salt_bridge_density(atoms)
    clashes = _clash_score(atoms)
    raw = residue_count * (0.9 - hbonds * 0.6 - salts * 0.4 + clashes * 1.5)
    normalized = max(0.0, min(1.0, 0.62 + hbonds * 0.05 + salts * 0.08 - clashes * 0.7))
    return normalized, raw, clashes, "proxy"


def _resolve_tool_command(template: str, executable: str, substitutions: Dict[str, str], default_args: List[str]) -> List[str]:
    if template:
        return shlex.split(template.format(**substitutions), posix=False)
    if executable:
        return [executable, *default_args]
    return []


def _parse_dssp_output(text: str) -> Tuple[float, float] | None:
    lines = [line.rstrip("\n") for line in text.splitlines() if line.strip()]
    if not lines:
        return None
    structured = [line for line in lines if len(line) > 16 and line[13:15].strip()]
    if not structured:
        return None
    total = 0
    helix = 0
    sheet = 0
    for line in structured:
        total += 1
        code = line[16].strip() if len(line) > 16 else " "
        if code in {"H", "G", "I"}:
            helix += 1
        elif code in {"E", "B"}:
            sheet += 1
    return (helix / total, sheet / total) if total else None


def _parse_json_metrics(text: str) -> Dict[str, object] | None:
    stripped = text.strip()
    if not stripped:
        return None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _parse_rosetta_score_file(path: Path) -> Tuple[float, float] | None:
    lines = [line.strip() for line in path.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
    header = None
    for line in lines:
        if not line.startswith("SCORE:"):
            continue
        parts = line.split()
        if header is None:
            header = parts[1:]
            continue
        if header and len(parts[1:]) == len(header):
            payload = dict(zip(header, parts[1:]))
            return float(payload.get("total_score", payload.get("score", 0.0))), float(payload.get("fa_rep", 0.0))
    return None


def _extract_numeric(text: str, label: str) -> float:
    match = re.search(rf"{re.escape(label)}\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", text, flags=re.IGNORECASE)
    return float(match.group(1)) if match else 0.0


def _map_pocket_to_residues(pdb_path: Path, info_file: Path) -> List[int]:
    pocket_pdb = _infer_matching_pocket_file(info_file)
    if pocket_pdb is None or not pocket_pdb.exists():
        return []
    original_residues, _ = _read_atom_records(pdb_path)
    pocket_residues, _ = _read_atom_records(pocket_pdb)
    if not original_residues or not pocket_residues:
        return []
    indices = []
    for pocket_residue in pocket_residues:
        best_index = min(range(len(original_residues)), key=lambda idx: _distance(pocket_residue.coord, original_residues[idx].coord))
        if _distance(pocket_residue.coord, original_residues[best_index].coord) <= 3.0:
            indices.append(best_index)
    return sorted(set(indices))


def _infer_matching_pocket_file(info_file: Path) -> Path | None:
    pocket_dir = info_file.parent
    pocket_name = info_file.stem.replace("_info", "")
    direct = pocket_dir / f"{pocket_name}_atm.pdb"
    if direct.exists():
        return direct
    matches = list(pocket_dir.glob(f"{pocket_name}*_atm.pdb"))
    return matches[0] if matches else None


def _motif_pocket_overlap(structure: StructureFeatures, motif_indices: set[int]) -> float:
    if not motif_indices or not structure.residues:
        return 0.0
    if structure.pocket_residue_indices:
        return len(motif_indices.intersection(structure.pocket_residue_indices)) / max(len(motif_indices), 1)
    scores = []
    for idx in motif_indices:
        if idx < len(structure.residues):
            density = _local_density(structure.residues, idx, cutoff=10.0)
            scores.append(max(0.0, min(1.0, 1.0 - density / 20.0)))
    return _mean(*scores) if scores else 0.0


def _active_site_residue_pool(sequence: str, structure: StructureFeatures, motif_regions: Sequence[Sequence[int]]) -> List[int]:
    pool = {idx for region in motif_regions for idx in region if idx < len(sequence)}
    pool.update(idx for idx in structure.pocket_residue_indices if idx < len(sequence))
    if not pool:
        pool.update(range(min(len(sequence), len(structure.residues))))
    return sorted(pool)


def _best_reactive_atom(atoms: Sequence[AtomRecord], residue_index: int, residue_name: str) -> AtomRecord | None:
    candidates = [atom for atom in atoms if atom.record_type == "ATOM" and atom.residue_index == residue_index]
    if not candidates:
        return None
    for atom_name in REACTIVE_ATOMS.get(residue_name, ()):
        for atom in candidates:
            if atom.atom_name == atom_name:
                return atom
    for atom in candidates:
        if atom.atom_name not in BACKBONE_ATOMS:
            return atom
    return candidates[0]


def _enumerate_residue_combinations(expected: Sequence[str], matched: Dict[str, List[int]]) -> List[List[int]]:
    combos: List[List[int]] = [[]]
    for residue_name in expected:
        next_combos: List[List[int]] = []
        for combo in combos:
            for index in matched.get(residue_name, []):
                if index not in combo:
                    next_combos.append(combo + [index])
        combos = next_combos
    return combos


def _score_catalytic_geometry(indices: Sequence[int], atoms: Sequence[AtomRecord], residue_names: Sequence[str]) -> float:
    pair_scores = []
    for i in range(len(indices)):
        for j in range(i + 1, len(indices)):
            lhs_name = residue_names[i]
            rhs_name = residue_names[j]
            dist = _distance(atoms[i].coord, atoms[j].coord)
            ideal = 4.0
            tolerance = 2.5
            if {lhs_name, rhs_name} in ({"S", "H"}, {"C", "H"}):
                ideal = 4.2
                tolerance = 2.0
            elif {lhs_name, rhs_name} in ({"H", "D"}, {"H", "E"}, {"H", "N"}):
                ideal = 4.0
                tolerance = 2.0
            elif {lhs_name, rhs_name} in ({"S", "D"}, {"S", "E"}, {"C", "N"}):
                ideal = 7.0
                tolerance = 3.5
            pair_scores.append(max(0.0, 1.0 - abs(dist - ideal) / tolerance))
    locality = max(0.0, 1.0 - ((max(indices) - min(indices)) if indices else 0) / 40.0)
    return _mean(*pair_scores, locality) if pair_scores else 0.0


def _normalize_energy(raw_energy: float, residue_count: int | None, clash_score: float) -> float:
    size = residue_count or 100
    per_residue = raw_energy / max(size, 1)
    logistic = 1.0 / (1.0 + exp((per_residue + 2.0) / 1.5))
    return max(0.0, min(1.0, logistic - clash_score * 0.1))


def _clash_score(atoms: Sequence[AtomRecord], cutoff: float = 1.8) -> float:
    protein_atoms = [atom for atom in atoms if atom.record_type == "ATOM" and atom.residue_index >= 0]
    if not protein_atoms:
        return 0.0
    clashes = 0
    comparisons = 0
    for i, lhs in enumerate(protein_atoms):
        for rhs in protein_atoms[i + 1 :]:
            if lhs.residue_index == rhs.residue_index:
                continue
            comparisons += 1
            if _distance(lhs.coord, rhs.coord) < cutoff:
                clashes += 1
    return clashes / max(comparisons, 1)


def _radius_of_gyration(coords: Sequence[Tuple[float, float, float]]) -> float:
    if not coords:
        return 0.0
    cx = sum(x for x, _, _ in coords) / len(coords)
    cy = sum(y for _, y, _ in coords) / len(coords)
    cz = sum(z for _, _, z in coords) / len(coords)
    return sqrt(sum((x - cx) ** 2 + (y - cy) ** 2 + (z - cz) ** 2 for x, y, z in coords) / len(coords))


def _surface_fraction(coords: Sequence[Tuple[float, float, float]]) -> float:
    if not coords:
        return 0.0
    counts = []
    for i, coord in enumerate(coords):
        neighbors = 0
        for j, other in enumerate(coords):
            if i != j and _distance(coord, other) <= 10.0:
                neighbors += 1
        counts.append(neighbors)
    return sum(count < 10 for count in counts) / len(coords)


def _secondary_like_fractions(coords: Sequence[Tuple[float, float, float]]) -> Tuple[float, float]:
    if len(coords) < 4:
        return 0.0, 0.0
    helix_like = 0
    sheet_like = 0
    total = 0
    for i in range(len(coords) - 3):
        d13 = _distance(coords[i], coords[i + 3])
        total += 1
        if 4.6 <= d13 <= 6.2:
            helix_like += 1
        elif 8.5 <= d13 <= 11.5:
            sheet_like += 1
    return (helix_like / total, sheet_like / total) if total else (0.0, 0.0)


def _neighbor_indices(residues: Sequence[ResiduePoint], index: int, cutoff: float) -> List[int]:
    if index >= len(residues):
        return []
    center = residues[index].coord
    return [residue.index for residue in residues if _distance(center, residue.coord) <= cutoff]


def _local_density(residues: Sequence[ResiduePoint], index: int, cutoff: float) -> float:
    return len(_neighbor_indices(residues, index, cutoff=cutoff))


def _sequence_coverage(observed: str, expected: str) -> float:
    if not expected:
        return 1.0
    return sum(a == b for a, b in zip(observed, expected)) / max(len(expected), 1)


def _distance(lhs: Tuple[float, float, float], rhs: Tuple[float, float, float]) -> float:
    return sqrt((lhs[0] - rhs[0]) ** 2 + (lhs[1] - rhs[1]) ** 2 + (lhs[2] - rhs[2]) ** 2)


def _mean(*values: float) -> float:
    return sum(values) / len(values) if values else 0.0


def _three_to_one(residue: str) -> str:
    mapping = {
        "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C", "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H",
        "ILE": "I", "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P", "SER": "S", "THR": "T", "TRP": "W",
        "TYR": "Y", "VAL": "V",
    }
    return mapping.get(residue.upper(), "X")
