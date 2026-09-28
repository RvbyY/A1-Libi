from typing import Literal, Optional, Any, Union
from collections import UserList

from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, Float, JSON
from sqlalchemy.orm import relationship, declarative_base

from src.galerelm.models.constants import SYSTEM_PROMPT

Base = declarative_base()

Role = Literal["system", "user", "assistant", "tool"]
ToolType = Literal["function"]
Format = Literal["json"]
Think = Literal["high", "medium", "low", "max"]


class ToolCallsFunction(Base):
    __tablename__ = "tool_calls_functions"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    tool_call_id: int = Column(Integer, ForeignKey("tool_calls.id"))

    name: str = Column(String, nullable=False)
    description: str = Column(Text, nullable=True)
    arguments: dict = Column(JSON, nullable=True)

    def __init__(self, name: str, description: str, arguments: dict):
        self.name = name
        self.description = description
        self.arguments = arguments

    def format(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "arguments": self.arguments
        }

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            arguments=data.get("arguments", {})
        )


class ToolCalls(Base):
    __tablename__ = "tool_calls"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    message_id: int = Column(Integer, ForeignKey("messages.id"))

    functions = relationship("ToolCallsFunction", backref="tool_call", cascade="all, delete-orphan")

    def __init__(self, functions: list[ToolCallsFunction]):
        self.functions = functions if functions is not None else []

    def format(self) -> dict:
        if isinstance(self.functions, list) and len(self.functions) > 0:
            return {"function": self.functions[0].format()}
        return {"function": getattr(self.functions, "format", lambda: {})()}

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        func_data = data.get("function")
        if func_data and isinstance(func_data, dict):
            functions = [ToolCallsFunction.from_format(func_data)]
        else:
            functions = []
        return cls(functions=functions)


class Message(Base):
    __tablename__ = "messages"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    chat_id: int = Column(Integer, ForeignKey("chats.id"), nullable=True)
    response_id: int = Column(Integer, ForeignKey("chat_responses.id"), nullable=True)

    role: str = Column(String, nullable=False)
    content: str = Column(Text, nullable=False)
    images: list[str] = Column(JSON, nullable=True)
    thinking: Optional[str] = Column(Text, nullable=True)

    tool_calls = relationship("ToolCalls", backref="message", cascade="all, delete-orphan")

    def __init__(self, role: str, content: str, images: list[str] = None, tool_calls: list[ToolCalls] = None,
                 thinking: str = None):
        self.role = role
        self.content = content
        self.images = images if images is not None else []
        self.tool_calls = tool_calls if tool_calls is not None else []
        self.thinking = thinking

    def format(self) -> dict:
        res = {
            "role": self.role,
            "content": self.content,
        }
        if self.images:
            res["images"] = self.images
        if self.tool_calls:
            res["tool_calls"] = [tc.format() for tc in self.tool_calls]
        return res

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        tool_calls_data = data.get("tool_calls", [])
        return cls(
            role=data.get("role", "user"),
            content=data.get("content", ""),
            images=data.get("images", []),
            tool_calls=[ToolCalls.from_format(tc) for tc in tool_calls_data] if tool_calls_data else [],
            thinking=data.get("thinking")
        )


class MessageList(UserList):
    """Collection typée réservée aux objets Message."""

    def format_all(self, separator: str = "\n---\n") -> str:
        return separator.join([m.content for m in self.data])

    def format(self) -> list[dict]:
        return [m.format() for m in self.data]

    @classmethod
    def from_format(cls, data: list[dict]):
        if data is None:
            return cls([])
        return cls([Message.from_format(m) for m in data])


class ToolsFunction(Base):
    __tablename__ = "tools_functions"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    tool_id: int = Column(Integer, ForeignKey("tools.id"))

    name: str = Column(String, nullable=False)
    parameters: dict = Column(JSON, nullable=True)
    description: str = Column(Text, nullable=True)

    def __init__(self, name: str, parameters: dict, description: str):
        self.name = name
        self.parameters = parameters
        self.description = description

    def format(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters
        }

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            parameters=data.get("parameters", {})
        )


