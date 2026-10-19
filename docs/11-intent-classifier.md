# Classification d'Intention (Guardrail)

Le module de classification d'intention (`src/galerelm/intent_classifier.py`) agit comme un filtre de sécurité intelligent (Guardrail) avant que le framework SensAI ne traite la demande de l'utilisateur.

## 🎯 Objectif
L'objectif est d'analyser l'intention réelle derrière le message de l'utilisateur afin de bloquer les requêtes malveillantes, dangereuses ou illégales avant même qu'elles n'atteignent le contexte ou la mémoire du LLM principal.

## ⚙️ Comment ça marche ?

Le système repose sur la classe `IntentGuardrail`. Lorsqu'un utilisateur envoie un message, le Guardrail :
1. Crée une instance de Chat isolée (sans historique ni mémoire).
2. Injecte un prompt système strict demandant au LLM d'agir comme un analyseur JSON.
3. Évalue trois critères spécifiques :
   - `controlled_substance` : Implication de substances réglementées.
   - `criminal_activity` : Activités interdites ou criminelles.
   - `dangerous_activity` : Danger physique ou matériel.
4. Extrait la réponse JSON générée par le modèle et détermine la catégorie globale : `LEGAL`, `ILLEGAL`, ou `AMBIGUOUS`.

## 🏗️ Architecture et Intégration

Le fichier `src/galerelm/intent_classifier.py` s'intègre nativement avec l'écosystème SensAI :
- Il utilise `RapideAPI` pour exécuter la requête via HTTP.
- Il utilise la classe `Chat` (mode streaming interne intercepté) pour générer le JSON.
- Il utilise les paramètres de `src/config.py` (comme le `DEFAULT_MODEL`) avec une `temperature` fixée à `0.0` pour garantir des réponses déterministes.

### Exemple d'utilisation dans le Wrapper

L'intégration dans le flux principal (par exemple dans `SensAIWrapper.chat_stream`) s'effectue ainsi :

```python
from src.galerelm.intent_classifier import IntentGuardrail

# Initialisation du filtre
guardrail = IntentGuardrail(api=self.core.api, model=self.core.model)

# Évaluation de la requête utilisateur
categorie = guardrail.classify(prompt)

if categorie == "ILLEGAL":
    yield "Désolé, je ne peux pas répondre à cette demande pour des raisons de sécurité."
    return
elif categorie == "AMBIGUOUS":
    # Optionnel : demander une clarification ou appliquer une modération plus stricte
    pass

# Si c'est LEGAL ou AMBIGUOUS, le flux normal continue
llm, context = self._setup_chat_environment(session, email, prompt)
# ... suite de la génération ...
```

## 🛡️ Pourquoi cette approche ?
Contrairement à la gestion par "Persona" où le modèle principal reçoit directement la requête malveillante, le Guardrail isole l'évaluation de l'intention. Cela garantit que :
- Les requêtes dangereuses ne polluent pas la mémoire long-terme (RAG).
- Le LLM principal n'est pas exposé à des tentatives de "Jailbreak".
