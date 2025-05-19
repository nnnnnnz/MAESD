import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_alphafold(
    sequence: str,
    output_dir: str = "af2_results",
    model_preset: str = "monomer",  # Options: monomer, monomer_casp14, monomer_ptm, multimer
    use_gpu: bool = True,
    max_template_date: str = "2020-05-14",
    db_preset: str = "full_dbs"  # Options: full_dbs, reduced_dbs
) -> Tuple[Optional[str], Optional[str]]:
    """
    Run AlphaFold2 prediction for a given protein sequence.
    
    Args:
        sequence: Protein sequence to predict (single-letter amino acid codes)
        output_dir: Directory to save results
        model_preset: AlphaFold model configuration
        use_gpu: Whether to use GPU acceleration
        max_template_date: Maximum template release date (YYYY-MM-DD)
        db_preset: Database preset configuration
        
    Returns:
        tuple: (path_to_pdb_file, path_to_pickle_file) or (None, None) if failed
    
    Example:
        pdb_path, _ = run_alphafold("MAAHKGAEHHHKAAEHHEQAAKHHHAAAEHAAK")
    """
    try:
        # Validate input
        if not isinstance(sequence, str) or len(sequence) < 10:
            raise ValueError("Sequence must be at least 10 amino acids long")
        
        sequence = sequence.upper()  # Ensure uppercase
        valid_aas = set("ACDEFGHIKLMNPQRSTVWY")
        if not all(aa in valid_aas for aa in sequence):
            raise ValueError("Sequence contains invalid amino acid characters")
            
        # Prepare output directory
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)
        
        # Build command (assuming AlphaFold is installed via Docker)
        cmd = [
            "docker", "run",
            "--gpus", "all" if use_gpu else "none",
            "-v", f"{output_path}:/data",
            "-v", "<path_to_alphafold_dbs>:/alphafold/data",
            "ghcr.io/deepmind/alphafold",
            "--fasta_paths=/data/target.fasta",
            "--output_dir=/data",
            f"--model_preset={model_preset}",
            f"--max_template_date={max_template_date}",
            f"--db_preset={db_preset}",
            "--data_dir=/alphafold/data"
        ]
        
        # Save sequence to temporary FASTA file
        fasta_path = output_path / "target.fasta"
        with open(fasta_path, "w") as f:
            f.write(f">target\n{sequence}")
        
        logger.info(f"Running AlphaFold2 for sequence of length {len(sequence)}")
        logger.debug(f"Command: {' '.join(cmd)}")
        
        # Execute AlphaFold
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True
        )
        
        # Check for successful completion
        if result.returncode != 0:
            raise RuntimeError(f"AlphaFold failed: {result.stderr}")
        
        # Find the best PDB result
        pdb_files = list(output_path.glob("target_unrelaxed_rank_1_*.pdb"))
        if not pdb_files:
            raise FileNotFoundError("No PDB file generated")
        
        pdb_path = str(pdb_files[0])
        pickle_path = str(output_path / "result_model_1_pred_0.pkl")
        
        logger.info(f"Prediction completed. PDB file: {pdb_path}")
        
        return pdb_path, pickle_path
        
    except subprocess.CalledProcessError as e:
        logger.error(f"AlphaFold execution failed: {e.stderr}")
        return None, None
    except Exception as e:
        logger.error(f"Error running AlphaFold: {str(e)}")
        return None, None
