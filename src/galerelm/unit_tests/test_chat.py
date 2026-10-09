import pytest
from src.galerelm.models import (
    Message, MessageList, Chat, Options, Tools, ToolsList, ToolsFunction,
    ChatResponse, ToolCalls, ToolCallsFunction, LogProb, TopLogProb
)
from src.rapideAPI import RapideAPI

def test_message_format():
    msg = Message(role="user", content="Hello", thinking="Hmm")
    d = msg.format()
    assert d["role"] == "user"
    assert d["content"] == "Hello"
    # thinking n'est plus retourné dans le payload
    assert "thinking" not in d
    assert "images" not in d or len(d["images"]) == 0

def test_tool_calls_format():
    tc_func = ToolCallsFunction(name="weather", description="Get weather", arguments={"city": "Paris"})
    tc = ToolCalls(functions=[tc_func])
    d = tc.format()
    assert "function" in d
    assert d["function"]["name"] == "weather"
    assert d["function"]["arguments"]["city"] == "Paris"
    tc_back = ToolCalls.from_format(d)
    assert len(tc_back.functions) == 1
    assert tc_back.functions[0].name == "weather"

def test_options_format():
    opts = Options(seed=42, temperature=0.7, top_k=50, top_p=0.9, min_p=0.0, stop=["\n"], num_ctx=1024, num_predict=100)
    d = opts.format()
    assert d["seed"] == 42
    assert d["temperature"] == 0.7
    opts_back = Options.from_format(d)
    assert opts_back.seed == 42
    assert opts_back.temperature == 0.7

def test_chat_format():
    opts = Options(seed=42)
    msgs = MessageList([
        Message(role="user", content="Hi")
    ])
    api = RapideAPI(base_url="http://fake")
    chat = Chat(
        model="llama3",
        api=api,
        messages=msgs,
        system_prompt="You are a bot",
        options=opts
    )
    d = chat.format()
    assert d["model"] == "llama3"
    assert d["stream"] is True
    assert len(d["messages"]) == 2  # system + user
    assert d["messages"][0]["role"] == "system"
    assert d["messages"][1]["role"] == "user"
    assert d["options"]["seed"] == 42

def test_chat_response():
    data = {
        "model": "llama3",
        "created_at": "2023-11-07T05:31:56Z",
        "message": {
            "role": "assistant",
            "content": "The sky is blue.",
        },
        "done": True,
        "total_duration": 123,
        "eval_count": 5
    }
    resp = ChatResponse.from_format(data)
    assert resp.model == "llama3"
    assert resp.done is True
    assert resp.message.role == "assistant"
    assert resp.message.content == "The sky is blue."

def test_logprob_format():
    top_lp = TopLogProb(token="sky", logprob=-0.5, bytes_repr=[115, 107, 121])
    lp = LogProb(token="the", logprob=-0.1, bytes_repr=[116, 104, 101], top_logprobs=[top_lp])
    d = lp.format()
    assert d["token"] == "the"
    assert d["logprob"] == -0.1
    assert len(d["top_logprobs"]) == 1
    assert d["top_logprobs"][0]["token"] == "sky"
    lp_back = LogProb.from_format(d)
    assert lp_back.token == "the"
    assert lp_back.top_logprobs[0].token == "sky"

def test_empty_from_format():
    assert ToolCallsFunction.from_format(None) is None
    assert ToolCalls.from_format(None) is None
    assert Message.from_format(None) is None
    assert Options.from_format(None) is None
    assert ChatResponse.from_format(None) is None
    assert len(MessageList.from_format(None)) == 0

def test_from_format_empty_dict():
    assert Message.from_format({}).role == "user"
    assert Options.from_format({}).seed == 0
    assert ChatResponse.from_format({}).model == ""
