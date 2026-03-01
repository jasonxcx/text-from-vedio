"""文本摘要 - 支持多种AI提供商"""
import logging
import json
import re
from typing import Optional, Callable, Dict, Any

from config import config

logger = logging.getLogger(__name__)


class SummaryProvider:
    """Base class for summary providers"""
    
    def __init__(self, base_url: str, model: str, api_key: str = ""):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_key = api_key
        
    def generate_summary(self, text: str, max_length: int = 500, 
                        progress_callback: Optional[Callable[[float, str], None]] = None) -> Dict[str, Any]:
        """Generate summary from text"""
        raise NotImplementedError()


class OllamaProvider(SummaryProvider):
    """Ollama local API provider"""
    
    def generate_summary(self, text: str, max_length: int = 500,
                        progress_callback: Optional[Callable[[float, str], None]] = None) -> Dict[str, Any]:
        import ollama
        
        if progress_callback:
            progress_callback(0, "连接Ollama...")
        
        # Truncate text if too long
        if len(text) > 8000:
            text = text[:8000] + "..."
        
        prompt = f"""请对以下文本进行摘要分析，并以JSON格式返回结果。

文本内容：
{text}

请生成：
1. summary: 一段简洁的摘要（不超过{max_length}字）
2. key_points: 3-5个关键要点（列表）
3. topics: 文本涉及的主要主题（列表）

返回格式必须是有效的JSON：
{{"summary": "...", "key_points": ["...", "..."], "topics": ["..."]}}"""

        if progress_callback:
            progress_callback(50, "生成摘要中...")
        
        response = ollama.chat(
            model=self.model,
            messages=[{"role": "user", "content": prompt}]
        )
        
        if progress_callback:
            progress_callback(80, "解析结果...")
        
        content = response.get('message', {}).get('content', '')
        result = _parse_json_response(content)
        
        if progress_callback:
            progress_callback(100, "摘要生成完成")
        
        return result


class OpenAICompatibleProvider(SummaryProvider):
    """OpenAI-compatible API provider (OpenAI, Custom, etc.)"""
    
    def generate_summary(self, text: str, max_length: int = 500,
                        progress_callback: Optional[Callable[[float, str], None]] = None) -> Dict[str, Any]:
        import httpx
        
        if progress_callback:
            progress_callback(0, "连接API...")
        
        # Truncate text if too long
        if len(text) > 8000:
            text = text[:8000] + "..."
        
        prompt = f"""请对以下文本进行摘要分析，并以JSON格式返回结果。

文本内容：
{text}

请生成：
1. summary: 一段简洁的摘要（不超过{max_length}字）
2. key_points: 3-5个关键要点（列表）
3. topics: 文本涉及的主要主题（列表）

返回格式必须是有效的JSON：
{{"summary": "...", "key_points": ["...", "..."], "topics": ["..."]}}"""

        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        data = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一个专业的文本摘要助手，擅长提取关键信息和生成简洁摘要。"},
                {"role": "user", "content": prompt}
            ],
            "temperature": config.get('summary.temperature', 0.7),
            "max_tokens": 2000
        }
        
        if progress_callback:
            progress_callback(50, "生成摘要中...")
        
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=data,
            timeout=120.0
        )
        response.raise_for_status()
        
        if progress_callback:
            progress_callback(80, "解析结果...")
        
        result_data = response.json()
        content = result_data.get('choices', [{}])[0].get('message', {}).get('content', '')
        result = _parse_json_response(content)
        
        if progress_callback:
            progress_callback(100, "摘要生成完成")
        
        return result


def _parse_json_response(content: str) -> Dict[str, Any]:
    """Parse JSON from model response"""
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
    if json_match:
        content = json_match.group(1)
    
    # Try to find JSON object
    try:
        result = json.loads(content)
    except json.JSONDecodeError:
        # Try to extract JSON object from text
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group())
            except json.JSONDecodeError:
                result = {}
        else:
            result = {}
    
    # Ensure required fields
    if 'summary' not in result:
        result['summary'] = content[:500]
    if 'key_points' not in result:
        result['key_points'] = []
    if 'topics' not in result:
        result['topics'] = []
    
    return result


def get_summary_provider() -> Optional[SummaryProvider]:
    """Get configured summary provider"""
    if not config.get('summary.enabled', True):
        logger.info("Summary generation is disabled")
        return None
    
    provider_name = config.get('summary.provider', 'ollama')
    
    if provider_name == 'ollama':
        base_url = config.get('summary.ollama.base_url', 'http://localhost:11434')
        model = config.get('summary.ollama.model', 'qwen2.5')
        return OllamaProvider(base_url, model)
    
    elif provider_name == 'openai':
        base_url = config.get('summary.openai.base_url', 'https://api.openai.com/v1')
        model = config.get('summary.openai.model', 'gpt-3.5-turbo')
        api_key = config.get('summary.openai.api_key', '')
        if not api_key:
            logger.warning("OpenAI API key not set")
        return OpenAICompatibleProvider(base_url, model, api_key)
    
    elif provider_name == 'custom':
        base_url = config.get('summary.custom.base_url', '')
        model = config.get('summary.custom.model', '')
        api_key = config.get('summary.custom.api_key', '')
        if not base_url or not model:
            logger.error("Custom provider base_url or model not set")
            return None
        return OpenAICompatibleProvider(base_url, model, api_key)
    
    else:
        logger.error(f"Unknown provider: {provider_name}")
        return None


def summarize_text(
    text: str,
    max_length: int = None,
    progress_callback: Optional[Callable[[float, str], None]] = None
) -> Optional[Dict[str, Any]]:
    """
    Generate summary using configured provider
    
    Args:
        text: Text to summarize
        max_length: Maximum summary length (chars)
        progress_callback: Progress callback function
        
    Returns:
        Dict with summary, key_points, topics or None on failure
    """
    if not text or len(text.strip()) < 10:
        logger.warning("Text too short to summarize")
        return {"summary": "文本太短，无法生成摘要", "key_points": [], "topics": []}
    
    provider = get_summary_provider()
    if provider is None:
        logger.info("No summary provider available, skipping summary")
        return None
    
    if max_length is None:
        max_length = config.get('summary.max_length', 500)
    
    try:
        logger.info(f"Generating summary with {config.get('summary.provider')} provider")
        result = provider.generate_summary(text, max_length, progress_callback)
        logger.info(f"Summary generated: {len(result.get('summary', ''))} chars, {len(result.get('key_points', []))} key points")
        return result
    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        raise
