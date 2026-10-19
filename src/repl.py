from src.config import config
"""
SensAI — Point d'entrée principal du framework LLM.
"""
import os
from galerelm.models.chat import Chat, Message
import logging
from src.galerelm.models import Chat, Message, Context
from rich.console import Console, Group
from rich.text import Text
from rich.table import Table
from rich.panel import Panel
from rich.theme import Theme

THEME = Theme({
    "hack":        "green",
    "hack.dim":    "dim green",
    "hack.bright": "bold bright_green",
    "hack.error":  "bold red",
})

console = Console(theme=THEME)
logger = logging.getLogger("sensai")

LOGO = Text.from_markup(
    "[hack.bright] ▄▀█ ▄█[/]\n"
    "[hack.bright] █▀█  █[/]\n"
    "[hack] █   █ █▄▄ █[/]\n"
    "[hack] █▄▄ █ █▄█ █[/]"
)

# ── Boucle interactive (REPL) ────────────────────────────────────

def repl(self):
    """Lance une boucle interactive de chat dans le terminal."""
    if not self.profile or not self.context:
        raise RuntimeError("Aucun profil chargé. Appelez load_or_create_profile() d'abord.")

    print_welcome(self)
    logger.info("Démarrage de la boucle interactive de discussion.")

    while True:
        user_prompt = read_input(self)

        if not user_prompt:
            continue

        if user_prompt.startswith("/"):
            if handle_command(self, user_prompt):
                break
            continue

        llm = stream_answer(self, user_prompt)
        if llm:
            save_answer(self, llm)

def read_input(self) -> str:
    """Affiche un prompt façon Kali Linux et lit la saisie."""
    console.print(f"\n[hack]┌──([hack.bright]{self.profile.name}㉿a1-libi[/])-\\[[white]~[/]][/]")
    return console.input("[hack]└─[hack.bright]❯[/][/] ").strip()

def print_welcome(self):
    """Affiche le message d'accueil."""
    console.clear()
    infos = Group(
        Text.from_markup("[hack.bright]A1-Libi[/] [hack.dim]v0.1 · uncensored[/]"),
        Text.from_markup(f"[hack.dim]> session :[/] [hack]{self.profile.name}[/] [hack.dim]· {len(self.context.messages)} messages chargés[/]"),
        Text.from_markup(f"[hack.dim]> modèle  :[/] [hack]{self.model.split('/')[-1]}[/]"),
        Text.from_markup("[hack.dim]> tapez[/] [hack.bright]/help[/] [hack.dim]pour les commandes[/]"),
    )

    grille = Table.grid(padding=(0, 3))
    grille.add_row(LOGO, infos)

    console.print(Panel(
        grille,
        title="[hack.bright][ A1-LIBI ][/]",
        title_align="left",
        border_style="hack",
        expand=False,
    ))
    console.print()

def handle_command(self, user_prompt: str) -> bool:
    """Exécute une commande /xxx. Renvoie True s'il faut quitter."""
    parts = user_prompt.split(maxsplit=1)
    command = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    if command not in _commands:
        console.print(f"[hack.error]\\[!] Commande inconnue : {command}.[/] [hack.dim]Tapez /help pour la liste.[/]")
        return False
    return bool(_commands[command](self, args))

def stream_answer(self, user_prompt: str):
    """Envoie le message à l'IA et affiche la réponse en streaming. Renvoie le Chat, ou None en cas d'erreur."""
    self.context.add(Message(role="user", content=user_prompt), api_client=self.api)
    self.session.commit()

    built_prompt = self.build_prompt(user_prompt)
    llm = Chat(
        model=self.model,
        api=self.api,
        messages=self.context.get_messages_copy(),
        system_prompt=built_prompt,
    )

    console.print("\n[hack.bright]>_[/] ", end="")

    try:
        for token in llm.execute_stream():
            console.print(token, end="", style="hack", markup=False)
        console.print()
    except Exception as e:
        console.print(f"\n[hack.error]\\[!] Erreur de connexion : {e}[/]")
        return None
    return llm

def save_answer(self, llm):
    """Enregistre la réponse de l'IA dans le contexte."""
    if llm.last_response and llm.last_response.message:
        assistant_msg = llm.last_response.message
        self.context.add(Message(
            role="assistant",
            content=assistant_msg.content,
            images=assistant_msg.images,
        ), api_client=self.api)
        self.session.commit()
    else:
        print("[!] Erreur: Aucune réponse retournée par le modèle.")

# ── Commandes REPL ───────────────────────────────────────────────

def _cmd_help(self, args: str):
    """Affiche les commandes."""
    # Regroupe les alias d'une même commande (/quit, /exit, /q) sur une seule ligne
    aliases = {}
    for cmd, handler in _commands.items():
        aliases.setdefault(handler, []).append(cmd)

    table = Table.grid(padding=(0, 3))
    for handler, cmds in aliases.items():
        table.add_row(
            Text(", ".join(cmds), style="hack.bright"),
            Text(handler.__doc__ or "", style="hack.dim"),
        )

    console.print()
    console.print(Panel(
        table,
        title="[hack.bright]\\[ COMMANDES ][/]",
        title_align="left",
        border_style="hack",
        expand=False,
        padding=(1, 2),
    ))

