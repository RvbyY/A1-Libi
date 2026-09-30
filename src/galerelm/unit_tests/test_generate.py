import pytest
from src.galerelm.models.chat import (
    GenerateRequest, GenerateResponse, Options, LogProb, TopLogProb
)

def test_options_format():
    opts = Options(seed=42, temperature=0.7, top_k=50, top_p=0.9, min_p=0.0, stop=["\n"], num_ctx=1024, num_predict=100)
    d = opts.format()
    assert d["seed"] == 42
    assert d["temperature"] == 0.7
    
    opts_back = Options.from_format(d)
    assert opts_back.seed == 42
    assert opts_back.temperature == 0.7

def test_generate_request_format():
    opts = Options(seed=42, temperature=0.7, top_k=50, top_p=0.9, min_p=0.0, stop=["\n"], num_ctx=1024, num_predict=100)
    
    req = GenerateRequest(
        model="llama3",
        prompt="Hello world",
        suffix="!",
        images=["img1"],
        request_format="json",
        system="You are an AI",
        stream=False,
        think=False,
        raw=True,
        keep_alive="5m",
        logprobs=True,
        top_logprobs=5,
        options=opts
    )

    d = req.format()
    assert d["model"] == "llama3"
    assert d["prompt"] == "Hello world"
    assert d["suffix"] == "!"
    assert d["images"] == ["img1"]
    assert d["stream"] is False
    assert d["raw"] is True
    assert d["options"]["seed"] == 42
    assert d["think"] is False

    req_back = GenerateRequest.from_format(d)
    assert req_back.model == "llama3"
    assert req_back.prompt == "Hello world"
    assert req_back.stream is False
    assert req_back.images == ["img1"]
    assert req_back.options.seed == 42

def test_generate_request_none_fields():
    req = GenerateRequest(
        model="llama3",
        prompt="Hi",
        suffix=None,
        images=None,
        request_format=None,
        system=None,
        stream=True,
        think=None,
        raw=False,
        keep_alive=None,
        logprobs=None,
        top_logprobs=None,
        options=None
    )
    d = req.format()
    assert "suffix" not in d
    assert "options" not in d
    assert "format" not in d
    assert "think" not in d
    assert "keep_alive" not in d
    assert "logprobs" not in d
    assert "top_logprobs" not in d

def test_generate_response():
    data = {
        "model": "llama3",
        "created_at": "2023-11-07T05:31:56Z",
        "response": "The sky is blue.",
        "thinking": "Thinking...",
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
    resp = GenerateResponse.from_format(data)
    assert resp.model == "llama3"
    assert resp.done is True
    assert resp.response == "The sky is blue."
    assert resp.thinking == "Thinking..."

    d = resp.format()
    assert d["model"] == "llama3"
    assert d["response"] == "The sky is blue."
    assert d["total_duration"] == 123

def test_generate_response_none_fields():
    resp = GenerateResponse(
        model="m", created_at="now", response="res", done=True, done_reason="stop",
        total_duration=1, load_duration=1, prompt_eval_count=1, prompt_eval_cached_count=1,
        prompt_eval_duration=1, eval_count=1, eval_duration=1, thinking=None, logprobs=None
    )
    d = resp.format()
    assert "thinking" not in d
    assert "logprobs" not in d

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
    assert Options.from_format(None) is None
    assert GenerateRequest.from_format(None) is None
    assert TopLogProb.from_format(None) is None
    assert LogProb.from_format(None) is None
    assert GenerateResponse.from_format(None) is None

def test_from_format_empty_dict():
    # Tests that providing {} falls back to default values properly
    assert Options.from_format({}).seed == 0
    assert GenerateRequest.from_format({}).model == ""
    assert TopLogProb.from_format({}).token == ""
    assert LogProb.from_format({}).token == ""
    assert GenerateResponse.from_format({}).model == ""

def test_missing_coverage():
    # Cover line with logprobs format in GenerateResponse
    lp = LogProb(token="tok", logprob=0.1, bytes_repr=[], top_logprobs=[])
    resp = GenerateResponse(
        model="m", created_at="now", response="res", done=True, done_reason="stop",
        total_duration=1, load_duration=1, prompt_eval_count=1, prompt_eval_cached_count=1,
        prompt_eval_duration=1, eval_count=1, eval_duration=1, logprobs=[lp]
    )
    d2 = resp.format()
    assert "logprobs" in d2
    assert d2["logprobs"][0]["token"] == "tok"

def test_generate_response_from_json():
    json_str = '{"model": "llama3", "response": "Hello JSON"}'
    resp = GenerateResponse.from_json(json_str)
    assert resp.model == "llama3"
    assert resp.response == "Hello JSON"
    
    # Test empty or invalid json returns None
    assert GenerateResponse.from_json(None) is None
    assert GenerateResponse.from_json("") is None
    assert GenerateResponse.from_json("invalid json string") is None
