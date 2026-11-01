"""
Module output_guardrail.py
Filtre de sortie : détecte les données personnelles dans les réponses du modèle,
puis les anonymise ou refuse la réponse, avant l'affichage et avant l'enregistrement en base.

Documentation : docs/user_stories/EV2-guardrails.md.
"""
import logging
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable, Iterator, Optional

logger = logging.getLogger("galerelm.output_guardrail")

OUTPUT_MODES = ("off", "anonymize", "refuse")


def _luhn_ok(digits: str) -> bool:
    """Contrôle de Luhn : écarte les longues suites de chiffres qui ne sont pas des numéros de carte."""
    total, parity = 0, len(digits) % 2
    for index, char in enumerate(digits):
        value = int(char)
        if index % 2 == parity:
            value *= 2
            if value > 9:
                value -= 9
        total += value
    return total % 10 == 0


@dataclass(frozen=True)
class PiiRule:
    category: str
    label: str
    pattern: re.Pattern
    check: Optional[Callable[[str], bool]] = None


# L'ordre compte : l'IBAN et la carte passent avant le téléphone, qui reconnaîtrait une partie de leurs chiffres.
PII_RULES: tuple[PiiRule, ...] = (
    PiiRule("email", "[EMAIL]", re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")),
    PiiRule("iban", "[IBAN]", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,4})?\b")),
    PiiRule("card", "[CARTE]", re.compile(r"\b\d(?:[ -]?\d){12,18}\b"),
            check=lambda text: _luhn_ok(re.sub(r"\D", "", text))),
    PiiRule("ssn", "[NUMERO_SECU]", re.compile(r"\b[12] ?\d{2} ?(?:0[1-9]|1[0-2]) ?\d{2} ?\d{3} ?\d{3}(?: ?\d{2})?\b")),
    PiiRule("phone", "[TELEPHONE]", re.compile(r"(?:\+33 ?|\b0)[1-9](?:[ .-]?\d{2}){4}\b")),
)
PII_CATEGORIES = tuple(rule.category for rule in PII_RULES)

REFUSAL_MESSAGE = (
    "Je ne peux pas afficher cette réponse : elle contient des données personnelles "
    "({categories}). Reformulez la demande sans ces informations."
)

# Fin de phrase : ponctuation suivie d'un espace, ou retour à la ligne. Un email ou un IBAN n'en contient pas.
_SENTENCE_END = re.compile(r"[.!?;:]\s|\n")


@dataclass
class OutputDecision:
    text: str
    found: dict[str, int] = field(default_factory=dict)
    refused: bool = False


class OutputGuardrail:
    """
    mode "anonymize" : chaque donnée détectée est remplacée par une étiquette ([EMAIL], [TELEPHONE]...).
    mode "refuse"    : toute la réponse est remplacée par un message de refus.
    """

    def __init__(self, mode: str = "anonymize", categories: Optional[Iterable[str]] = None):
        if mode not in OUTPUT_MODES or mode == "off":
            raise ValueError(f"Mode de filtre de sortie invalide : {mode!r} (attendu : anonymize, refuse).")
        self.mode = mode
        selected = set(categories) if categories is not None else set(PII_CATEGORIES)
        unknown = selected - set(PII_CATEGORIES)
        if unknown:
            raise ValueError(f"Catégories inconnues : {', '.join(sorted(unknown))} (connues : {', '.join(PII_CATEGORIES)}).")
        self.rules = [rule for rule in PII_RULES if rule.category in selected]

    def anonymize(self, text: str) -> OutputDecision:
        found: dict[str, int] = {}

        for rule in self.rules:
            def replace(match: re.Match, rule=rule) -> str:
                if rule.check is not None and not rule.check(match.group(0)):
                    return match.group(0)
                found[rule.category] = found.get(rule.category, 0) + 1
                return rule.label
            text = rule.pattern.sub(replace, text)
        return OutputDecision(text=text, found=found)

    def apply(self, text: str) -> OutputDecision:
        """Filtre une réponse complète selon le mode."""
        decision = self.anonymize(text)
        if decision.found:
            logger.info(f"[OutputGuardrail] Données personnelles détectées : {decision.found}")
        if decision.found and self.mode == "refuse":
            categories = ", ".join(sorted(decision.found))
            return OutputDecision(text=REFUSAL_MESSAGE.format(categories=categories), found=decision.found, refused=True)
        return decision

    def filter_stream(self, tokens: Iterable[str]) -> Iterator[str]:
        """
        Filtre un flux de tokens.
        - anonymize : le texte est gardé jusqu'à la fin de chaque phrase, puis filtré et envoyé.
          Une donnée découpée en plusieurs tokens est donc reconnue en entier.
        - refuse : rien n'est envoyé avant la fin, puisque toute la réponse peut être remplacée.
        """
        if self.mode == "refuse":
            yield self.apply("".join(tokens)).text
            return

        buffer = ""
        for token in tokens:
            buffer += token
            last_end = None
            for match in _SENTENCE_END.finditer(buffer):
                last_end = match.end()
            if last_end is not None:
                ready, buffer = buffer[:last_end], buffer[last_end:]
                yield self.anonymize(ready).text
        if buffer:
            yield self.anonymize(buffer).text
