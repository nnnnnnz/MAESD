#!/usr/bin/env python
# -*- coding: utf-8 -*-

import ast
import inspect
import os
import re
from typing import List, Tuple

from agents.system.logs import logger


def check_cmd_exists(command) -> int:
    """Check if a command exists in the system
    
    :param command: Command to check
    :return: 0 if command exists, non-zero otherwise
    """
    check_command = 'command -v ' + command + ' >/dev/null 2>&1 || { echo >&2 "no mermaid"; exit 1; }'
    result = os.system(check_command)
    return result


class OutputParser:
    """Utility class for parsing structured output text"""

    @classmethod
    def parse_blocks(cls, text: str):
        """Split text into blocks using ## delimiters"""
        blocks = text.split("##")
        block_dict = {}

        for block in blocks:
            if block.strip() != "":
                try:
                    block_title, block_content = block.split("\n", 1)
                    # Fix potential LLM formatting errors
                    if block_title.endswith(":"):
                        block_title = block_title[:-1]
                    block_dict[block_title.strip()] = block_content.strip()
                except ValueError:
                    continue

        return block_dict

    @classmethod
    def parse_code(cls, text: str, lang: str = "") -> str:
        """Extract code block from text"""
        pattern = rf'```{lang}.*?\s+(.*?)```'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1)
        raise ValueError("No code block found")

    @classmethod
    def parse_str(cls, text: str):
        """Parse a simple string value"""
        text = text.split("=")[-1]
        return text.strip().strip("'").strip("\"")

    @classmethod
    def parse_file_list(cls, text: str) -> list[str]:
        """Parse a list of files from text"""
        pattern = r'\s*(.*=.*)?(\[.*\])'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return ast.literal_eval(match.group(2))
        return text.split("\n")

    @classmethod
    def parse_data(cls, data):
        """Parse structured data with automatic format detection"""
        block_dict = cls.parse_blocks(data)
        parsed_data = {}
        for block, content in block_dict.items():
            # Try parsing as code
            try:
                content = cls.parse_code(text=content)
            except Exception:
                pass
            
            # Try parsing as list
            try:
                content = cls.parse_file_list(text=content)
            except Exception:
                pass
            
            parsed_data[block] = content
        return parsed_data

    @classmethod
    def parse_data_with_mapping(cls, data, mapping):
        """Parse data with type annotations"""
        block_dict = cls.parse_blocks(data)
        parsed_data = {}
        for block, content in block_dict.items():
            # Try parsing as code
            try:
                content = cls.parse_code(text=content)
            except Exception:
                pass
                
            typing_define = mapping.get(block, None)
            if isinstance(typing_define, tuple):
                typing = typing_define[0]
            else:
                typing = typing_define
                
            if typing in (List[str], List[Tuple[str, str]]):
                try:
                    content = cls.parse_file_list(text=content)
                except Exception:
                    pass
                    
            parsed_data[block] = content
        return parsed_data


class CodeParser:
    """Specialized parser for code-related text parsing"""

    @classmethod
    def parse_block(cls, block: str, text: str) -> str:
        """Extract specific block from text"""
        blocks = cls.parse_blocks(text)
        for k, v in blocks.items():
            if block in k:
                return v
        return ""

    @classmethod
    def parse_blocks(cls, text: str):
        """Split text into named blocks"""
        blocks = text.split("##")
        block_dict = {}

        for block in blocks:
            if block.strip() != "":
                try:
                    block_title, block_content = block.split("\n", 1)
                    block_dict[block_title.strip()] = block_content.strip()
                except ValueError:
                    continue

        return block_dict

    @classmethod
    def parse_code(cls, block: str, text: str, lang: str = "") -> str:
        """Extract code block from text with optional block filtering"""
        if block:
            text = cls.parse_block(block, text)
        pattern = rf'```{lang}.*?\s+(.*?)```'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1)
        logger.error(f"Pattern {pattern} not found in text")
        raise ValueError("Code block not found")

    @classmethod
    def parse_str(cls, block: str, text: str, lang: str = ""):
        """Parse a simple string value from code block"""
        code = cls.parse_code(block, text, lang)
        code = code.split("=")[-1]
        return code.strip().strip("'").strip("\"")

    @classmethod
    def parse_file_list(cls, block: str, text: str, lang: str = "") -> list[str]:
        """Parse list of files from code block"""
        code = cls.parse_code(block, text, lang)
        pattern = r'\s*(.*=.*)?(\[.*\])'
        match = re.search(pattern, code, re.DOTALL)
        if match:
            return ast.literal_eval(match.group(2))
        raise ValueError("List pattern not found")


class InsufficientFundsException(Exception):
    """Raised when operation cannot be completed due to insufficient funds"""

    def __init__(self, amount, message="Insufficient funds"):
        self.amount = amount
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f'{self.message} -> Amount required: {self.amount}'


def print_members(module, indent=0):
    """
    Recursively print members of a module/class
    
    :param module: Module or class to inspect
    :param indent: Indentation level for output
    """
    prefix = ' ' * indent
    for name, obj in inspect.getmembers(module):
        if inspect.isclass(obj):
            print(f'{prefix}Class: {name}')
            if name not in ['__class__', '__base__']:
                print_members(obj, indent + 2)
        elif inspect.isfunction(obj):
            print(f'{prefix}Function: {name}')
        elif inspect.ismethod(obj):
            print(f'{prefix}Method: {name}')
