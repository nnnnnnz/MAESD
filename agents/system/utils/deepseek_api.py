
import os
from typing import Optional, AsyncGenerator
import aiohttp
from ..config import CONFIG

class DeepSeekAPI:
    """
    DeepSeek API provider implementation
    """
    
    def __init__(self):
        self.api_key = CONFIG.get("DEEPSEEK_API_KEY")
        self.api_base = CONFIG.get("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1")
        self.model = CONFIG.get("DEEPSEEK_MODEL", "deepseek-chat")
        
    async def aask(self, 
                  prompt: str, 
                  temperature: float = 0.7,
                  max_tokens: int = 2048) -> str:
        """
        Async method to send prompt to DeepSeek API
        
        Args:
            prompt: Input text/prompt
            temperature: Creativity parameter
            max_tokens: Maximum tokens to generate
            
        Returns:
            Generated response text
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{self.api_base}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                if response.status != 200:
                    error = await response.text()
                    raise Exception(f"DeepSeek API error: {error}")
                
                data = await response.json()
                return data['choices'][0]['message']['content']
