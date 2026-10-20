import pytest
from src.galerelm.models import (
    Prompt, PromptBuilder, PromptTemplate, Profile, LongTermMemory, Chat, MessageList
)
from src.tools.registry import ToolRegistry
from src.tools.calendar.calendar_tools import Calendar
from src.rapideAPI import RapideAPI


def test_prompt_template_variables_and_render():
    tpl = PromptTemplate(
        template="Bonjour {name}, tu es {persona}.\nRègles:\n{rules}",
        defaults={"persona": "SensAI"},
        rules=["Sois précis", "Réponds vite"],
    )
    assert tpl.variables == {"name", "persona", "rules"}

    rendered = tpl.render(name="Alice")
    assert "Bonjour Alice, tu es SensAI." in rendered
    assert "- Sois précis" in rendered
    assert "- Réponds vite" in rendered


def test_prompt_template_missing_variable_raises():
    tpl = PromptTemplate(template="Requête de {user}: {query}")
    with pytest.raises(ValueError, match="Variables manquantes"):
        tpl.render(user="Bob")


def test_prompt_template_serialization():
    tpl = PromptTemplate.default_system(persona="Alibi")
    data = tpl.format()
    restored = PromptTemplate.from_format(data)
    assert restored is not None
    assert restored.render() == tpl.render()
    assert PromptTemplate.from_format(None) is None


def test_intent_classifier_templates():
    cls_tpl = PromptTemplate.intent_classifier()
    rendered = cls_tpl.render(user_input="Comment cuisiner des pâtes ?")
    assert "Comment cuisiner des pâtes ?" in rendered
    assert '"category": "LEGAL"' in rendered

    amb_tpl = PromptTemplate.ambiguity_resolver()
    rendered_amb = amb_tpl.render(user_input="Test requête")
    assert "Test requête" in rendered_amb


def test_prompt_builder_with_profile_memories_and_tools():
    profile = Profile(
        name="TestUser",
        email="user@test.com",
        instructions="Tu es {persona}, assistant personnel.",
    )
    memories = [
        (0.92, LongTermMemory(role="user", content="J'habite à Lyon", embedding=[0.1, 0.2])),
        LongTermMemory(role="assistant", content="Noté pour Lyon.", embedding=[0.1, 0.2]),
    ]
    registry = ToolRegistry([Calendar()])

    prompt = (
        PromptBuilder()
        .with_persona("SensAI")
        .with_profile(profile)
        .with_rules(["Vérifie toujours l'agenda."])
        .with_memories(memories)
        .with_tools(registry)
        .with_user_query("Quel temps fait-il chez moi ?")
        .build()
    )

    assert "Tu es SensAI, assistant personnel." in prompt.system_content
    assert "Vérifie toujours l'agenda." in prompt.system_content
    assert "- calendar:" in prompt.system_content
    assert "- [user] J'habite à Lyon" in prompt.system_content
    assert prompt.memories_injected == 2
    assert prompt.tools_injected == 1
    assert prompt.user_content == "Quel temps fait-il chez moi ?"

    sys_msg = prompt.to_system_message()
    assert sys_msg.role == "system"
    assert sys_msg.content == prompt.system_content

    usr_msg = prompt.to_user_message()
    assert usr_msg.role == "user"
    assert usr_msg.content == "Quel temps fait-il chez moi ?"


def test_chat_accepts_prompt_object():
    prompt = (
        PromptBuilder()
        .with_instructions("Tu es un assistant.")
        .with_memories(["Souvenir 1"])
        .build()
    )
    chat = Chat(
        model="llama3.2",
        api=RapideAPI(base_url="http://localhost:11434"),
        messages=MessageList([]),
        system_prompt=prompt,
    )
    payload = chat.format()
    assert payload["messages"][0]["role"] == "system"
    assert "Souvenir 1" in payload["messages"][0]["content"]
