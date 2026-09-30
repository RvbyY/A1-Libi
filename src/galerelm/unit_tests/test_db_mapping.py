import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.galerelm.models.chat import Base, GenerateRequest, Options, GenerateResponse
from src.galerelm.models.profile import Profile

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

    # Test d'insertion d'un GenerateRequest
    opts = Options(seed=123, temperature=0.5, top_k=10, top_p=0.9, min_p=0.0, stop=["\n"], num_ctx=512, num_predict=50)
    req = GenerateRequest(
        model="db_model",
        prompt="Hello DB",
        suffix=None,
        images=[],
        request_format="json",
        system=None,
        stream=True,
        think=False,
        raw=False,
        keep_alive="1m",
        logprobs=False,
        top_logprobs=None,
        options=opts
    )
    
    session.add(req)
    session.commit()
    
    # On vérifie que l'ID a bien été généré (preuve que c'est une table SQL)
    assert req.id is not None
    assert req.options.id is not None
    
    # On vérifie la relation GenerateRequest -> Options
    fetched_req = session.query(GenerateRequest).filter_by(model="db_model").first()
    assert fetched_req is not None
    assert fetched_req.prompt == "Hello DB"
    assert fetched_req.options.seed == 123
