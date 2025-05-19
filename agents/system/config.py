#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import openai
import yaml

from .const import PROJECT_ROOT
from .logs import logger
from .utils.singleton import Singleton
from .tools import SearchEngineType, WebBrowserEngineType


class NotConfiguredException(Exception):
    """Exception raised for errors in configuration.

    Attributes:
        message -- explanation of the error
    """

    def __init__(self, message="Required configuration is not set"):
        self.message = message
        super().__init__(self.message)

class Config(metaclass=Singleton):
    """
    Common usage:
    config = Config("config.yaml")
    secret_key = config.get_key("SECRET_KEY")
    print("Secret key:", secret_key)
    """

    _instance = None
    key_yaml_file = PROJECT_ROOT / "config/key.yaml"
    default_yaml_file = PROJECT_ROOT / "config/config.yaml"

    def __init__(self, yaml_file=default_yaml_file):
        self._configs = {}
        self._init_with_config_files_and_env(self._configs, yaml_file)
        logger.info("Configuration loading completed.")
        self.global_proxy = self._get("GLOBAL_PROXY")
        self.llm_api_key = self._get("LLM_API_KEY")
        
        self.llm_api_base = self._get("LLM_API_BASE")
        self.llm_proxy = self._get("LLM_PROXY")
        
        self.llm_api_type = self._get("LLM_API_TYPE")
        self.llm_api_version = self._get("LLM_API_VERSION")
        self.llm_api_rpm = self._get("RPM", 3)
        self.llm_api_model = self._get("LLM_API_MODEL", "gpt-4")
        self.max_tokens_rsp = self._get("MAX_TOKENS", 2048)
        self.deployment_id = self._get("DEPLOYMENT_ID")

        self.alternate_api_key = self._get('ALTERNATE_API_KEY')
        self.search_api_key_1 = self._get("SEARCH_API_KEY_1")
        self.search_api_key_2 = self._get("SEARCH_API_KEY_2")
        self.search_service_key = self._get("SEARCH_SERVICE_KEY")
        self.search_service_id = self._get("SEARCH_SERVICE_ID")
        self.search_engine = self._get("SEARCH_ENGINE", SearchEngineType.SEARCH_ENGINE_1)
 
        self.web_browser_engine = WebBrowserEngineType(self._get("WEB_BROWSER_ENGINE", "playwright"))
        self.browser_type_1 = self._get("BROWSER_TYPE_1", "chromium")
        self.browser_type_2 = self._get("BROWSER_TYPE_2", "chrome")
      
        self.long_term_memory = self._get('LONG_TERM_MEMORY', False)
        if self.long_term_memory:
            logger.warning("LONG_TERM_MEMORY is enabled")
        self.max_budget = self._get("MAX_BUDGET", 10.0)
        self.total_cost = 0.0

    def _init_with_config_files_and_env(self, configs: dict, yaml_file):
        """Load configurations from config/key.yaml, config/config.yaml, and environment variables in descending priority"""
        configs.update(os.environ)

        for _yaml_file in [yaml_file, self.key_yaml_file]:
            if not _yaml_file.exists():
                continue

            # Load local YAML file
            with open(_yaml_file, "r", encoding="utf-8") as file:
                yaml_data = yaml.safe_load(file)
                if not yaml_data:
                    continue
                os.environ.update({k: v for k, v in yaml_data.items() if isinstance(v, str)})
                configs.update(yaml_data)

    def _get(self, *args, **kwargs):
        return self._configs.get(*args, **kwargs)

    def get(self, key, *args, **kwargs):
        """Get value from config/key.yaml, config/config.yaml or environment variables, raise error if not found"""
        value = self._get(key, *args, **kwargs)
        if value is None:
            raise ValueError(f"Key '{key}' not found in environment variables or YAML configuration")
        return value


CONFIG = Config()
