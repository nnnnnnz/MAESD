#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Mermaid diagram generation utilities
"""
import os
import subprocess
from pathlib import Path

from agents.system.const import PROJECT_ROOT
from agents.system.logs import logger
from .common import check_cmd_exists

IS_DOCKER = os.environ.get('AM_I_IN_A_DOCKER_CONTAINER', 'false').lower()


def mermaid_to_file(mermaid_code, output_file_without_suffix, width=2048, height=2048) -> int:
    """Convert Mermaid code to image files (PNG/SVG/PDF)
    
    Args:
        mermaid_code: Mermaid diagram code
        output_file_without_suffix: Output filename without extension
        width: Image width in pixels
        height: Image height in pixels
    
    Returns:
        0 if successful, -1 if failed
    """
    # Write Mermaid code to temporary file
    tmp = Path(f'{output_file_without_suffix}.mmd')
    tmp.write_text(mermaid_code, encoding='utf-8')

    if check_cmd_exists('mmdc') != 0:
        logger.warning("RUN `npm install -g @mermaid-js/mermaid-cli` to install mmdc")
        return -1

    for suffix in ['pdf', 'svg', 'png']:
        output_file = f'{output_file_without_suffix}.{suffix}'
        logger.info(f"Generating {output_file}...")
        if IS_DOCKER == 'true':
            subprocess.run(['mmdc', '-p', '/app/agents/puppeteer-config.json', '-i',
                           str(tmp), '-o', output_file, '-w', str(width), '-H', str(height)])
        else:
            subprocess.run(['mmdc', '-i', str(tmp), '-o',
                           output_file, '-w', str(width), '-H', str(height)])
    return 0


# Example Class Diagram
CLASS_DIAGRAM = """classDiagram
    class Main {
        -SearchEngine search_engine
        +main() str
    }
    class SearchEngine {
        -Index index
        -Ranking ranking
        -Summary summary
        +search(query: str) str
    }
    class Index {
        -KnowledgeBase knowledge_base
        +create_index(data: dict)
        +query_index(query: str) list
    }
    class Ranking {
        +rank_results(results: list) list
    }
    class Summary {
        +summarize_results(results: list) str
    }
    class KnowledgeBase {
        +update(data: dict)
        +fetch_data(query: str) dict
    }
    Main --> SearchEngine
    SearchEngine --> Index
    SearchEngine --> Ranking
    SearchEngine --> Summary
    Index --> KnowledgeBase"""

# Example Sequence Diagram
SEQUENCE_DIAGRAM = """sequenceDiagram
    participant M as Main
    participant SE as SearchEngine
    participant I as Index
    participant R as Ranking
    participant S as Summary
    participant KB as KnowledgeBase
    M->>SE: search(query)
    SE->>I: query_index(query)
    I->>KB: fetch_data(query)
    KB-->>I: return data
    I-->>SE: return results
    SE->>R: rank_results(results)
    R-->>SE: return ranked_results
    SE->>S: summarize_results(ranked_results)
    S-->>SE: return summary
    SE-->>M: return summary"""


if __name__ == '__main__':
    # Example usage
    mermaid_to_file(CLASS_DIAGRAM, PROJECT_ROOT / 'tmp/class_diagram')
    mermaid_to_file(SEQUENCE_DIAGRAM, PROJECT_ROOT / 'tmp/sequence_diagram')
