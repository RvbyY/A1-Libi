import pytest

from src.commands import DocumentsCommand, IngestCommand
from src.galerelm.documents import DocumentStore, chunk_text, collect_files
from src.galerelm.graph import HallucinationGrade
from src.galerelm.models import DocumentChunk
from src.main import SensAI

KEYWORDS = ("vacances", "remboursement", "télétravail", "salaire")


def keyword_vector(text: str) -> list[float]:
    """Vecteur jouet : un axe par mot-clé, pour que la recherche « par le sens » soit vérifiable."""
    lower = text.lower()
    return [float(lower.count(word)) for word in KEYWORDS] + [0.1]


class FakeOllama:
    base_url = "http://fake"

    def __init__(self):
        self.systems = []

    def post(self, endpoint, json=None, **kwargs):
        inputs = json["input"]
        texts = [inputs] if isinstance(inputs, str) else inputs
        return {"embeddings": [keyword_vector(t) for t in texts]}

    def stream_ndjson(self, endpoint, json_data=None, **kwargs):
        messages = json_data["messages"]
        self.systems.append(messages[0]["content"] if messages[0]["role"] == "system" else "")
        yield {"message": {"role": "assistant", "content": "D'après [rh.md#1], 25 jours."}, "done": True, "model": "m"}


@pytest.fixture
def docs(tmp_path):
    folder = tmp_path / "docs"
    (folder / "sous").mkdir(parents=True)
    (folder / "rh.md").write_text("# Congés\n\nChaque salarié a droit à 25 jours de vacances par an.", encoding="utf-8")
    (folder / "sous" / "frais.txt").write_text("Le remboursement des frais se fait sous 30 jours.", encoding="utf-8")
    (folder / "image.png").write_bytes(b"\x89PNG")
    (folder / ".cache").mkdir()
    (folder / ".cache" / "secret.md").write_text("vacances cachées", encoding="utf-8")
    return folder


def make_app():
    app = SensAI(db_url="sqlite:///:memory:")
    app.api = app.chat_engine.api = FakeOllama()
    app.load_or_create_profile(email="docs@test.com", name="Docs")
    return app


# ── Découpage ────────────────────────────────────────────────────────

def test_chunks_respect_size_and_overlap():
    text = "\n\n".join(f"Paragraphe {i}. " + "mot " * 60 for i in range(12))
    chunks = chunk_text(text, size=500, overlap=80)
    assert len(chunks) > 3
    assert all(len(c) <= 500 for c in chunks)
    assert all(c.startswith(("Paragraphe", "mot")) for c in chunks)   # coupe entre deux mots, jamais au milieu
    assert chunks[0][-40:].split()[-1] in chunks[1]                    # le fragment suivant reprend la fin


def test_short_text_is_one_chunk_and_bad_overlap_is_refused():
    assert chunk_text("Une phrase.") == ["Une phrase."]
    assert chunk_text("   \n\n ") == []
    with pytest.raises(ValueError):
        chunk_text("x", size=100, overlap=100)


def test_collect_files_keeps_text_files_only(docs):
    names = [f.name for f in collect_files(docs)]
    assert names == ["rh.md", "frais.txt"]      # ni le PNG, ni le dossier caché
    with pytest.raises(FileNotFoundError):
        collect_files(docs / "absent")


# ── Ingestion et recherche ───────────────────────────────────────────

def test_ingest_search_and_reingest(docs):
    app = make_app()
    store = app.chat_engine.documents
    report = store.ingest(app.session, app.profile.id, str(docs), api_client=app.api)
    assert (report.files, report.chunks, report.vectorized) == (2, 2, 2)

    results = store.search(app.session, app.profile.id, "Combien de jours de vacances ?", api_client=app.api, top_k=1)
    assert results[0][1].source.endswith("rh.md") and results[0][1].label.endswith("rh.md#1")

    (docs / "rh.md").write_text("Nouvelle règle : 30 jours de vacances.", encoding="utf-8")
    store.ingest(app.session, app.profile.id, str(docs / "rh.md"), api_client=app.api)
    contents = [c.content for c in app.session.query(DocumentChunk).all()]
    assert "Nouvelle règle : 30 jours de vacances." in contents and len(contents) == 2   # remplacé, pas dupliqué


def test_documents_are_private_to_each_profile(docs):
    app = make_app()
    app.chat_engine.documents.ingest(app.session, app.profile.id, str(docs), api_client=app.api)
    other = app.session_manager.get_or_create_profile(app.session, "autre@test.com", "Autre")
    assert app.chat_engine.documents.search(app.session, other.id, "vacances", api_client=app.api) == []


def test_prompt_cites_document_extracts(docs):
    app = make_app()
    app.chat_engine.documents.ingest(app.session, app.profile.id, str(docs), api_client=app.api)
    app.chat("Combien de jours de vacances ai-je ?")
    system = app.api.systems[-1]
    assert "Extraits de documents de l'utilisateur" in system
    assert "rh.md#1] # Congés Chaque salarié a droit à 25 jours de vacances" in system
    assert app.chat_engine.last_built_prompt.documents_injected == 2


def test_no_document_block_without_documents():
    app = make_app()
    app.chat("Bonjour")
    assert "Extraits de documents" not in app.api.systems[-1]


def test_anti_hallucination_judge_receives_document_facts(docs):
    class Judge:
        facts = None

        def grade(self, user_input, candidate, facts=None):
            Judge.facts = facts
            return HallucinationGrade(grounded=True)

    app = make_app()
    app.chat_engine.hallucination_grader = Judge()
    app.chat_engine.documents.ingest(app.session, app.profile.id, str(docs), api_client=app.api)
    app.chat("Combien de jours de vacances ?")
    assert any("25 jours de vacances" in fact for fact in Judge.facts)
    assert any("rh.md#1" in system for system in app.api.systems)


# ── Commandes ────────────────────────────────────────────────────────

def test_ingest_and_documents_commands(docs, capsys):
    app = make_app()
    IngestCommand().execute(app, str(docs))
    assert "2 fichier(s), 2 fragment(s) ajoutés (2 vectorisés)" in capsys.readouterr().out
    DocumentsCommand().execute(app, "")
    out = capsys.readouterr().out
    assert "rh.md" in out and "frais.txt" in out
    DocumentsCommand().execute(app, f"oublier {docs / 'rh.md'}")
    assert "1 fragment(s) supprimé(s)" in capsys.readouterr().out
    DocumentsCommand().execute(app, "oublier tout")
    DocumentsCommand().execute(app, "")
    assert "Aucun document" in capsys.readouterr().out


def test_ingest_command_errors(tmp_path, capsys):
    app = make_app()
    IngestCommand().execute(app, "")
    assert "Usage" in capsys.readouterr().out
    IngestCommand().execute(app, str(tmp_path / "absent"))
    assert "Chemin introuvable" in capsys.readouterr().out
