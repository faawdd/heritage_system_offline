import json
from dataclasses import dataclass
from typing import Any

import requests

from system.models import SystemConfig


PROVIDER_DEFAULTS = {
    'deepseek': {
        'label': 'DeepSeek',
        'base_url': 'https://api.deepseek.com/v1',
        'model': 'deepseek-chat',
        'requires_api_key': True,
    },
    'bailian': {
        'label': '阿里云百炼（Qwen）',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'model': 'qwen-plus',
        'requires_api_key': True,
    },
    'kimi': {
        'label': 'Kimi（Moonshot）',
        'base_url': 'https://api.moonshot.cn/v1',
        'model': 'moonshot-v1-8k',
        'requires_api_key': True,
    },
    'gemini': {
        'label': 'Google Gemini',
        'base_url': 'https://generativelanguage.googleapis.com/v1beta/openai/',
        'model': 'gemini-2.5-flash',
        'requires_api_key': True,
    },
    'openai': {
        'label': 'ChatGPT（OpenAI）',
        'base_url': 'https://api.openai.com/v1',
        'model': 'gpt-4o-mini',
        'requires_api_key': True,
    },
    'ollama': {
        'label': 'Ollama（本地部署）',
        'base_url': 'http://127.0.0.1:11434',
        'model': 'qwen2.5:7b',
        'requires_api_key': False,
    },
}

LEGACY_KEYS = {
    'api_key': 'deepseek.api_key',
    'base_url': 'deepseek.base_url',
    'model': 'deepseek.model',
    'temperature': 'deepseek.temperature',
    'system_prompt': 'deepseek.system_prompt',
}


def _config_value(key: str, default: str = '') -> str:
    row = SystemConfig.objects.filter(key=key).values_list('value', flat=True).first()
    return str(row if row is not None else default)


@dataclass(frozen=True)
class AIConfig:
    provider: str
    api_key: str
    base_url: str
    model: str
    temperature: float = 0.2
    system_prompt: str = ''
    timeout: int = 120
    max_tokens: int = 1800


def provider_defaults(provider: str) -> dict[str, Any]:
    return PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS['deepseek'])


def get_ai_config() -> AIConfig:
    provider = (_config_value('ai.provider') or 'deepseek').strip().lower()
    if provider == 'chatgpt':
        provider = 'openai'
    provider = provider if provider in PROVIDER_DEFAULTS else 'deepseek'
    defaults = provider_defaults(provider)
    legacy_base = _config_value('deepseek.base_url') if provider == 'deepseek' else ''
    legacy_model = _config_value('deepseek.model') if provider == 'deepseek' else ''
    return AIConfig(
        provider=provider,
        api_key=(
            _config_value(f'ai.{provider}.api_key')
            or (_config_value('ai.api_key') if provider == 'deepseek' else '')
            or (_config_value('deepseek.api_key') if provider == 'deepseek' else '')
            or ''
        ).strip(),
        base_url=(
            _config_value('ai.base_url')
            or legacy_base
            or str(defaults['base_url'])
        ).strip(),
        model=(
            _config_value('ai.model')
            or legacy_model
            or str(defaults['model'])
        ).strip(),
        temperature=_safe_float(_config_value('ai.temperature') or _config_value('deepseek.temperature'), 0.2),
        system_prompt=_config_value('ai.system_prompt') or _config_value('deepseek.system_prompt'),
        timeout=max(10, min(600, int(_safe_float(_config_value('ai.timeout'), 120)))),
        max_tokens=max(128, min(8192, int(_safe_float(_config_value('ai.max_tokens'), 1800)))),
    )


def _safe_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _base_url(config: AIConfig) -> str:
    return config.base_url.rstrip('/')


def _headers(config: AIConfig) -> dict[str, str]:
    headers = {'Accept': 'application/json', 'Content-Type': 'application/json'}
    if config.api_key:
        headers['Authorization'] = f'Bearer {config.api_key}'
    return headers


def list_models(config: AIConfig) -> list[str]:
    base_url = _base_url(config)
    if config.provider == 'ollama':
        response = requests.get(f'{base_url}/api/tags', headers=_headers(config), timeout=min(config.timeout, 20))
        response.raise_for_status()
        data = response.json()
        models = data.get('models') if isinstance(data, dict) else []
        return sorted(
            {
                str(item.get('name') or item.get('model') or '').strip()
                for item in (models or [])
                if isinstance(item, dict) and str(item.get('name') or item.get('model') or '').strip()
            }
        )

    if not config.api_key:
        raise ValueError('该服务需要 API Key 才能检测模型列表')
    response = requests.get(f'{base_url}/models', headers=_headers(config), timeout=min(config.timeout, 30))
    response.raise_for_status()
    data = response.json()
    models = data.get('data') if isinstance(data, dict) else data
    return sorted(
        {
            str(item.get('id') or item.get('name') or '').strip()
            for item in (models or [])
            if isinstance(item, dict) and str(item.get('id') or item.get('name') or '').strip()
        }
    )


def chat_completion(
    messages: list[dict[str, str]],
    *,
    config: AIConfig | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> str:
    config = config or get_ai_config()
    if not config.model:
        raise ValueError('AI 模型未配置')
    if provider_defaults(config.provider).get('requires_api_key') and not config.api_key:
        raise ValueError(f"未配置 {provider_defaults(config.provider).get('label')} API Key")

    base_url = _base_url(config)
    if config.provider == 'ollama':
        payload = {
            'model': config.model,
            'stream': False,
            'messages': messages,
            'format': 'json',
            'options': {
                'temperature': config.temperature if temperature is None else temperature,
                'num_predict': config.max_tokens if max_tokens is None else max_tokens,
            },
        }
        url = f'{base_url}/api/chat'
    else:
        payload = {
            'model': config.model,
            'messages': messages,
            'temperature': config.temperature if temperature is None else temperature,
            'max_tokens': config.max_tokens if max_tokens is None else max_tokens,
        }
        url = f'{base_url}/chat/completions'

    try:
        response = requests.post(url, headers=_headers(config), json=payload, timeout=config.timeout)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as exc:
        detail = ''
        if getattr(exc, 'response', None) is not None:
            try:
                detail = exc.response.json().get('error', exc.response.text)
            except (ValueError, AttributeError):
                detail = exc.response.text[:500]
        raise ValueError(f"AI 服务调用失败：{detail or exc}") from exc

    if config.provider == 'ollama':
        content = (data.get('message') or {}).get('content') if isinstance(data, dict) else ''
    else:
        try:
            content = data['choices'][0]['message']['content']
        except (KeyError, IndexError, TypeError):
            raise ValueError(f'AI 服务返回格式异常：{json.dumps(data, ensure_ascii=False)[:500]}')
    if not str(content or '').strip():
        raise ValueError('AI 服务返回内容为空')
    return str(content)


def parse_json_response(content: str) -> dict[str, Any]:
    text = (content or '').strip()
    if text.startswith('```'):
        lines = text.splitlines()
        if len(lines) >= 3 and lines[-1].strip().startswith('```'):
            text = '\n'.join(lines[1:-1]).strip()
            if text.lower().startswith('json'):
                text = text[4:].lstrip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f'AI 返回内容不是合法 JSON：{exc.msg}') from exc
    if not isinstance(parsed, dict):
        raise ValueError('AI 返回 JSON 必须是对象')
    return parsed