class Tools(Base):
    __tablename__ = "tools"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    chat_id: int = Column(Integer, ForeignKey("chats.id"))

    tool_type: str = Column(String, nullable=False)
    tool_function = relationship("ToolsFunction", uselist=False, backref="tool", cascade="all, delete-orphan")

    def __init__(self, tool_type: str, tool_function: ToolsFunction):
        self.tool_type = tool_type
        self.tool_function = tool_function

    def format(self) -> dict:
        return {
            "type": self.tool_type,
            "function": self.tool_function.format() if self.tool_function else None
        }

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(
            tool_type=data.get("type", "function"),
            tool_function=ToolsFunction.from_format(data.get("function", {}))
        )


class ToolsList(UserList):
    """Collection typée réservée aux objets Message."""

    def format_all(self, separator: str = "\n---\n") -> str:
        return ""

    def format(self) -> list[dict]:
        return [t.format() for t in self.data]

    @classmethod
    def from_format(cls, data: list[dict]):
        if data is None:
            return cls([])
        return cls([Tools.from_format(t) for t in data])


class Options(Base):
    __tablename__ = "options"
    id: int = Column(Integer, primary_key=True, autoincrement=True)
    chat_id: int = Column(Integer, ForeignKey("chats.id"))

    seed: int = Column(Integer)
    temperature: float = Column(Float)
    top_k: int = Column(Integer)
    top_p: float = Column(Float)
    min_p: float = Column(Float)
    stop: Union[str, list[str]] = Column(JSON)
    num_ctx: int = Column(Integer)
    num_predict: int = Column(Integer)

    def __init__(self, seed: int, temperature: float, top_k: int, top_p: float, min_p: float,
                 stop: Union[str, list[str]], num_ctx: int, num_predict: int):
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


class Chat(Base):
    __tablename__ = "chats"
    id: int = Column(Integer, primary_key=True, autoincrement=True)

    model: str = Column(String, nullable=False)
    request_format: str = Column(String, nullable=True)
    stream: bool = Column(Boolean, default=True)
    think: Think | bool = Column(String, nullable=True)
    keep_alive: str = Column(String, nullable=True)
    logprobs: bool = Column(Boolean, default=False)
    top_logprobs: int = Column(Integer, nullable=True)

    messages = relationship("Message", collection_class=MessageList, backref="chat", foreign_keys="[Message.chat_id]",
                            cascade="all, delete-orphan")
    tools = relationship("Tools", collection_class=ToolsList, backref="chat", cascade="all, delete-orphan")
    options = relationship("Options", uselist=False, backref="chat", cascade="all, delete-orphan")

    def __init__(self, model: str, messages: MessageList | None, tools: ToolsList | None, request_format: Format, options: Options,
                 stream: bool, think: Union[bool, Think], keep_alive: Union[str, int], logprobs: bool,
                 top_logprobs: int):
        self.model = model
        self.messages = messages if messages is not None else MessageList([])
        self.tools = tools if tools is not None else ToolsList([])
        self.request_format = request_format
        self.options = options
        self.stream = stream
        self.think = think
        self.keep_alive = keep_alive
        self.logprobs = logprobs
        self.top_logprobs = top_logprobs
        self.last_response = None
        self.last_response = None
        self.set_system_prompt()



    def execute_stream(self, api_client):
        """
        Envoie la requête de chat à l'API en streaming, yield chaque token pour un affichage en temps réel,
        et enregistre le résultat final complet dans self.last_response.
        """
        full_response = []
        final_chunk = None

        for chunk in api_client.stream_ndjson("api/chat", json_data=self.format()):
            token = chunk.get("message", {}).get("content", "")
            if token:
                full_response.append(token)
                yield token
            
            if chunk.get("done", False):
                final_chunk = chunk

        if final_chunk:
            if "message" not in final_chunk:
                final_chunk["message"] = {}
            final_chunk["message"]["role"] = "assistant"
            final_chunk["message"]["content"] = "".join(full_response)
            self.last_response = ChatResponse.from_format(final_chunk)
    def format(self) -> dict:
        res = {
            "model": self.model,
            "messages": self.messages.format() if self.messages else [],
            "stream": self.stream,
        }
        if self.tools:
            res["tools"] = self.tools.format()
        if self.request_format:
            res["format"] = self.request_format
        if self.options:
            res["options"] = self.options.format()
        if getattr(self, "think", None) is not None:
            res["think"] = self.think
        if getattr(self, "keep_alive", None) is not None:
            res["keep_alive"] = self.keep_alive
        if getattr(self, "logprobs", None):  # Only send if True
            res["logprobs"] = self.logprobs
        if getattr(self, "top_logprobs", None) is not None:
            res["top_logprobs"] = self.top_logprobs
        return res

    @classmethod
    def from_format(cls, data: dict):
        if data is None:
            return None
        return cls(
            model=data.get("model", ""),
            messages=MessageList.from_format(data.get("messages", [])),
            tools=ToolsList.from_format(data.get("tools", [])),
            request_format=data.get("format", "json"),
            options=Options.from_format(data.get("options")) if data.get("options") else None,
            stream=data.get("stream", True),
            think=data.get("think"),
            keep_alive=data.get("keep_alive"),
            logprobs=data.get("logprobs", False),
            top_logprobs=data.get("top_logprobs")
        )

    # Pourquoi j'utilise add message meme dans user et system prompt ?
    # Car dans l'ajout des prompts il faudra surement ajouter dans la db ou d'autres manipulations
    def add_message(self, content: str, image: list[str], tool_calls: list[ToolCalls] | None, thinking: str = None, role: str = "user"):
        message = Message(role, content, image, tool_calls, thinking)
        self.messages.append(message)

    def set_system_prompt(self):
        message = Message(role="system", content=SYSTEM_PROMPT, images=[], tool_calls=[], thinking=None)
        self.messages.insert(0, message)

    def add_user_prompt(self, content: str, image: list[str], tool_calls: list[ToolCalls], thinking: str):
        self.add_message(content, image, tool_calls, thinking)

    def add_assistant_response(self, content: str, image: list[str], tool_calls: list[ToolCalls]):
        self.add_message(content, image, tool_calls, role="assistant")

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
    response_id: int = Column(Integer, ForeignKey("chat_responses.id"))

    token: str = Column(String)
    logprob: float = Column(Float)
    bytes: list[int] = Column(JSON, nullable=True)

    top_logprobs = relationship("TopLogProb", backref="parent_logprob", cascade="all, delete-orphan")

    def __init__(self, token: str, logprob: float, bytes_repr: list[int], top_logprobs: list[TopLogProb]):
        self.token = token
        self.logprob = logprob
        self.bytes = bytes_repr
        self.top_logprobs = top_logprobs
        self.last_response = None if top_logprobs is not None else []

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


