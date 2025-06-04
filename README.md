# MAESD:A Unified Multi-Agent Evolutionary Framework for Protein Sequence Design

![figure1](./picture/figure%201.png) 

## Setup
- Install dependencies
    ```
    conda create -n maesd python=3.9
    conda activate maesd
    pip install -r requirements.txt
    ```
  Protein design model deployment
  ProteinMPNN
    ```
    git clone https://github.com/dauparas/ProteinMPNN
    ```
  Progen2
  ```
  git clone https://github.com/salesforce/progen
  cd progen/progen2
  ```
  AlphaFold2
  ```
  docker pull alphafolddev/alphafold:latest
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

### Installation

```bash
cd MAESD
python setup.py install
```
-----------------------------------------------------------------------------------------------------
Output example:
```
>job_name, score=1.1515, global_score=1.1643, fixed_chains=['B'], designed_chains=['A', 'C'], model_name=v_48_020, loop=5 seed=41
MFEVDLSKLPCGMEGSVYFTAEYADGGKSLYPLDTAGAAYGTGYCDSYCTRHLRWIGGVLNVDGWVPSSNNPNDGVGGYGSCCARVDLLEGNNISIRFAPHPCTVVGRHRCSGDACGGYYSSNPNGGPCDYNGCYYNPIQMGNTNFYGPGPSFTIDSSKPFTIIVSFNDDGSIDISFIQDGVTYSWPEVTIGSYSGNTIDQAYCDALEATFGGSCFSNKGGLAQFKKAIAG
>T=0.1, sample=1, score=0.7232, global_score=0.9312, seq_recovery=0.5674
MFSDTTYKQFTLLGNEVQFKVDLSNLPCGVVGAFFFVSMPADGGRSLYPTNTAGARYGAGYCNSYCTRNLRFIGGLTNVTGWTPSSNNPTWGVGGRGSCCSQADLLEGNNLSYVTNPHPCTTTGTTECTGDACGGYYSSNENGGPCDPWGCAYNPYAEGNTNFFGPGSSYTIDSNKPFTVVVSFNPDGSITISFVQDGVTYAAPTVTIGDYTGNVIDAAYCAAKAKVWGGS
>T=0.1, sample=2, score=0.7435, global_score=0.9313, seq_recovery=0.6225
MFEVDTYLQFKLLGNEVQFTVDVSKLPCGIEGAVYFTTMPADGGRSRYPLNTAGARYGMGYCNAHCDRWLRFIAGRSNVTGWVPDPNDPTNGIGGRGMCCAELDLFEGNNISWELNPHPCTTVGATECTGDACGGPYASNYNGGPCDPNGCGFNPWQEGNTTFYGPGSSYTIDSTKPFTVIVSVNPSGDIEMSFVQDGKTYAAPNVTIGDYSGNVLNAAYCAAREAVYGGS
```
* `score` - average over residues that were designed negative log probability of sampled amino acids
* `global score` - average over all residues in all chains negative log probability of sampled/fixed amino acids
* `fixed_chains` - chains that were not designed (fixed)
* `designed_chains` - chains that were redesigned
* `model_name/CA_model_name` - model name that was used to generate results, e.g. `v_48_020`
* `loop` - The number of training sessions for the evolutionary loop
* `seed` - random seed
* `T=0.1` - temperature equal to 0.1 was used to sample sequences
* `sample` - sequence sample number 1, 2, 3...etc
----------------------------------------------------
## Acknowledgements
The [system](https://github.com/nnnnnnz/MAESD/tree/master/agents/system), [action_bank](https://github.com/nnnnnnz/MAESD/tree/master/agents/actions/action_bank) and [role_bank](https://github.com/nnnnnnz/MAESD/tree/master/agents/roles/role_bank) of this code base is built using [MetaGPT](https://github.com/geekan/MetaGPT)

## Results

```bash
$ python main.py --input "Protein design text description" --output result.txt
```
