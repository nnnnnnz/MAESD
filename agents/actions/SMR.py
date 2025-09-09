import MDAnalysis as mda
import numpy as np
from MDAnalysis.analysis import distances
from MDAnalysis.analysis.hydrogenbonds import HydrogenBondAnalysis
from numba import jit
from Bio.Align import PairwiseAligner
from Bio.Seq import Seq

class ProtScreenAgent:
    def __init__(self):
        self.name = "prot_screen agent"
        self.actions = {
            "SGHFS": self.calculate_structural_interactions
        }
        
    def SGHFS(self, design_pdb: str, natural_pdb: str, design_resid: int, radius: float = 8.0) -> dict:
        """
        Calculate Structural and Geometric Hydration Features Score (SGHFS)
        
        Parameters:
        -----------
        design_pdb : str
            Path to the designed protein PDB file
        natural_pdb : str
            Path to the natural template PDB file
        design_resid : int
            Residue ID in the designed protein to analyze
        radius : float, optional
            Radius of the microenvironment to analyze (default: 8.0 Å)
            
        Returns:
        --------
        dict
            Dictionary containing SMR score and interaction counts
        """
        return self.calculate_structural_interactions(design_pdb, natural_pdb, design_resid, radius)
        
    def calculate_structural_interactions(self, design_pdb, natural_pdb, design_resid, radius=8.0):
        """Main function to calculate structural interactions (renamed from calculate_SMR)"""
        # 1. Sequence alignment
        alignment_map = self.align_sequences(design_pdb, natural_pdb)
        if design_resid not in alignment_map:
            raise ValueError(f"Designed protein residue {design_resid} cannot be mapped to natural template")
        natural_resid = alignment_map[design_resid]

        # 2. Load structures
        design = mda.Universe(design_pdb)
        natural = mda.Universe(natural_pdb)

        # 3. Get CA positions
        center_design = self.get_ca_position(design, design_resid)
        center_natural = self.get_ca_position(natural, natural_resid)

        # 4. Select microenvironment
        micro_env_design = self.select_micro_env(design, center_design, radius)
        micro_env_natural = self.select_micro_env(natural, center_natural, radius)

        # 5. Calculate interactions
        n_hbonds_design = self.count_hbonds(design, f"point {center_design[0]} {center_design[1]} {center_design[2]} {radius}")
        n_hbonds_natural = self.count_hbonds(natural, f"point {center_natural[0]} {center_natural[1]} {center_natural[2]} {radius}")

        hydrophobic_design = micro_env_design.select_atoms("(name C* CD* CE* CG*) and not (name CA CB)")
        hydrophobic_natural = micro_env_natural.select_atoms("(name C* CD* CE* CG*) and not (name CA CB)")
        n_hydrophobic_design = self.count_hydrophobic(hydrophobic_design.positions)
        n_hydrophobic_natural = self.count_hydrophobic(hydrophobic_natural.positions)

        positive_design = micro_env_design.select_atoms("(resname ARG LYS) and (name NH* NZ)")
        negative_design = micro_env_design.select_atoms("(resname ASP GLU) and (name OE* OD*)")
        positive_natural = micro_env_natural.select_atoms("(resname ARG LYS) and (name NH* NZ)")
        negative_natural = micro_env_natural.select_atoms("(resname ASP GLU) and (name OE* OD*)")
        n_salt_bridges_design = self.count_salt_bridges(positive_design, negative_design)
        n_salt_bridges_natural = self.count_salt_bridges(positive_natural, negative_natural)

        # 6. Calculate SMR score
        total_design = n_hbonds_design + n_hydrophobic_design + n_salt_bridges_design
        total_natural = n_hbonds_natural + n_hydrophobic_natural + n_salt_bridges_natural
        SMR = min(total_design / total_natural, 1.0) if total_natural > 0 else 0.0

        return {
            "status": "success",
            "design_resid": design_resid,
            "natural_resid": natural_resid,
            "design": {
                "hbonds": n_hbonds_design,
                "hydrophobic": n_hydrophobic_design,
                "salt_bridges": n_salt_bridges_design,
                "total": total_design
            },
            "natural": {
                "hbonds": n_hbonds_natural,
                "hydrophobic": n_hydrophobic_natural,
                "salt_bridges": n_salt_bridges_natural,
                "total": total_natural
            },
            "SMR": SMR,
            "metadata": {
                "radius_used": radius,
                "units": {
                    "distances": "Å",
                    "angles": "degrees"
                }
            }
        }

    # Helper methods (converted from standalone functions to class methods)
    def align_sequences(self, design_pdb, natural_pdb):
        def get_sequence_and_numbers(pdb_file):
            u = mda.Universe(pdb_file)
            seq = ""
            res_numbers = []
            for res in u.residues:
                seq += res.resname[:1]
                res_numbers.append(res.resid)
            return seq, res_numbers

        design_seq, design_nums = get_sequence_and_numbers(design_pdb)
        natural_seq, natural_nums = get_sequence_and_numbers(natural_pdb)

        aligner = PairwiseAligner()
        aligner.mode = 'global'
        aligner.open_gap_score = -10
        aligner.extend_gap_score = -0.5
        alignments = aligner.align(Seq(design_seq), Seq(natural_seq))
        best_alignment = alignments[0]

        alignment_map = {}
        design_idx = 0
        natural_idx = 0

        for d, n in zip(best_alignment[0], best_alignment[1]):
            if d != '-' and n != '-':
                alignment_map[design_nums[design_idx]] = natural_nums[natural_idx]
            if d != '-':
                design_idx += 1
            if n != '-':
                natural_idx += 1

        return alignment_map

    def count_hbonds(self, universe, selection):
        try:
            hbonds = HydrogenBondAnalysis(
                universe=universe,
                donors_sel=f"({selection}) and (name NE2 ND1 NH1 NH2 NZ or (backbone and name N))",
                hydrogens_sel=f"({selection}) and (name H* or name [1-9]H*)",
                acceptors_sel=f"({selection}) and (name O OE1 OE2 OD1 OD2 or (backbone and name O))",
                d_a_cutoff=3.5,
                d_h_a_angle_cutoff=120.0,
                update_selections=False
            )
            hbonds.run()
            return len(hbonds.results.hbonds) if hasattr(hbonds.results, 'hbonds') else 0
        except Exception as e:
            print(f"Hydrogen bond analysis error: {str(e)}")
            return 0

    @staticmethod
    @jit(nopython=True)
    def count_hydrophobic(positions):
        n = len(positions)
        count = 0
        for i in range(n):
            for j in range(i + 1, n):
                dist = np.sqrt(np.sum((positions[i] - positions[j]) ** 2))
                if dist <= 4.0:
                    count += 1
        return count

    @staticmethod
    def count_salt_bridges(pos_atoms, neg_atoms):
        pos_sel = pos_atoms.select_atoms("(resname ARG and name NH*) or (resname LYS and name NZ) and not resname HOH")
        neg_sel = neg_atoms.select_atoms("(resname ASP and name OD*) or (resname GLU and name OE*) and not resname HOH")
        
        if len(pos_sel) == 0 or len(neg_sel) == 0:
            return 0
        
        dist_matrix = distances.distance_array(pos_sel.positions, neg_sel.positions)
        return np.sum((dist_matrix <= 4.0) & (dist_matrix >= 2.5))

    @staticmethod
    def get_ca_position(universe, resid):
        ca = universe.select_atoms(f"resid {resid} and name CA")
        if len(ca) == 0:
            raise ValueError(f"Residue {resid} has no CA atom")
        return ca.positions[0]

    @staticmethod
    def select_micro_env(universe, center, radius):
        return universe.select_atoms(f"point {center[0]} {center[1]} {center[2]} {radius}")


# Example usage:
if __name__ == "__main__":
    agent = ProtScreenAgent()
    
    # Example call to the SGHFS action
    result = agent.SGHFS(
        design_pdb="6y7f_design_H.pdb",
        natural_pdb="6y7f_H.pdb",
        design_resid=111,
        radius=8.0
    )
    
    print("\nResults:")
    print(f"Design residue {result['design_resid']} maps to natural residue {result['natural_resid']}")
    print(f"SMR score: {result['SMR']:.2f}")
    print("\nDesign protein interactions:")
    print(f"  Hydrogen bonds: {result['design']['hbonds']}")
    print(f"  Hydrophobic interactions: {result['design']['hydrophobic']}")
    print(f"  Salt bridges: {result['design']['salt_bridges']}")
    print(f"  Total: {result['design']['total']}")
    print("\nNatural template interactions:")
    print(f"  Hydrogen bonds: {result['natural']['hbonds']}")
    print(f"  Hydrophobic interactions: {result['natural']['hydrophobic']}")
    print(f"  Salt bridges: {result['natural']['salt_bridges']}")
    print(f"  Total: {result['natural']['total']}")
