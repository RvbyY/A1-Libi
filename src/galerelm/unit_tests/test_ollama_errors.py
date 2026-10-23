import json

import httpx
import pytest

from src.galerelm.models.chat import Chat
from src.galerelm.ollama import (
    ModelNotFoundError,
    OllamaError,
    OllamaTimeoutError,
    OllamaUnreachableError,
    check_ollama,
    model_is_available,
    translate_error,
)
from src.rapideAPI.client import RapideAPI

HOST = "http://fake-ollama:11434"


def api_with(handler) -> RapideAPI:
    """RapideAPI branché sur un transport httpx factice (aucun appel réseau)."""
    api = RapideAPI(base_url=HOST)
    api.session = httpx.Client(transport=httpx.MockTransport(handler))
    return api


def capture(fn):
    try:
        fn()
    except Exception as exc:
        return exc
    pytest.fail("Une exception était attendue")


# ── translate_error sur de vraies réponses httpx ─────────────────────

def test_connection_refused_becomes_unreachable():
    def refuse(request):
        raise httpx.ConnectError("Connection refused", request=request)

    exc = capture(lambda: api_with(refuse).get("api/tags"))
    error = translate_error(exc, host=HOST)
    assert isinstance(error, OllamaUnreachableError)
    assert HOST in error.message
    assert "ollama serve" in error.hint


def test_timeout_is_reported_as_timeout():
    def slow(request):
        raise httpx.ReadTimeout("timed out", request=request)

    exc = capture(lambda: api_with(slow).get("api/tags"))
    assert isinstance(translate_error(exc, host=HOST), OllamaTimeoutError)


def test_streamed_404_becomes_model_not_found():
    def missing(request):
        return httpx.Response(404, json={"error": 'model "ghost" not found, try pulling it first'})

    api = api_with(missing)
    exc = capture(lambda: list(api.stream_ndjson("api/chat", json_data={"model": "ghost", "messages": []})))
    error = translate_error(exc, host=HOST, model="fallback")
    assert isinstance(error, ModelNotFoundError)
    assert error.model == "ghost"
    assert "ollama pull ghost" in error.hint


def test_other_http_error_keeps_ollama_detail():
    def broken(request):
        return httpx.Response(500, json={"error": "out of memory"})

    exc = capture(lambda: api_with(broken).post("api/chat", json={"model": "x"}))
    error = translate_error(exc, host=HOST)
    assert type(error) is OllamaError
    assert "500" in error.message and "out of memory" in error.message


def test_unknown_endpoint_404_is_not_a_missing_model():
    exc = capture(lambda: api_with(lambda r: httpx.Response(404, text="404 page not found")).get("api/nope"))
    assert not isinstance(translate_error(exc, host=HOST), ModelNotFoundError)


def test_non_http_exceptions_are_left_untouched():
    original = ValueError("bug")
    assert translate_error(original) is original


def test_error_chunk_in_stream_raises():
    def error_mid_stream(request):
        lines = [{"message": {"content": "Bon"}, "done": False}, {"error": "model crashed"}]
        return httpx.Response(200, content="\n".join(json.dumps(l) for l in lines))

    chat = Chat(model="llama3.2", api=api_with(error_mid_stream))
    with pytest.raises(OllamaError, match="model crashed"):
        list(chat.execute_stream())


# ── Vérification au démarrage ────────────────────────────────────────

def tags(*names):
    return lambda request: httpx.Response(200, json={"models": [{"name": n} for n in names]})


@pytest.mark.parametrize("model, installed, expected", [
    ("llama3.2", ["llama3.2:latest"], True),
    ("llama3.2:latest", ["llama3.2:latest"], True),
    ("llama3.2:1b", ["llama3.2:latest"], False),
    ("hf.co/org/model", ["hf.co/org/model:latest"], True),
    ("mistral", ["llama3.2:latest"], False),
])
def test_model_is_available(model, installed, expected):
    assert model_is_available(model, installed) is expected


def test_check_ollama_ok_with_warning_for_missing_embedding_model():
    warnings = check_ollama(api_with(tags("llama3.2:latest")), "llama3.2", "nomic-embed-text")
    assert len(warnings) == 1
    assert "ollama pull nomic-embed-text" in warnings[0]


def test_check_ollama_missing_chat_model_lists_installed_ones():
    with pytest.raises(ModelNotFoundError) as info:
        check_ollama(api_with(tags("mistral:latest", "qwen2.5:7b")), "llama3.2")
    assert info.value.available == ["mistral:latest", "qwen2.5:7b"]


def test_check_ollama_unreachable():
    def refuse(request):
        raise httpx.ConnectError("Connection refused", request=request)

    with pytest.raises(OllamaUnreachableError):
        check_ollama(api_with(refuse), "llama3.2")


def test_check_ollama_rejects_non_ollama_server():
    with pytest.raises(OllamaError, match="serveur Ollama"):
        check_ollama(api_with(lambda r: httpx.Response(200, text="<html>hello</html>")), "llama3.2")
