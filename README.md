# MAESD:A Unified Multi-Agent Evolutionary Framework for Protein Sequence Design

![figure1](./picture/figure%201.png) 

## Setup
- Install dependencies
    ```
    pip install -r requirements.txt
    ```
- Set up OpenAI API configs in `config.yaml`.

## Datasets
All datasets can be found in the `data/` folder.

**Task1.Semantic-to-Biological Translation Test
We randomly selected 1,000 reviewed protein entries from the UniProt KB database as the test set.

**Task2.Domain-Guided Test
We randomly selected 1,000 entries from the Pfam-A seed dataset as the test set。

**Task3.Structure-Guided Test
We randomly selected 400 protein structures with lengths under 500 amino acids from the PDB database as the test set.
