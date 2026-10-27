"""Who makes a model, read from its identifier.

A gateway's `/models` reports `owned_by` as the API dialect it speaks ("openai" for
everything behind an OpenAI-compatible proxy), not the maker, so the maker has to come
from the id itself.
"""

OTHER_VENDOR = "Other"

# `maker/model` ids, as Vertex's Model Garden and Hugging Face name them.
VENDOR_PREFIXES = {
    "openai": "OpenAI",
    "qwen": "Qwen",
    "zai-org": "Z.ai",
    "moonshotai": "Moonshot",
    "meta": "Meta",
    "minimaxai": "MiniMax",
    "deepseek-ai": "DeepSeek",
    "mistralai": "Mistral",
    "google": "Google",
    "anthropic": "Anthropic",
}

# Bare ids, matched on how they start.
VENDOR_NAMES = (
    ("claude", "Anthropic"),
    ("gemini", "Google"),
    ("gemma", "Google"),
    ("veo", "Google"),
    ("imagen", "Google"),
    ("mistral", "Mistral"),
    ("codestral", "Mistral"),
    ("gpt", "OpenAI"),
    ("o1", "OpenAI"),
    ("o3", "OpenAI"),
    ("o4", "OpenAI"),
    ("text-embedding", "OpenAI"),
    ("llama", "Meta"),
    ("deepseek", "DeepSeek"),
    ("qwen", "Qwen"),
    ("glm", "Z.ai"),
    ("kimi", "Moonshot"),
    ("minimax", "MiniMax"),
)


def vendor(model_id: str) -> str:
    """The maker: the `maker/` prefix when the id has one, else its name; "Other" when unknown."""
    head, _, rest = model_id.partition("/")
    if rest:
        return VENDOR_PREFIXES.get(head.lower(), head)
    lowered = model_id.lower()
    return next((name for start, name in VENDOR_NAMES if lowered.startswith(start)), OTHER_VENDOR)
