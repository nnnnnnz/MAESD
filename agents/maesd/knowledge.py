from __future__ import annotations


GO_LIBRARY = {
    "hydrolase": {"go": "GO:0016787", "description": "hydrolase activity"},
    "oxidoreductase": {"go": "GO:0016491", "description": "oxidoreductase activity"},
    "transferase": {"go": "GO:0016740", "description": "transferase activity"},
    "binding": {"go": "GO:0005488", "description": "binding"},
    "transporter": {"go": "GO:0005215", "description": "transporter activity"},
    "membrane": {"go": "GO:0016020", "description": "membrane"},
    "thermostable": {"go": "GO:0009266", "description": "response to temperature stimulus"},
    "salt": {"go": "GO:0009651", "description": "response to salt stress"},
}


EC_LIBRARY = {
    "hydrolase": {"ec": "EC 3.-.-.-", "description": "hydrolase class"},
    "protease": {"ec": "EC 3.4.-.-", "description": "peptidase class"},
    "esterase": {"ec": "EC 3.1.1.-", "description": "carboxylic ester hydrolase"},
    "oxidoreductase": {"ec": "EC 1.-.-.-", "description": "oxidoreductase class"},
    "transferase": {"ec": "EC 2.-.-.-", "description": "transferase class"},
}


DOMAIN_LIBRARY = {
    "kinase": {"name": "protein kinase-like domain", "accession": "IPR011009"},
    "membrane": {"name": "transmembrane helix", "accession": "IPR020635"},
    "transmembrane": {"name": "transmembrane helix", "accession": "IPR020635"},
    "zinc": {"name": "zinc-binding region", "accession": "IPR013087"},
    "beta-lactamase": {"name": "beta-lactamase-like domain", "accession": "IPR001466"},
    "egf": {"name": "EGF-like domain", "accession": "IPR000742"},
    "repeat": {"name": "repeat-containing region", "accession": "IPR013783"},
    "binding": {"name": "ligand-binding region", "accession": "IPR000048"},
}


MOTIF_LIBRARY = {
    "catalytic triad": "SHN",
    "zinc": "HXXH",
    "beta-lactamase": "SXXK",
    "membrane": "LVAIL",
    "binding": "GGH",
}


AMINO_ACIDS = "ACDEFGHIKLMNPQRSTVWY"
HYDROPHOBIC = set("AILMFWVY")
CHARGED = set("DEKRH")
POLAR = set("STNQCGP")


TERM_SYNONYMS = {
    "hydrolase": ["hydrolase", "hydrolysis", "esterase", "protease", "lipase"],
    "binding": ["binding", "bind", "affinity", "recognition"],
    "membrane": ["membrane", "transmembrane", "lipid bilayer"],
    "thermostable": ["thermostable", "thermostability", "heat tolerant", "heat stable"],
    "salt": ["salt", "halotolerant", "halophilic", "osmotic"],
    "oxidoreductase": ["oxidoreductase", "redox enzyme", "oxidase", "dehydrogenase"],
    "transferase": ["transferase", "transfer enzyme"],
    "zinc": ["zinc", "zn2+", "zinc-binding", "zinc binding"],
}


GO_HIERARCHY = {
    "GO:0016787": [{"id": "GO:0003824", "name": "catalytic activity"}],
    "GO:0016491": [{"id": "GO:0003824", "name": "catalytic activity"}],
    "GO:0016740": [{"id": "GO:0003824", "name": "catalytic activity"}],
    "GO:0005488": [{"id": "GO:0003674", "name": "molecular_function"}],
    "GO:0016020": [{"id": "GO:0110165", "name": "cellular anatomical entity"}],
}


EC_HIERARCHY = {
    "EC 3.1.1.-": [{"id": "EC 3.-.-.-", "name": "hydrolases"}],
    "EC 3.4.-.-": [{"id": "EC 3.-.-.-", "name": "hydrolases"}],
    "EC 3.-.-.-": [{"id": "EC 3", "name": "hydrolases"}],
    "EC 1.-.-.-": [{"id": "EC 1", "name": "oxidoreductases"}],
    "EC 2.-.-.-": [{"id": "EC 2", "name": "transferases"}],
}


CROSS_LIBRARY_ALIGNMENTS = {
    "hydrolase": {"go": "GO:0016787", "ec": "EC 3.-.-.-"},
    "esterase": {"go": "GO:0016787", "ec": "EC 3.1.1.-"},
    "protease": {"go": "GO:0016787", "ec": "EC 3.4.-.-"},
    "oxidoreductase": {"go": "GO:0016491", "ec": "EC 1.-.-.-"},
    "transferase": {"go": "GO:0016740", "ec": "EC 2.-.-.-"},
    "binding": {"go": "GO:0005488", "domain": "IPR000048"},
    "membrane": {"go": "GO:0016020", "domain": "IPR020635"},
    "zinc": {"domain": "IPR013087"},
}


DISAMBIGUATION_RULES = {
    "binding": {
        "zinc": {"boost": {"domain:IPR013087": 0.45}, "translation_hint": "prefer metal-binding interpretation"},
        "membrane": {"boost": {"go:GO:0016020": 0.25, "domain:IPR020635": 0.3}, "translation_hint": "prefer localization/context interpretation"},
        "receptor": {"goal": "binding_affinity", "translation_hint": "prefer ligand/receptor affinity interpretation"},
    },
    "hydrolase": {
        "membrane": {"goal": "membrane_localization", "translation_hint": "combine catalysis with membrane context"},
        "zinc": {"motif": "HXXH", "translation_hint": "favor metallohydrolase interpretation"},
    },
}
