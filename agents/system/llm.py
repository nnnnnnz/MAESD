from .config import CONFIG
from .provider.anthropic_api import Claude2 as Claude
from .provider.openai_api import OpenAIGPTAPI as LLM
from .utils.deepseek_api import DeepSeekAPI

# Initialize LLM providers
DEFAULT_LLM = LLM()
CLAUDE_LLM = Claude()
DEEPSEEK_LLM = DeepSeekAPI() if CONFIG._get("DEEPSEEK_API_KEY") else None

async def ai_func(prompt, model="default"):
    """
    AI function that routes prompts to different LLM providers
    
    Args:
        prompt: The input prompt/text
        model: Which model to use ('default', 'claude', 'deepseek')
    
    Returns:
        The generated response
    """
    if model == "claude":
        return await CLAUDE_LLM.aask(prompt)
    elif model == "deepseek":
        if DEEPSEEK_LLM is None:
            raise ValueError("DeepSeek is not configured")
        return await DEEPSEEK_LLM.aask(prompt)
    else:  # default
        return await DEFAULT_LLM.aask(prompt)
