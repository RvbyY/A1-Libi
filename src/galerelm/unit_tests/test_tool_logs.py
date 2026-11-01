import io

from rich.console import Console

from src.galerelm.models.message import Message, ToolCalls
from src.main import SensAI
from src.repl import THEME, TerminalREPL
from src.tools import SelfTestTool
from src.tools.ITools import ToolContext
from src.tools.registry import ToolExecutor, ToolRegistry


def call(executor: ToolExecutor, name: str, arguments: dict):
    msg = Message(
        role="assistant",
        content="",
        tool_calls=[ToolCalls.from_format({"function": {"name": name, "arguments": arguments}})],
    )
    return executor.execute_calls(msg, ToolContext(user_id="u1"))


def test_executor_reports_each_call_to_observer():
    seen = []
    executor = ToolExecutor(
        ToolRegistry([SelfTestTool()]),
        on_call=lambda name, args, result, ms: seen.append((name, args, result.success, ms)),
    )
    call(executor, "tools_selftest", {"message": "ping"})
    call(executor, "tools_selftest", {"message": "ping", "mode": "fail"})

    assert [(n, a, ok) for n, a, ok, _ in seen] == [
        ("tools_selftest", {"message": "ping"}, True),
        ("tools_selftest", {"message": "ping", "mode": "fail"}, False),
    ]
    assert all(ms >= 0 for *_, ms in seen)


def test_failing_observer_does_not_break_tool_execution():
    def boom(*args):
        raise RuntimeError("display crashed")

    results = call(ToolExecutor(ToolRegistry([SelfTestTool()]), on_call=boom), "tools_selftest", {"message": "ping"})
    assert results[0][1].success is True


def test_format_tool_call_truncates_long_values():
    line = TerminalREPL.format_tool_call("email", {"recipient": "bob@x.io", "content": "a" * 100})
    assert line.startswith("email(recipient='bob@x.io', content='aaaa")
    assert line.endswith("…)")
    assert len(line) < 80


def make_repl():
    app = SensAI(db_url="sqlite:///:memory:")
    app.load_or_create_profile(email="logs@test.com", name="LogsUser")
    output = io.StringIO()
    repl = TerminalREPL(app, console=Console(file=output, theme=THEME, width=200, color_system=None))
    return app, repl, output


def test_repl_registers_itself_as_tool_logger():
    app, repl, _ = make_repl()
    assert app.chat_engine.on_tool_call == repl.log_tool_call


def test_repl_prints_tool_calls_with_status_and_duration():
    app, repl, output = make_repl()
    executor = app.chat_engine.tool_executor

    call(executor, "tools_selftest", {"message": "ping"})
    call(executor, "tools_selftest", {"message": "ping", "mode": "fail"})

    lines = [l for l in output.getvalue().splitlines() if "⚙ tool" in l]
    assert len(lines) == 2
    assert "tools_selftest(message='ping') ✓ Selftest OK: ping (" in lines[0]
    assert "ms)" in lines[0]
    assert "✗ Simulated failure requested (mode=fail)." in lines[1]


def test_repl_keeps_each_tool_call_on_one_line():
    app, repl, output = make_repl()
    call(app.chat_engine.tool_executor, "tools_selftest", {"message": "ligne 1\nligne 2 " + "x" * 150})

    lines = [l for l in output.getvalue().splitlines() if l.strip()]
    assert len(lines) == 1
    assert "\\n" in lines[0]                       # l'argument est affiché échappé
    assert "Selftest OK: ligne 1 ligne 2" in lines[0]  # le message est remis sur une ligne
    assert "…" in lines[0]
