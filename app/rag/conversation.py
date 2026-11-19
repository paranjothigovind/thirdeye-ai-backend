"""Conversation normalization and generation-message assembly for the RAG layer.

Provider-neutral: produces ``{"role", "content"}`` dicts consumed by any
``LLMProvider``.
"""
import html
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.core.config import settings
from app.rag.prompts import GROUNDING_RULES

ChatMessage = Dict[str, str]


def _field(message: Any, name: str) -> str:
    value = message.get(name) if isinstance(message, dict) else getattr(message, name, None)
    return value if isinstance(value, str) else ""


def split_conversation(
    messages: Iterable[Any],
    max_history: Optional[int] = None,
) -> Tuple[Optional[str], List[ChatMessage]]:
    """Split a client conversation into ``(query, history)``.

    - ``query`` is the content of the last user message (``None`` if there is none).
    - ``history`` holds the user/assistant turns before it, oldest first. Client
      ``system`` messages and unknown roles are dropped, so a client cannot replace
      the application's system prompt. Empty messages are dropped, the history is
      trimmed to the most recent ``max_history`` turns, and it always starts with
      a user turn.
    - Anything after the last user message is ignored.

    History comes only from the request itself; nothing is stored or shared
    between requests.
    """
    if max_history is None:
        max_history = settings.LLM_MAX_HISTORY_MESSAGES

    items = list(messages)
    last_user_index = None
    for index in range(len(items) - 1, -1, -1):
        if _field(items[index], "role") == "user":
            last_user_index = index
            break
    if last_user_index is None:
        return None, []

    query = _field(items[last_user_index], "content")

    history: List[ChatMessage] = []
    for item in items[:last_user_index]:
        role = _field(item, "role")
        content = _field(item, "content")
        if role in ("user", "assistant") and content.strip():
            history.append({"role": role, "content": content})

    history = history[-max_history:] if max_history > 0 else []
    while history and history[0]["role"] != "user":
        history.pop(0)
    return query, history


def escape_for_prompt(text: str) -> str:
    """Escape ``&``, ``<`` and ``>`` so content cannot open or close prompt delimiters."""
    return html.escape(text, quote=False)


def format_user_turn(context: str, query: str) -> str:
    """Wrap retrieved context and the question in unambiguous delimiters.

    Both are escaped: the question is user-controlled, and the context may embed
    the question (Angelitic template) or document text containing tag-like markup.
    """
    return (
        f"<retrieved_context>\n{escape_for_prompt(context.strip())}\n</retrieved_context>\n\n"
        f"<question>\n{escape_for_prompt(query)}\n</question>"
    )


def build_generation_messages(
    system_prompt: str,
    context: str,
    query: str,
    history: Optional[List[ChatMessage]] = None,
) -> List[ChatMessage]:
    """System prompt (+ grounding rules), prior turns, then context + question."""
    return [
        {"role": "system", "content": f"{system_prompt.rstrip()}\n\n{GROUNDING_RULES}"},
        *(history or []),
        {"role": "user", "content": format_user_turn(context, query)},
    ]
