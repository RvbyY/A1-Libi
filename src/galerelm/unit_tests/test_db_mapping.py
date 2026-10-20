import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.galerelm.models import Base, Profile, Context, Message, DeepContext, LongTermMemory

def test_sqlalchemy_mappings():
    # Création d'une base de données en mémoire pour tester les schémas
    engine = create_engine('sqlite:///:memory:')
    
    # Si les relations ou colonnes ont un problème, create_all plantera
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()

    # Test d'insertion d'un Profile
    prof = Profile(name="DB User", email="db@user.com", instructions="Do stuff")
    session.add(prof)
    session.commit()
    assert prof.id is not None
    
    # On vérifie qu'il est bien dans la BDD
    fetched_prof = session.query(Profile).filter_by(email="db@user.com").first()
    assert fetched_prof is not None
    assert fetched_prof.name == "DB User"

    # Test d'insertion d'un Context
    ctx = Context(profile_id=prof.id, context_limit=10)
    session.add(ctx)
    session.commit()
    assert ctx.id is not None
    
    # Test d'insertion d'un Message dans le Context
    msg = Message(role="user", content="Hello DB")
    msg.context_id = ctx.id
    session.add(msg)
    session.commit()
    assert msg.id is not None
    
    # Vérification des relations
    fetched_ctx = session.query(Context).filter_by(id=ctx.id).first()
    assert len(fetched_ctx.messages) == 1
    assert fetched_ctx.messages[0].content == "Hello DB"


def test_embedding_service_and_rag_manager():
    from src.galerelm.models import MessageList
    from src.galerelm.rag import EmbeddingService, RAGManager

    assert EmbeddingService.cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert EmbeddingService.cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert EmbeddingService.cosine_similarity([], [1.0]) == 0.0

    class FakeEmbedClient:
        def post(self, endpoint, json=None, **kwargs):
            inp = json.get("input")
            if isinstance(inp, list):
                return {"embeddings": [[1.0, 0.0], [0.0, 1.0]][: len(inp)]}
            return {"embeddings": [[1.0, 0.0]]}

    deep = DeepContext(vector_limit=2)
    rag = RAGManager(api_client=FakeEmbedClient())
    archived = rag.archive(
        deep,
        MessageList([
            Message(role="user", content="Premier souvenir"),
            Message(role="assistant", content="Second souvenir"),
        ]),
    )
    assert len(archived) == 2
    assert len(deep.memories) == 2

    results = rag.search(deep, "Premier", top_k=1)
    assert len(results) == 1
    score, top_mem = results[0]
    assert score == pytest.approx(1.0)
    assert top_mem.content == "Premier souvenir"

