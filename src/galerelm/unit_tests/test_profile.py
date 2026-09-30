import pytest
from src.galerelm.models.profile import Profile

def test_profile_creation():
    p = Profile(name="Test User", email="test@test.com", instructions="Do something")
    assert p.name == "Test User"
    assert p.email == "test@test.com"
    assert p.instructions == "Do something"
    assert p.password == ""
    assert p.id is not None
    assert isinstance(p.id, str)

def test_profile_format():
    p = Profile(name="Test User", email="test@test.com", instructions="Do something")
    d = p.format()
    assert d["name"] == "Test User"
    assert d["email"] == "test@test.com"
    assert "id" in d

def test_profile_from_format():
    data = {
        "id": "custom-uuid-123",
        "name": "Jane",
        "email": "jane@doe.com",
        "password": "hashed_password",
        "instructions": "Be polite"
    }
    p = Profile.from_format(data)
    assert p.id == "custom-uuid-123"
    assert p.name == "Jane"
    assert p.email == "jane@doe.com"
    assert p.password == "hashed_password"
    assert p.instructions == "Be polite"

def test_profile_from_format_empty():
    p = Profile.from_format(None)
    assert p is None
