"""Bundled frontend SSE parser tests (requires Node.js; skipped if unavailable).

Runs the Node unit tests, then replays real server SSE bodies (buffered
responses with keep-alives, Tamil text, emergency and error streams) through
the browser parser in random-size byte fragments.
"""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api import routes_chat
from app.core.config import settings
from app.main import app
from app.models.base import LLMRefusalError
from app.rag.guardrails import Guardrails
from tests.test_chat_integration import GUIDE_DOC, ScriptedProvider, make_chain

NODE = shutil.which("node")
FRONTEND_TESTS = Path(__file__).parent / "frontend"
pytestmark = pytest.mark.skipif(NODE is None, reason="Node.js is not installed")

client = TestClient(app)


def replay(body: bytes, tmp_path: Path, seed: int):
    path = tmp_path / f"body-{seed}.txt"
    path.write_bytes(body)
    result = subprocess.run(
        [NODE, str(FRONTEND_TESTS / "replay_stream.mjs"), str(path), str(seed)],
        capture_output=True, text=True, encoding="utf-8", timeout=60, check=True,
    )
    return json.loads(result.stdout)


def test_node_parser_unit_tests():
    result = subprocess.run(
        [NODE, "--test", str(FRONTEND_TESTS / "sse_parser.test.mjs")],
        capture_output=True, text=True, encoding="utf-8", timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_real_buffered_stream_parses_in_fragments(monkeypatch, tmp_path):
    tamil = "இயல்பான மூச்சை கவனியுங்கள்."
    provider = ScriptedProvider(["Observe the natural breath. ", tamil])

    async def slow_stream(messages, *, temperature=None, max_tokens=None):
        import asyncio
        await asyncio.sleep(0.05)
        for chunk in provider.chunks:
            yield chunk

    provider.stream = slow_stream
    monkeypatch.setattr(settings, "SSE_KEEPALIVE_SECONDS", 0.01)
    monkeypatch.setattr(routes_chat, "rag_chain", make_chain(provider, documents=[GUIDE_DOC]))

    body = client.post("/api/chat", json={"messages": [{"role": "user", "content": "q"}], "stream": True}).content
    assert body.startswith(b": keep-alive")

    for seed in (1, 7, 42):
        events = replay(body, tmp_path, seed)
        types = [e["type"] for e in events]
        assert types[-2:] == ["citations", "done"] and types.count("done") == 1
        assert "parse_error" not in types
        text = "".join(e["chunk"] for e in events if e["type"] == "content")
        assert text == "Observe the natural breath. " + tamil
        assert events[-2]["citations"] == [{"title": "Nettrikkan Guide", "reference": "page 3"}]


def test_emergency_and_error_streams_parse(monkeypatch, tmp_path):
    emergency = client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "I am in crisis"}], "stream": True}).content
    events = replay(emergency, tmp_path, 3)
    assert "".join(e["chunk"] for e in events if e["type"] == "content") == Guardrails().handle_emergency()
    assert [e["type"] for e in events][-1] == "done"

    monkeypatch.setattr(routes_chat, "rag_chain",
                        make_chain(ScriptedProvider(["partial"], error=LLMRefusalError("x"))))
    error_body = client.post("/api/chat", json={
        "messages": [{"role": "user", "content": "q"}], "stream": True}).content
    events = replay(error_body, tmp_path, 5)
    assert [e["type"] for e in events] == ["error"]
