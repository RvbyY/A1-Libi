import pytest

from src.commands.session import NewCommand
from src.config import PROJECT_ROOT, resolve_db_url
from src.galerelm.database import DatabaseManager
from src.galerelm.models import Message, PromptBuilder
from src.galerelm.wrapper import SensAIWrapper
from src.main import SensAI
from src.tools.registry import ToolRegistry
from src.tools import SelfTestTool


class FakeOllama:
    """Faux Ollama : embeddings constants et réponse fixe (aucun appel réseau)."""
    base_url = "http://fake-ollama"

    def __init__(self):
        self.embedded: list[str] = []
        self.chat_requests: list[list[dict]] = []

    def post(self, endpoint, data=None, json=None, **kwargs):
        inputs = json["input"]
        texts = [inputs] if isinstance(inputs, str) else list(inputs)
        self.embedded.extend(texts)
        return {"embeddings": [[1.0, 0.0, 0.0] for _ in texts]}

    def stream_ndjson(self, endpoint, data=None, json_data=None, **kwargs):
        self.chat_requests.append(json_data["messages"])
        yield {"message": {"role": "assistant", "content": "OK"}, "done": True, "model": "llama3.2"}


def make_app():
    app = SensAI(db_url="sqlite:///:memory:")
    app.api = app.chat_engine.api = FakeOllama()
    app.load_or_create_profile(email="memory@test.com", name="Memory")
    return app


def long_term(app):
    return [(m.role, m.content) for m in app.profile.deep_context.memories]


# ── Archivage à l'ouverture d'un nouveau chat ────────────────────────

def test_new_chat_archives_previous_short_chat():
    app = make_app()
    first = app.context
    app.chat("J'habite à Lyon")
    assert long_term(app) == []          # chat court : rien n'a débordé de CONTEXT_LIMIT

    NewCommand().execute(app, "")

    assert app.context is not first
    assert long_term(app) == [("user", "J'habite à Lyon"), ("assistant", "OK")]
    assert len(first.messages) == 2      # l'ancien chat reste intact
    assert all(m.embedding for m in app.profile.deep_context.memories)


def test_new_chat_memory_is_injected_in_next_prompt():
    app = make_app()
    app.chat("J'habite à Lyon")
    NewCommand().execute(app, "")

    app.chat("Où est-ce que j'habite ?")

    system = app.api.chat_requests[-1][0]["content"]
    assert "- [user] J'habite à Lyon" in system
    assert app.chat_engine.last_built_prompt.memories_injected > 0


def test_archiving_is_idempotent_and_skips_noise():
    app = make_app()
    app.context.add(Message(role="user", content="Mon chien s'appelle Rex"))
    app.context.add(Message(role="tool", content="[tools_selftest] Selftest OK: ping"))
    app.context.add(Message(role="assistant", content="   "))
    app.session.commit()

    assert app.session_manager.archive_chats(app.session, app.profile, api_client=app.api) == 1
    assert app.session_manager.archive_chats(app.session, app.profile, api_client=app.api) == 0
    assert long_term(app) == [("user", "Mon chien s'appelle Rex")]


def test_every_previous_chat_is_archived():
    app = make_app()
    app.chat("Chat A")
    NewCommand().execute(app, "")
    app.chat("Chat B")
    NewCommand().execute(app, "")

    contents = [content for _, content in long_term(app)]
    assert contents.count("Chat A") == 1
    assert contents.count("Chat B") == 1


def test_webapp_new_chat_archives_previous_chats():
    wrapper = SensAIWrapper(db_url="sqlite:///:memory:")
    fake = FakeOllama()
    wrapper.core.api = wrapper.engine.api = fake
    wrapper.create_profile(email="web@test.com", name="Web")
    first_chat = wrapper.list_chats("web@test.com")[0].id
    list(wrapper.chat_stream("web@test.com", "J'habite à Lyon", context_id=first_chat))

    wrapper.start_new_chat("web@test.com")

    assert "J'habite à Lyon" in fake.embedded
    with wrapper.core.db.session_scope() as session:
        profile = wrapper.sessions.get_profile(session, "web@test.com")
        assert ("user", "J'habite à Lyon") in [(m.role, m.content) for m in profile.deep_context.memories]


# ── Place et consigne des souvenirs dans le prompt ───────────────────

def test_memories_come_first_with_usage_instruction():
    system = (
        PromptBuilder()
        .with_rules(["Règle en plus."])
        .with_tools(ToolRegistry([SelfTestTool()]))
        .with_memories(["[user] J'habite à Lyon"])
        .build()
        .system_content
    )
    memories = system.index("Souvenirs de tes conversations précédentes")
    assert "au lieu de dire que tu ne sais pas" in system
    assert memories < system.index("Règles complémentaires")
    assert memories < system.index("Outils disponibles")
    assert system.index("- [user] J'habite à Lyon") > memories


# ── Chemin de la base de données ─────────────────────────────────────

@pytest.mark.parametrize("url, expected", [
    ("sqlite:///galerelm.db", f"sqlite:///{PROJECT_ROOT / 'galerelm.db'}"),
    ("sqlite:///data/app.db", f"sqlite:///{PROJECT_ROOT / 'data' / 'app.db'}"),
    ("sqlite:////tmp/app.db", "sqlite:////tmp/app.db"),
    ("sqlite:///:memory:", "sqlite:///:memory:"),
    ("postgresql://user@host/db", "postgresql://user@host/db"),
])
def test_resolve_db_url(url, expected):
    assert resolve_db_url(url) == expected


def test_database_path_does_not_depend_on_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = DatabaseManager(db_url="sqlite:///test_cwd_check.db")
    try:
        assert db.db_url == f"sqlite:///{PROJECT_ROOT / 'test_cwd_check.db'}"
        assert not (tmp_path / "test_cwd_check.db").exists()
    finally:
        db.engine.dispose()
        (PROJECT_ROOT / "test_cwd_check.db").unlink(missing_ok=True)
