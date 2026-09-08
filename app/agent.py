"""The agent brain: a manual Claude tool-use loop.

We use a manual loop (rather than the beta tool runner) so the POC has no beta
dependency and full control over tool dispatch + per-conversation persistence.
See docs/02-architecture.md, Section D & F.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import anthropic

from . import db, tools
from .config import get_settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "system_prompt.md"
_MAX_TOOL_ITERATIONS = 6


@lru_cache
def _client() -> anthropic.Anthropic:
    settings = get_settings()
    if settings.anthropic_api_key:
        return anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return anthropic.Anthropic()  # resolves from env / `ant auth login`


@lru_cache
def _system_prompt() -> str:
    settings = get_settings()
    template = _PROMPT_PATH.read_text()
    faq = (Path(__file__).resolve().parent.parent / "data" / "faq.md").read_text()
    return (
        template.format(business_name=settings.business_name)
        + "\n\n# Knowledge base (studio FAQ)\n"
        + faq
    )


def generate_reply(ig_user_id: str, user_text: str, referenced_media_id: str | None = None) -> str:
    """Run the agent loop for one inbound message and return the reply text.

    The inbound message is expected to already be persisted by the caller. This
    function persists the outbound reply.
    """
    settings = get_settings()
    client = _client()

    history = db.get_history(ig_user_id, limit=20)

    # Give the model the media reference (if the DM was a story-reply/post-share)
    # as a lightweight system-style hint appended to the latest user turn.
    latest = user_text
    if referenced_media_id:
        latest = f"[Customer is referring to Instagram media id: {referenced_media_id}]\n{user_text}"

    # history already includes the just-logged inbound message as the last 'user'
    # entry; replace its content with the media-annotated version.
    if history and history[-1]["role"] == "user":
        history[-1]["content"] = latest
    else:
        history.append({"role": "user", "content": latest})

    messages = history

    final_text = ""
    for _ in range(_MAX_TOOL_ITERATIONS):
        response = client.messages.create(
            model=settings.claude_model,
            max_tokens=1024,
            system=[
                {
                    "type": "text",
                    "text": _system_prompt(),
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            tools=tools.tool_definitions(),
            messages=messages,
        )

        if response.stop_reason == "tool_use":
            messages.append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result, is_error = tools.execute_tool(block.name, block.input, ig_user_id)
                    logger.info("tool=%s error=%s", block.name, is_error)
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                            "is_error": is_error,
                        }
                    )
            messages.append({"role": "user", "content": tool_results})
            continue

        # Natural end of turn (or refusal): collect the text.
        final_text = "".join(b.text for b in response.content if b.type == "text").strip()
        break

    if not final_text:
        final_text = (
            "Thanks for your message! Let me connect you with a specialist who "
            "can help — someone will follow up shortly."
        )

    db.log_message(ig_user_id, "out", final_text)
    return final_text
