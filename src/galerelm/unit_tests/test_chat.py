import pytest

from src.galerelm.models.chat import (
    Message, MessageList, Chat, Options, Tools, ToolsList, ToolsFunction,
    ChatResponse, ToolCalls, ToolCallsFunction, LogProb, TopLogProb
)


def test_message_format():
    msg = Message(role="user", content="Hello", thinking="Hmm")
    d = msg.format()
    assert d["role"] == "user"
    assert d["content"] == "Hello"
    assert d["thinking"] == "Hmm"
    assert "images" not in d or len(d["images"]) == 0

    msg_back = Message.from_format(d)
    assert msg_back.role == "user"
    assert msg_back.content == "Hello"
    assert msg_back.thinking == "Hmm"


def test_tool_calls_format():
    tc_func = ToolCallsFunction(name="weather", description="get weather", arguments={"city": "Paris"})
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
    opts = Options(seed=42, temperature=0.7, top_k=50, top_p=0.9, min_p=0.0, stop=["\n"], num_ctx=1024, num_predict=100)
    tools = ToolsList([
        Tools(tool_type="function", tool_function=ToolsFunction("get_weather", {"loc": "str"}, "Get weather"))
    ])
    msgs = MessageList([
        Message(role="system", content="You are a bot")
    ])

    chat = Chat(
        model="llama3",
        messages=msgs,
        tools=tools,
        request_format="json",
        options=opts,
        stream=False,
        think=False,
        keep_alive="5m",
        logprobs=True,
        top_logprobs=5
    )

    d = chat.format()
    assert d["model"] == "llama3"
    assert d["stream"] is False
    assert len(d["messages"]) == 1
    assert len(d["tools"]) == 1
    assert d["options"]["seed"] == 42
    assert d["think"] is False

    chat_back = Chat.from_format(d)
    assert chat_back.model == "llama3"
    assert chat_back.stream is False
    assert len(chat_back.messages) == 1
    assert chat_back.messages[0].role == "system"
    assert chat_back.options.seed == 42


def test_chat_response():
    data = {
        "model": "llama3",
        "created_at": "2023-11-07T05:31:56Z",
        "message": {
            "role": "assistant",
            "content": "The sky is blue.",
            "thinking": "Thinking...",
        },
        "done": True,
        "done_reason": "stop",
        "total_duration": 123,
        "load_duration": 123,
        "prompt_eval_count": 123,
        "prompt_eval_cached_count": 123,
        "prompt_eval_duration": 123,
        "eval_count": 123,
        "eval_duration": 123
    }
    resp = ChatResponse.from_format(data)
    assert resp.model == "llama3"
    assert resp.done is True
    assert resp.message.role == "assistant"
    assert resp.message.content == "The sky is blue."
    assert resp.message.thinking == "Thinking..."

    d = resp.format()
    assert d["model"] == "llama3"
    assert d["message"]["content"] == "The sky is blue."
    assert d["total_duration"] == 123


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
    # Tests that providing None returns None gracefully
    assert ToolCallsFunction.from_format(None) is None
    assert ToolCalls.from_format(None) is None
    assert Message.from_format(None) is None
    assert ToolsFunction.from_format(None) is None
    assert Tools.from_format(None) is None
    assert Options.from_format(None) is None
    assert Chat.from_format(None) is None
    assert TopLogProb.from_format(None) is None
    assert LogProb.from_format(None) is None
    assert ChatResponse.from_format(None) is None

    # UserLists return empty lists
    assert len(MessageList.from_format(None)) == 0
    assert len(ToolsList.from_format(None)) == 0


def test_from_format_empty_dict():
    # Tests that providing {} falls back to default values properly
    assert Message.from_format({}).role == "user"
    assert Options.from_format({}).seed == 0
    assert Chat.from_format({}).model == ""
    assert len(ToolCalls.from_format({}).functions) == 0
    assert ToolCallsFunction.from_format({}).name == ""
    assert ToolsFunction.from_format({}).name == ""
    assert Tools.from_format({}).tool_type == "function"
    assert TopLogProb.from_format({}).token == ""
    assert LogProb.from_format({}).token == ""
    assert ChatResponse.from_format({}).model == ""


def test_format_all():
    ml = MessageList([
        Message(role="user", content="Hello"),
        Message(role="assistant", content="Hi")
    ])
    assert ml.format_all() == "Hello\n---\nHi"

    tl = ToolsList([])
    assert tl.format_all() == ""


def test_chat_none_fields():
    chat = Chat(
        model="llama3",
        messages=MessageList([]),
        tools=None,
        request_format=None,
        options=None,
        stream=True,
        think=None,
        keep_alive=None,
        logprobs=None,
        top_logprobs=None
    )
    d = chat.format()
    # Missing fields should be ignored in the dict
    assert "tools" not in d
    assert "options" not in d
    assert "format" not in d
    assert "think" not in d
    assert "keep_alive" not in d
    assert "logprobs" not in d
    assert "top_logprobs" not in d


def test_chat_response_none_fields():
    resp = ChatResponse(
        model="m", created_at="now", message=None, done=True, done_reason="stop",
        total_duration=1, load_duration=1, prompt_eval_count=1, prompt_eval_cached_count=1,
        prompt_eval_duration=1, eval_count=1, eval_duration=1, logprobs=None
    )
    d = resp.format()
    assert d["message"] is None
    assert "logprobs" not in d


def test_tool_calls_edge_cases():
    # Test when function in JSON is not a dict
    tc = ToolCalls.from_format({"function": "not_a_dict"})
    assert len(tc.functions) == 0