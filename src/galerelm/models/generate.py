from typing import Literal, Optional, Any, Union
from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship, declarative_base

Base = declarative_base()

Format = Literal["json"]
Think = Literal["high", "medium", "low", "max"]


class Options(Base):
    __tablename__ = "options"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    generate_id: int = Column(Integer, ForeignKey("generate_requests.id"), nullable=True)

    seed: int = Column(Integer)
    temperature: float = Column(Float)
    top_k: int = Column(Integer)
    top_p: float = Column(Float)
    min_p: float = Column(Float)
    stop: Union[str, list[str]] = Column(JSON)
    num_ctx: int = Column(Integer)
    num_predict: int = Column(Integer)

    def __init__(self, seed: int, temperature: float, top_k: int, top_p: float, min_p: float, stop: Union[str, list[str]], num_ctx: int, num_predict: int):
        self.seed = seed
        self.temperature = temperature
        self.top_k = top_k
        self.top_p = top_p
        self.min_p = min_p
        self.stop = stop
        self.num_ctx = num_ctx
        self.num_predict = num_predict

    def format(self) -> dict:
        return {
            "seed": self.seed,
            "temperature": self.temperature,
            "top_k": self.top_k,
            "top_p": self.top_p,
            "min_p": self.min_p,
            "stop": self.stop,
            "num_ctx": self.num_ctx,
            "num_predict": self.num_predict
        }

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(
            seed=data.get("seed", 0),
            temperature=data.get("temperature", 0.8),
            top_k=data.get("top_k", 40),
            top_p=data.get("top_p", 0.9),
            min_p=data.get("min_p", 0.0),
            stop=data.get("stop", ""),
            num_ctx=data.get("num_ctx", 2048),
            num_predict=data.get("num_predict", 128)
        )


class GenerateRequest(Base):
    __tablename__ = "generate_requests"
    id: int = Column(Integer, primary_key=True, autoincrement=True)

    model: str = Column(String, nullable=False)
    prompt: str = Column(Text, nullable=False)
    suffix: Optional[str] = Column(Text, nullable=True)
    images: list[str] = Column(JSON, nullable=True)
    request_format: Optional[str] = Column(String, nullable=True)
    system: Optional[str] = Column(Text, nullable=True)
    stream: bool = Column(Boolean, default=True)
    think: Optional[str] = Column(String, nullable=True)
    raw: bool = Column(Boolean, default=False)
    keep_alive: Optional[str] = Column(String, nullable=True)
    logprobs: bool = Column(Boolean, default=False)
    top_logprobs: Optional[int] = Column(Integer, nullable=True)

    options = relationship("Options", uselist=False, backref="generate_request", cascade="all, delete-orphan")

    def __init__(
        self, 
        model: str = None, 
        prompt: str = None, 
        suffix: str = None, 
        images: list[str] = None, 
        request_format: Format = None, 
        system: str = None, 
        stream: bool = True, 
        think: Union[bool, Think] = None, 
        raw: bool = False, 
        keep_alive: Union[str, int] = None, 
        logprobs: bool = False, 
        top_logprobs: int = None, 
        options: Options = None
    ):
        self.model = model
        self.prompt = prompt
        self.suffix = suffix
        self.images = images if images is not None else []
        self.request_format = request_format
        self.system = system
        self.stream = stream
        self.think = think
        self.raw = raw
        self.keep_alive = keep_alive
        self.logprobs = logprobs
        self.top_logprobs = top_logprobs
        self.options = options

    def format(self) -> dict:
        res = {
            "model": self.model,
            "prompt": self.prompt,
            "stream": self.stream,
            "raw": self.raw,
        }
        if self.suffix is not None:
            res["suffix"] = self.suffix
        if self.images is not None:
            res["images"] = self.images
        if self.request_format is not None:
            res["format"] = self.request_format
        if self.system is not None:
            res["system"] = self.system
        if self.think is not None:
            res["think"] = self.think
        if self.keep_alive is not None:
            res["keep_alive"] = self.keep_alive
        if self.options is not None:
            res["options"] = self.options.format()
        if self.logprobs is not None:
            res["logprobs"] = self.logprobs
        if self.top_logprobs is not None:
            res["top_logprobs"] = self.top_logprobs
        return res

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(
            model=data.get("model", ""),
            prompt=data.get("prompt", ""),
            suffix=data.get("suffix"),
            images=data.get("images", []),
            request_format=data.get("format"),
            system=data.get("system"),
            stream=data.get("stream", True),
            think=data.get("think"),
            raw=data.get("raw", False),
            keep_alive=data.get("keep_alive"),
            logprobs=data.get("logprobs", False),
            top_logprobs=data.get("top_logprobs"),
            options=Options.from_format(data.get("options")) if data.get("options") else None
        )