class ChatResponse(Base):
    __tablename__ = "chat_responses"
    id: int = Column(Integer, primary_key=True, autoincrement=True)

    model: str = Column(String)
    created_at: str = Column(String)
    done: bool = Column(Boolean)
    done_reason: str = Column(String)
    total_duration: int = Column(Integer)
    load_duration: int = Column(Integer)
    prompt_eval_count: int = Column(Integer)
    prompt_eval_cached_count: int = Column(Integer)
    prompt_eval_duration: int = Column(Integer)
    eval_count: int = Column(Integer)
    eval_duration: int = Column(Integer)

    message = relationship("Message", uselist=False, backref="response_parent", foreign_keys="[Message.response_id]",
                           cascade="all, delete-orphan")
    logprobs = relationship("LogProb", backref="response", cascade="all, delete-orphan")

    def __init__(
            self,
            model: str,
            created_at: str,
            message: Message,
            done: bool,
            done_reason: str,
            total_duration: int,
            load_duration: int,
            prompt_eval_count: int,
            prompt_eval_cached_count: int,
            prompt_eval_duration: int,
            eval_count: int,
            eval_duration: int,
            logprobs: Optional[list[LogProb]] = None
    ):
        self.model = model
        self.created_at = created_at
        self.message = message
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
            "message": self.message.format() if self.message else None,
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
            message=Message.from_format(data.get("message", {})),
            done=data.get("done", False),
            done_reason=data.get("done_reason", ""),
            total_duration=data.get("total_duration", 0),
            load_duration=data.get("load_duration", 0),
            prompt_eval_count=data.get("prompt_eval_count", 0),
            prompt_eval_cached_count=data.get("prompt_eval_cached_count", 0),
            prompt_eval_duration=data.get("prompt_eval_duration", 0),
            eval_count=data.get("eval_count", 0),
            eval_duration=data.get("eval_duration", 0),
            logprobs=[LogProb.from_format(lp) for lp in logprobs_data] if logprobs_data else None
        )