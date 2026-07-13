from typing import Dict, Any

DEFAULT_SYSTEM_PROMPT = (
    "You are a highly capable, private, local agentic AI assistant. "
    "Always provide helpful, precise, and secure responses."
)

def format_system_prompt(template: str, context: Dict[str, Any]) -> str:
    """Safely formats a system prompt template using context variables."""
    try:
        return template.format(**context)
    except KeyError as e:
        # Fallback to returning template if variable is missing
        return template
