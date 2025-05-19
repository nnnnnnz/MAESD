import json
import subprocess
import logging
import tempfile
from pathlib import Path
from typing import List, Dict, Optional
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_proteinmpnn(
    pdb_path: str,
    num_seqs: int = 10,
    temperature: float = 0.1,
    output_dir: Optional[str] = None,
    use_gpu: bool = True,
    verbose: bool = False
) -> List[Dict]:
    """
    Run ProteinMPNN to generate designed protein sequences from an input PDB structure.
    
    Args:
        pdb_path: Path to input PDB file
        num_seqs: Number of sequences to generate (default: 10)
        temperature: Sampling temperature (default: 0.1)
        output_dir: Directory to save results (default: temporary directory)
        use_gpu: Whether to use GPU acceleration (default: True)
        verbose: Show detailed output (default: False)
    
    Returns:
        List of dictionaries containing designed sequences and metadata
        
    Example:
        results = run_proteinmpnn("input.pdb", num_seqs=5)
        print(json.dumps(results, indent=2))
    """
    try:
        # Validate input PDB file
        pdb_file = Path(pdb_path)
        if not pdb_file.exists():
            raise FileNotFoundError(f"PDB file not found: {pdb_path}")
        
        if not pdb_file.suffix == '.pdb':
            raise ValueError("Input file must have .pdb extension")
        
        # Setup output directory
        if output_dir is None:
            output_dir = tempfile.mkdtemp(prefix="proteinmpnn_")
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True, parents=True)
        
        # Prepare ProteinMPNN command
        cmd = [
            "python", 
            "/path/to/protein_mpnn_run.py",  # Update with actual path
            "--pdb_path", str(pdb_file.resolve()),
            "--out_folder", str(output_path.resolve()),
            "--num_seq_per_target", str(num_seqs),
            "--sampling_temp", str(temperature),
            "--batch_size", "1"  # Reduce for large proteins
        ]
        
        if use_gpu:
            cmd.extend(["--device", "cuda:0"])
        else:
            cmd.extend(["--device", "cpu"])
        
        if verbose:
            cmd.append("--verbose")
        
        logger.info(f"Running ProteinMPNN for {pdb_file.name}")
        logger.debug(f"Command: {' '.join(cmd)}")
        
        # Execute ProteinMPNN
        env = os.environ.copy()
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            env=env
        )
        
        if verbose:
            logger.debug(f"ProteinMPNN stdout: {result.stdout}")
            if result.stderr:
                logger.debug(f"ProteinMPNN stderr: {result.stderr}")
        
        # Parse output files
        seq_file = output_path / "seqs" / f"{pdb_file.stem}.fa"
        if not seq_file.exists():
            raise FileNotFoundError(f"Output sequence file not found: {seq_file}")
        
        # Parse FASTA format into JSON list
        sequences = []
        current_seq = {}
        with open(seq_file, 'r') as f:
            for line in f:
                if line.startswith('>'):
                    if current_seq:
                        sequences.append(current_seq)
                    current_seq = {
                        "id": line[1:].strip(),
                        "sequence": "",
                        "score": None,
                        "temperature": temperature
                    }
                else:
                    current_seq["sequence"] += line.strip()
        
        if current_seq:  # Add the last sequence
            sequences.append(current_seq)
        
        # Try to parse scores if available
        score_file = output_path / "scores" / f"{pdb_file.stem}.json"
        if score_file.exists():
            with open(score_file, 'r') as f:
                scores = json.load(f)
            for seq, score_data in zip(sequences, scores):
                seq.update({
                    "score": score_data.get("score"),
                    "global_score": score_data.get("global_score")
                })
        
        logger.info(f"Successfully generated {len(sequences)} sequences")
        return sequences
        
    except subprocess.CalledProcessError as e:
        logger.error(f"ProteinMPNN failed with exit code {e.returncode}: {e.stderr}")
        return []
    except Exception as e:
        logger.error(f"Error running ProteinMPNN: {str(e)}")
        return []
