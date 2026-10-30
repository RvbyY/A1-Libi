"""
Module selftest_tool.py
Outil de diagnostic sans effet de bord : renvoie le message reçu pour vérifier de bout en bout
que le LLM sait appeler un outil (schéma, validation, exécution, réinjection du résultat, logs).
"""
import logging
from datetime import datetime, timezone

from ..ITools import ToolContext, ToolResult, ToolsInterface

logger = logging.getLogger("sensai.tools.selftest")

MODES = ("echo", "fail")
MAX_MESSAGE_LENGTH = 200
MAX_REPEAT = 5


class SelfTest(ToolsInterface):
    """Outil de test : renvoie (echo) ou fait échouer volontairement (fail) l'appel."""

    @property
    def name(self) -> str:
        return "tools_selftest"

    @property
    def description(self) -> str:
        return (
            "Diagnostic tool that echoes a message back to check that tool calling works. "
            "Use it only when the user explicitly asks to test the tools. No side effect."
        )

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": f"Text to echo back (1 to {MAX_MESSAGE_LENGTH} characters).",
                },
                "mode": {
                    "type": "string",
                    "enum": list(MODES),
                    "description": "echo returns the message, fail simulates a tool error. Default: echo.",
                },
                "repeat": {
                    "type": "integer",
                    "description": f"How many times to repeat the message (1 to {MAX_REPEAT}). Default: 1.",
                },
            },
            "required": ["message"],
        }

    def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        try:
            message, mode, repeat = self._validate(arguments)
        except ValueError as exc:
            return ToolResult(False, str(exc))

        if mode == "fail":
            logger.debug("[SelfTest] Échec simulé demandé.")
            return ToolResult(False, "Simulated failure requested (mode=fail).", {"mode": "fail"})

        echo = " ".join([message] * repeat)
        logger.debug(f"[SelfTest] Echo x{repeat} pour l'utilisateur {context.user_id}.")
        return ToolResult(
            True,
            f"Selftest OK: {echo}",
            {
                "echo": echo,
                "repeat": repeat,
                "user_id": context.user_id,
                "checked_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    @staticmethod
    def _validate(arguments: dict) -> tuple[str, str, int]:
        """Valide les arguments envoyés par le LLM. Lève ValueError avec un message lisible."""
        if not isinstance(arguments, dict):
            raise ValueError("arguments must be an object.")

        message = arguments.get("message")
        if not isinstance(message, str) or not message.strip():
            raise ValueError("message is required.")
        message = message.strip()
        if len(message) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"message must be at most {MAX_MESSAGE_LENGTH} characters.")

        mode = arguments.get("mode", "echo")
        if mode not in MODES:
            raise ValueError(f"mode must be one of: {', '.join(MODES)}.")

        repeat = arguments.get("repeat", 1)
        # bool est un sous-type de int : on l'exclut explicitement
        if isinstance(repeat, bool) or not isinstance(repeat, int) or not 1 <= repeat <= MAX_REPEAT:
            raise ValueError(f"repeat must be an integer between 1 and {MAX_REPEAT}.")

        return message, mode, repeat


SelfTestTool = SelfTest