def _cmd_quit(self, args: str):
    """Quitter le programme."""
    logger.info("Fermeture du programme demandée par l'utilisateur.")
    console.print("\n[hack.dim]> session terminée.[/] [hack.bright]Au revoir ![/]\n")
    return True

def _cmd_messages(self, args: str):
    """Lister les messages du contexte."""
    messages = self.context.messages
    if not messages:
        print("\n[i] Aucun message dans le contexte actuel.\n")
        return

    print(f"\n── Messages en contexte ({len(messages)}/{self.context.context_limit}) ──")
    for i, m in enumerate(messages):
        role_icon = {"system": "⚙️", "user": "👤", "assistant": "🤖", "tool": "🔧"}.get(m.role, "❓")
        content_preview = m.content[:80].replace("\n", "↵")
        if len(m.content) > 80:
            content_preview += "..."
        print(f"  {i+1}. {role_icon} [{m.role}] {content_preview}")
    print()

def _cmd_memories(self, args: str):
    """Lister les mémoires long terme."""
    if not self.profile.deep_context or not self.profile.deep_context.memories:
        print("\n[i] Aucune mémoire long terme enregistrée.\n")
        return

    memories = self.profile.deep_context.memories
    print(f"\n── Mémoires Long Terme ({len(memories)} entrées) ──")
    for i, mem in enumerate(memories):
        role_icon = {"user": "👤", "assistant": "🤖"}.get(mem.role, "❓")
        content_preview = mem.content[:80].replace("\n", "↵")
        if len(mem.content) > 80:
            content_preview += "..."
        print(f"  {i+1}. {role_icon} [{mem.role}] {content_preview}")
    print()

def _cmd_profile(self, args: str):
    """Afficher le profil courant."""
    p = self.profile
    print(f"\n── Profil ──")
    print(f"  ID           : {p.id}")
    print(f"  Nom          : {p.name}")
    print(f"  Email        : {p.email}")
    print(f"  Instructions : {p.instructions[:100]}{'...' if len(p.instructions) > 100 else ''}")
    print()

def _cmd_context(self, args: str):
    """Afficher les stats du contexte."""
    ctx = self.context
    mem_count = len(self.profile.deep_context.memories) if self.profile.deep_context else 0
    print(f"\n── Contexte ──")
    print(f"  ID              : {ctx.id}")
    print(f"  Profile ID      : {ctx.profile_id}")
    print(f"  Messages        : {len(ctx.messages)}/{ctx.context_limit}")
    print(f"  Mémoires LT     : {mem_count}")
    print(f"  Modèle          : {self.model}")
    print()

def _cmd_payload(self, args: str):
    """Afficher le payload JSON brut."""
    import json
    llm = Chat(
        model=self.model,
        api=self.api,
        messages=self.context.get_messages_copy(),
        system_prompt=self.profile.instructions,
    )
    payload = llm.format()
    print(f"\n── Payload JSON ──")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    print()

def _cmd_clear(self, args: str):
    """Vider le contexte courant."""
    from src.galerelm.models.message import MessageList
    count = len(self.context.messages)
    self.context.messages = MessageList([])
    self.session.commit()
    print(f"\n[✓] {count} messages supprimés du contexte.\n")

def _cmd_new(self, args: str):
    """Créer un nouveau contexte vierge."""
    self.context = Context(profile_id=self.profile.id, context_limit=config.CONTEXT_LIMIT)
    self.session.add(self.context)
    self.session.commit()
    print("\n[✓] Nouveau contexte créé. Historique vierge.\n")

def _cmd_recall(self, args: str):
    """Rechercher dans la mémoire long terme."""
    if not args:
        print("\n[!] Usage : /recall <votre requête>\n")
        return

    if not self.profile.deep_context or not self.profile.deep_context.memories:
        print("\n[i] Aucune mémoire long terme enregistrée.\n")
        return

    try:
        results = self.profile.deep_context.search(args, self.api, top_k=5)
    except Exception as e:
        print(f"\n[!] Erreur lors de la recherche : {e}\n")
        return

    if not results:
        print("\n[i] Aucun résultat pertinent trouvé.\n")
        return

    print(f"\n── Résultats RAG pour \"{args}\" ({len(results)} trouvés) ──")
    for i, (score, mem) in enumerate(results):
        role_icon = {"user": "👤", "assistant": "🤖"}.get(mem.role, "❓")
        content_preview = mem.content[:100].replace("\n", "↵")
        if len(mem.content) > 100:
            content_preview += "..."
        print(f"  {i+1}. {role_icon} [{mem.role}] (score: {score:.4f}) {content_preview}")
    print()

# ── Registre des commandes ───────────────────────────────────────

_commands = {
    "/help":     _cmd_help,
    "/quit":     _cmd_quit,
    "/exit":     _cmd_quit,
    "/q":        _cmd_quit,
    "/messages": _cmd_messages,
    "/memories": _cmd_memories,
    "/profile":  _cmd_profile,
    "/context":  _cmd_context,
    "/payload":  _cmd_payload,
    "/clear":    _cmd_clear,
    "/new":      _cmd_new,
    "/recall":   _cmd_recall,
}