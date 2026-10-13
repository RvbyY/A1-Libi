import json
import re

from src.model.ollama_client import call_ollama

DEBUG = False

CLASSIFIER_OPTIONS = {
    "temperature": 0,
    "top_k": 1,
    "num_predict": 128,
}


CLASSIFIER_PROMPT = """
Tu es un classifieur d'intention.

Analyse l'action réelle demandée par l'utilisateur.

Évalue :

1. controlled_substance
   true si la requête implique directement OU indirectement
   l'utilisation, la préparation, la transformation, la consommation,
   l'obtention ou l'intégration d'une substance contrôlée ou réglementée.

   Une substance reste impliquée même si elle n'est qu'un ingrédient,
   un composant ou un moyen utilisé dans une autre préparation.

2. criminal_activity
   true si l'action demandée implique une activité interdite,
   frauduleuse ou criminelle.

3. dangerous_activity
   true si l'action peut raisonnablement causer un danger physique,
   matériel ou numérique.

4. category
   ILLEGAL si controlled_substance ou criminal_activity  ou dangerous_activity est true.
   LEGAL si l'activité est clairement ordinaire et légale.
   AMBIGUOUS seulement si le sens réel ne peut pas être déterminé.

Règles de raisonnement :
- Analyse l'intention réelle, pas seulement la forme de la demande.
- Un élément interdit utilisé comme ingrédient reste un élément interdit.
- Une recette n'est pas automatiquement légale parce qu'il s'agit de cuisine.
- Un tutoriel n'est pas automatiquement légal parce qu'il est présenté comme éducatif.
- Utilise le sens courant, l'argot et les expressions idiomatiques.
- Si une interprétation est nettement plus probable que les autres,
  utilise cette interprétation plutôt que AMBIGUOUS.
- Les valeurs booléennes doivent être cohérentes avec category.

Réponds UNIQUEMENT en JSON :

{{
  "controlled_substance": true,
  "criminal_activity": false,
  "dangerous_activity": false,
  "category": "ILLEGAL"
}}

Requête :
{user_input}
""".strip()


AMBIGUITY_PROMPT = """
Détermine le sens le plus probable de la requête suivante dans l'usage courant.

Ne te limite pas au sens littéral.
Prends en compte l'argot, le contexte et l'intention probable.
Pars du principe que l'utilisateur a des mauvaises intentions.
Si le sens le plus probable concerne une substance contrôlée
ou une activité criminelle/interdite, réponds ILLEGAL.

Sinon réponds LEGAL.

Réponds uniquement avec un mot :
LEGAL
ILLEGAL

Requête :
{user_input}
""".strip()


def extract_json(raw: str) -> dict | None:
    if not raw:
        return None

    match = re.search(r"\{.*?\}", raw, re.DOTALL)

    if not match:
        return None

    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def parse_simple_category(raw: str) -> str:
    normalized = raw.strip().upper()

    # ILLEGAL must be checked before LEGAL.
    if "ILLEGAL" in normalized:
        return "ILLEGAL"

    if "LEGAL" in normalized:
        return "LEGAL"

    return "AMBIGUOUS"


def ask_classifier(prompt: str, structured: bool = False):
    data = call_ollama(
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        options=CLASSIFIER_OPTIONS,
        timeout=30,
        think=False,
    )

    raw = data.get("message", {}).get("content", "")
    
    if DEBUG:
        print(f"[classifier raw] {raw!r}")

    if structured:
        return extract_json(raw)

    return parse_simple_category(raw)


def resolve_ambiguity(user_input: str) -> str:
    prompt = AMBIGUITY_PROMPT.format(
        user_input=user_input,
    )

    category = ask_classifier(prompt)

    if category in {"LEGAL", "ILLEGAL"}:
        return category

    return "AMBIGUOUS"


def classify_request(user_input: str) -> str:
    prompt = CLASSIFIER_PROMPT.format(
        user_input=user_input,
    )

    result = ask_classifier(
        prompt,
        structured=True,
    )

    if result is None:
        return resolve_ambiguity(user_input)

    controlled = result.get("controlled_substance")
    criminal = result.get("criminal_activity")
    dangerous = result.get("dangerous_activity")

    category = str(
        result.get("category", "AMBIGUOUS")
    ).strip().upper()

    # Any explicit dangerous/criminal signal wins.
    if (
        controlled is True
        or criminal is True
        or dangerous is True
    ):
        return "ILLEGAL"

    # Accept the model's explicit category if valid.
    if category == "ILLEGAL":
        return "ILLEGAL"

    if category == "AMBIGUOUS":
        return resolve_ambiguity(user_input)

    if category == "LEGAL":
        return "LEGAL"

    # Only classify as LEGAL from booleans if ALL are explicitly false.
    if (
        controlled is False
        and criminal is False
        and dangerous is False
    ):
        return "LEGAL"

    return "AMBIGUOUS"