class TopLogProb(Base):
    __tablename__ = "top_logprobs"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    logprob_id: int = Column(Integer, ForeignKey("logprobs.id"))

    token: str = Column(String)
    logprob: float = Column(Float)
    bytes: list[int] = Column(JSON, nullable=True)

    def __init__(self, token: str, logprob: float, bytes_repr: list[int]):
        self.token = token
        self.logprob = logprob
        self.bytes = bytes_repr

    def format(self) -> dict:
        return {
            "token": self.token,
            "logprob": self.logprob,
            "bytes": self.bytes
        }

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(
            token=data.get("token", ""),
            logprob=data.get("logprob", 0.0),
            bytes_repr=data.get("bytes", [])
        )


class LogProb(Base):
    __tablename__ = "logprobs"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    response_id: int = Column(Integer, ForeignKey("generate_responses.id"))

    token: str = Column(String)
    logprob: float = Column(Float)
    bytes: list[int] = Column(JSON, nullable=True)
    
    top_logprobs = relationship("TopLogProb", backref="parent_logprob", cascade="all, delete-orphan")

    def __init__(self, token: str, logprob: float, bytes_repr: list[int], top_logprobs: list[TopLogProb]):
        self.token = token
        self.logprob = logprob
        self.bytes = bytes_repr
        self.top_logprobs = top_logprobs if top_logprobs is not None else []

    def format(self) -> dict:
        return {
            "token": self.token,
            "logprob": self.logprob,
            "bytes": self.bytes,
            "top_logprobs": [t.format() for t in self.top_logprobs] if self.top_logprobs else []
        }

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(
            token=data.get("token", ""),
            logprob=data.get("logprob", 0.0),
            bytes_repr=data.get("bytes", []),
            top_logprobs=[TopLogProb.from_format(t) for t in data.get("top_logprobs", [])]
        )


class GenerateResponse(Base):
    __tablename__ = "generate_responses"
    id: int = Column(Integer, primary_key=True, autoincrement=True)

    model: str = Column(String)
    created_at: str = Column(String)
    response: str = Column(Text)
    thinking: Optional[str] = Column(Text, nullable=True)
    done: bool = Column(Boolean)
    done_reason: str = Column(String)
    total_duration: int = Column(Integer)
    load_duration: int = Column(Integer)
    prompt_eval_count: int = Column(Integer)
    prompt_eval_cached_count: int = Column(Integer)
    prompt_eval_duration: int = Column(Integer)
    eval_count: int = Column(Integer)
    eval_duration: int = Column(Integer)

    logprobs = relationship("LogProb", backref="generate_response", cascade="all, delete-orphan")

    def __init__(
        self,
        model: str = None,
        created_at: str = None,
        response: str = None,
        done: bool,
        done_reason: str = None,
        total_duration: int,
        load_duration: int,
        prompt_eval_count: int,
        prompt_eval_cached_count: int,
        prompt_eval_duration: int,
        eval_count: int,
        eval_duration: int,
        thinking: str = None,
        logprobs: Optional[list[LogProb]] = None
    ):
        self.model = model
        self.created_at = created_at
        self.response = response
        self.thinking = thinking
        self.done = done
        self.done_reason = done_reason
        self.total_duration = total_duration
        self.load_duration = load_duration
        self.prompt_eval_count = prompt_eval_count
        self.prompt_eval_cached_count = prompt_eval_cached_count
        self.prompt_eval_duration = prompt_eval_duration
        self.eval_count = eval_count
        self.eval_duration = eval_duration
        self.logprobs = logprobs if logprobs is not None else []

    def format(self) -> dict:
        res = {
            "model": self.model,
            "created_at": self.created_at,
            "response": self.response,
            "done": self.done,
            "done_reason": self.done_reason,
            "total_duration": self.total_duration,
            "load_duration": self.load_duration,
            "prompt_eval_count": self.prompt_eval_count,
            "prompt_eval_cached_count": self.prompt_eval_cached_count,
            "prompt_eval_duration": self.prompt_eval_duration,
            "eval_count": self.eval_count,
            "eval_duration": self.eval_duration,
        }
        if self.thinking is not None:
            res["thinking"] = self.thinking
        if self.logprobs:
            res["logprobs"] = [lp.format() for lp in self.logprobs]
        return res

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        logprobs_data = data.get("logprobs")
        return cls(
            model=data.get("model", ""),
            created_at=data.get("created_at", ""),
            response=data.get("response", ""),
            thinking=data.get("thinking"),
            done=data.get("done", False),
            done_reason=data.get("done_reason", ""),
            total_duration=data.get("total_duration", 0),
            load_duration=data.get("load_duration", 0),
            prompt_eval_count=data.get("prompt_eval_count", 0),
            prompt_eval_cached_count=data.get("prompt_eval_cached_count", 0),
            prompt_eval_duration=data.get("prompt_eval_duration", 0),
            eval_count=data.get("eval_count", 0),
            eval_duration=data.get("eval_duration", 0),
            logprobs=[LogProb.from_format(lp) for lp in logprobs_data] if logprobs_data else []
        )

    @classmethod
    def from_json(cls, json_str: str):
        if not json_str:
            return None
        import json
        try:
            data = json.loads(json_str)
            return cls.from_format(data)
        except json.JSONDecodeError:
            return None
