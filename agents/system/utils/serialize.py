#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Serialization and deserialization utilities for action messages
"""

import copy
import pickle
from typing import Tuple, List, Dict
from collections import defaultdict
from pydantic import create_model

from agents.system.schema import Message
from agents.actions.action import Action, ActionOutput


def schema_to_field_mapping(schema: Dict) -> Dict:
    """Convert JSON schema to Python type mapping for model creation
    
    Args:
        schema: JSON schema dictionary containing field definitions
        
    Returns:
        Dictionary mapping field names to (type, ...) tuples for pydantic model creation
        
    Example Input Schema:
        {
            "title":"prd",
            "type":"object",
            "properties":{
                "Original Requirements":{
                    "title":"Original Requirements",
                    "type":"string"
                },
            },
            "required":[
                "Original Requirements",
            ]
        }
    """
    field_mapping = dict()
    for field, prop in schema['properties'].items():
        if prop['type'] == 'string':
            field_mapping[field] = (str, ...)
        elif prop['type'] == 'array' and prop['items']['type'] == 'string':
            field_mapping[field] = (List[str], ...)
        elif prop['type'] == 'array' and prop['items']['type'] == 'array':
            # Currently only handles List[Tuple[str, str]] case
            field_mapping[field] = (List[Tuple[str, str]], ...)
    return field_mapping


def serialize_message(message: Message) -> bytes:
    """Serialize a Message object to bytes using pickle
    
    Handles special serialization of instruct_content which contains 
    dynamically generated pydantic models.
    
    Args:
        message: Message object to serialize
        
    Returns:
        Pickled bytes of the serialized message
    """
    message_copy = copy.deepcopy(message)  # Prevent reference updates
    
    if message_copy.instruct_content:
        ic = message_copy.instruct_content
        schema = ic.schema()
        mapping = schema_to_field_mapping(schema)

        # Convert dynamic model to serializable dict format
        message_copy.instruct_content = {
            'model_name': schema['title'],
            'field_mapping': mapping,
            'field_values': ic.dict()
        }
    
    return pickle.dumps(message_copy)


def deserialize_message(serialized_msg: bytes) -> Message:
    """Deserialize bytes back into a Message object
    
    Reconstructs any dynamic pydantic models that were serialized.
    
    Args:
        serialized_msg: Pickled bytes of a Message
        
    Returns:
        Reconstructed Message object with original structure
    """
    message = pickle.loads(serialized_msg)
    
    if message.instruct_content:
        ic_data = message.instruct_content
        # Recreate the dynamic model class
        model_class = ActionOutput.create_model_class(
            class_name=ic_data['model_name'],
            mapping=ic_data['field_mapping']
        )
        # Instantiate with original values
        reconstructed_content = model_class(**ic_data['field_values'])
        message.instruct_content = reconstructed_content

    return message
