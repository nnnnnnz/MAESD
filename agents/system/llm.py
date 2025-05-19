from .provider.anthropic_api import Claude2 as Claude
from .provider.openai_api import OpenAIGPTAPI as LLM
from .provider.deepseek_api import DeepSeekAPI  # Add this import

# Initialize LLM providers
DEFAULT_LLM = LLM()
CLAUDE_LLM = Claude()
DEEPSEEK_LLM = DeepSeekAPI()  # Add DeepSeek instance

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
        return await DEEPSEEK_LLM.aask(prompt)
    else:  # default
        return await DEFAULT_LLM.aask(prompt)
