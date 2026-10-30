"""
SensAI — Interface Terminal Interactive (TerminalREPL).
Encapsule l'affichage Rich et délègue les commandes au CommandRegistry et l'inférence au ChatEngine.
"""
import logging
from typing import TYPE_CHECKING, Optional

from rich.console import Console, Group
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from src.commands.base import CommandResult
from src.commands.registry import CommandRegistry
from src.galerelm.ollama import OllamaError, translate_error

if TYPE_CHECKING:
    from src.main import SensAI

logger = logging.getLogger("sensai.repl")

THEME = Theme({
    "hack":        "green",
    "hack.dim":    "dim green",
    "hack.bright": "bold bright_green",
    "hack.error":  "bold red",
})

LOGO = Text.from_markup(
    "[hack.bright] ▄▀█ ▄█[/]\n"
    "[hack.bright] █▀█  █[/]\n"
    "[hack] █   █ █▄▄ █[/]\n"
    "[hack] █▄▄ █ █▄█ █[/]"
)


class TerminalREPL:
    """
    Interface en ligne de commande (REPL) orientée objet pour SensAI.
    Gère l'affichage Rich, la lecture des entrées utilisateur, le dispatch
    des commandes via CommandRegistry et l'affichage en streaming via SensAI.
    """

    def __init__(self, app: "SensAI", console: Optional[Console] = None):
        self.app = app
        self.console = console or Console(theme=THEME)
        self.app.chat_engine.confirm_tool = self.confirm_tool
        self.app.chat_engine.on_tool_call = self.log_tool_call

    @staticmethod
    def format_tool_call(name: str, arguments: dict, max_value_len: int = 40) -> str:
        """Résume un appel d'outil sur une ligne : nom(arg='valeur', ...), valeurs longues tronquées."""
        parts = []
        for key, value in arguments.items():
            shown = repr(value)
            if len(shown) > max_value_len:
                shown = shown[: max_value_len - 1] + "…"
            parts.append(f"{key}={shown}")
        return f"{name}({', '.join(parts)})"

    def log_tool_call(self, name: str, arguments: dict, result, duration_ms: float) -> None:
        """Affiche dans le terminal chaque outil appelé par l'assistant, son statut et sa durée."""
        status = "[hack.bright]✓[/]" if result.success else "[hack.error]✗[/]"
        # Une ligne par appel, même si le message du tool contient des retours à la ligne
        message = " ".join(str(result.message).split())
        if len(message) > 100:
            message = message[:99] + "…"
        self.console.print(
            f"\n[hack.dim]⚙ tool[/] [hack]{escape(self.format_tool_call(name, arguments))}[/] "
            f"{status} [hack.dim]{escape(message)} ({duration_ms:.0f} ms)[/]"
        )

    def confirm_tool(self, name: str, arguments: dict) -> bool:
        """Demande à l'utilisateur d'autoriser un outil sensible avant son exécution (défaut : non)."""
        details = "\n".join(f"  {key} = {value!r}" for key, value in arguments.items()) or "  (aucun argument)"
        self.console.print(
            f"\n[hack.error]\\[?] L'assistant veut exécuter l'outil « {escape(name)} » :[/]\n"
            f"[hack]{escape(details)}[/]"
        )
        try:
            answer = self.console.input("[hack.bright]Autoriser ? [o/N] [/]").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        approved = answer in ("o", "oui", "y", "yes")
        if not approved:
            self.console.print("[hack.dim]> action annulée.[/]")
        return approved

    def print_welcome(self) -> None:
        """Affiche la bannière d'accueil dans le terminal."""
        self.console.clear()
        infos = Group(
            Text.from_markup("[hack.bright]A1-Libi[/] [hack.dim]v0.1 · uncensored[/]"),
            Text.from_markup(
                f"[hack.dim]> session :[/] [hack]{self.app.profile.name}[/] "
                f"[hack.dim]· {len(self.app.context.messages)} messages chargés[/]"
            ),
            Text.from_markup(f"[hack.dim]> modèle  :[/] [hack]{self.app.model.split('/')[-1]}[/]"),
            Text.from_markup("[hack.dim]> tapez[/] [hack.bright]/help[/] [hack.dim]pour les commandes[/]"),
        )

        grille = Table.grid(padding=(0, 3))
        grille.add_row(LOGO, infos)

        self.console.print(Panel(
            grille,
            title="[hack.bright][ A1-LIBI ][/]",
            title_align="left",
            border_style="hack",
            expand=False,
        ))
        self.console.print()

    def read_input(self) -> str:
        """Affiche le prompt utilisateur et lit la saisie."""
        self.console.print(f"\n[hack]┌──([hack.bright]{self.app.profile.name}㉿a1-libi[/])-\\[[white]~[/]][/]")
        return self.console.input("[hack]└─[hack.bright]❯[/][/] ").strip()

    def handle_command(self, user_prompt: str) -> bool:
        """Délègue l'exécution d'une commande /xxx au CommandRegistry. Renvoie True s'il faut quitter."""
        result = self.app.commands.dispatch(user_prompt, self.app)
        return result == CommandResult.QUIT

    def stream_answer(self, user_prompt: str) -> None:
        """Exécute un tour de chat en streaming via SensAI et affiche les tokens en temps réel."""
        self.console.print("\n[hack.bright]>_[/] ", end="")
        try:
            for token in self.app.stream_chat(user_prompt):
                self.console.print(token, end="", style="hack", markup=False)
            self.console.print()
        except Exception as exc:
            error = translate_error(exc, host=self.app.api.base_url, model=self.app.model)
            if not isinstance(error, OllamaError):
                logger.exception("Erreur inattendue pendant la génération")
            self.print_error(error)

    def print_error(self, error: Exception) -> None:
        """Affiche une erreur (et sa suggestion de résolution pour les OllamaError)."""
        if isinstance(error, OllamaError):
            self.console.print(f"\n[hack.error]\\[!] {escape(error.message)}[/]")
            if error.hint:
                self.console.print(f"[hack.dim]    → {escape(error.hint)}[/]")
        else:
            self.console.print(f"\n[hack.error]\\[!] Erreur inattendue : {escape(str(error))}[/]")

    def run(self) -> None:
        """Lance la boucle principale d'interaction dans le terminal."""
        if not self.app.profile or not self.app.context:
            raise RuntimeError("Aucun profil chargé. Appelez load_or_create_profile() d'abord.")

        self.print_welcome()
        logger.info("Démarrage de la boucle interactive de discussion.")

        while True:
            try:
                user_prompt = self.read_input()
            except (EOFError, KeyboardInterrupt):
                self.console.print("\n[hack.dim]> session terminée.[/] [hack.bright]Au revoir ![/]\n")
                break

            if not user_prompt:
                continue

            if CommandRegistry.is_command(user_prompt):
                if self.handle_command(user_prompt):
                    break
                continue

            self.stream_answer(user_prompt)


def repl(app: "SensAI") -> None:
    """Point d'entrée de compatibilité qui instancie et lance TerminalREPL."""
    TerminalREPL(app).run()