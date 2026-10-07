# Documentation : Chat (`chat.py`)

## Description Générale
La classe `Chat` est un objet métier éphémère. Elle n'est **pas** un modèle ORM (Object-Relational Mapping) stocké en base de données. Son rôle principal est de :
1. Construire le payload JSON formaté pour l'API LLM (Ollama).
2. Gérer le flux de requêtes et de réponses en temps réel (streaming).
3. Stocker la réponse finale sous forme d'objet `ChatResponse`.

## Attributs Principaux
- `model` (str) : Le nom du modèle LLM à interroger.
- `api` (RapideAPI) : Le client HTTP pour communiquer avec l'API.
- `messages` (MessageList) : La liste des messages (historique) à envoyer.
- `system_prompt` (str) : Les instructions système, toujours placées en première position.

## Méthodes Clés
### `format() -> dict`
Construit le dictionnaire JSON final qui sera envoyé à l'API via POST. Gère l'inclusion conditionnelle des outils, des options, et du format de réponse.

### `execute_stream(api_client=None)`
Envoie la requête de chat à l'API en streaming (`stream_ndjson`).
- Utilise `yield` pour retourner chaque token dès sa réception (permettant un affichage en temps réel dans le terminal).
- Une fois le flux terminé (token contenant `done: True`), génère un objet `ChatResponse` complet et l'enregistre dans `self.last_response`.

### `ask(content, ...)`
Méthode de commodité qui effectue le processus complet :
1. Ajoute le prompt utilisateur à `self.messages`.
2. Lance `execute_stream()` et affiche les tokens.
3. Ajoute automatiquement la réponse de l'assistant à l'historique une fois terminée.

### `_set_system_prompt(content)`
Injecte ou met à jour le message système. Opération idempotente : si un prompt système existe déjà en position 0, il n'est pas dupliqué.
