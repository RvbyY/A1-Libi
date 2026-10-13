# Spécifications du Wrapper Web (Facade API)

Ce document liste l'ensemble des fonctions haut niveau ("endpoints") exposées par la classe `SensAIWrapper`. Ce wrapper simplifie l'utilisation du framework pour les applications clientes (APIs REST, interfaces web).

Pour garantir la sécurité du typage et éviter les erreurs de manipulation de dictionnaires (`dict`), toutes les fonctions renvoient des objets de type **Response** (implémentés via `dataclasses` ou `Pydantic`).

## Modèles de Données (Types de Sortie)

```python
class ProfileResponse:
    id: str
    name: str
    email: str
    instructions: str

class ContextResponse:
    id: int
    profile_id: str
    context_limit: int

class MessageResponse:
    role: str
    content: str

class ChatCompletionResponse:
    message: MessageResponse
    eval_count: int
    eval_duration: float

class MemoryResponse:
    id: int
    role: str
    content: str
    score: float = None  # Utilisé uniquement lors de la recherche

class StatusResponse:
    db_status: str
    api_status: str
    active_model: str
```

---

## 1. Gestion des Utilisateurs (Profils)

Ces fonctions permettent de gérer les comptes utilisateurs et leurs personnalisations.

- **`create_profile(email: str, name: str, instructions: str) -> ProfileResponse`**
  - *Description* : Crée un nouvel utilisateur dans la base de données.

- **`get_profile(email: str) -> ProfileResponse | None`**
  - *Description* : Récupère les informations d'un profil existant.

- **`update_profile(email: str, name: str = None, instructions: str = None) -> ProfileResponse`**
  - *Description* : Modifie le nom ou le prompt système d'un utilisateur.

- **`list_profiles() -> list[ProfileResponse]`**
  - *Description* : Récupère l'ensemble des profils enregistrés dans le système.

## 2. Gestion des Sessions (Contexte Court Terme)

- **`start_new_chat(email: str) -> ContextResponse`**
  - *Description* : Crée un contexte vierge pour l'utilisateur (bouton "Nouvelle conversation").

- **`get_chat_history(email: str) -> list[MessageResponse]`**
  - *Description* : Récupère la liste des messages de la conversation active pour affichage.

- **`clear_chat(email: str) -> bool`**
  - *Description* : Vide l'historique du contexte actif sans changer l'ID du contexte.

## 3. Inférence & Discussion

- **`chat_stream(email: str, prompt: str) -> Generator[str, None, None]`**
  - *Description* : Reçoit le prompt, applique le RAG en arrière-plan, et renvoie un générateur qui stream la réponse token par token (idéal pour les WebSockets / SSE).

- **`chat_blocking(email: str, prompt: str) -> ChatCompletionResponse`**
  - *Description* : Bloque jusqu'à la fin de la génération, puis renvoie la réponse complète encapsulée dans un objet fortement typé avec ses métadonnées.

## 4. Transparence et Mémoire Long Terme (RAG)

- **`get_memories(email: str) -> list[MemoryResponse]`**
  - *Description* : Renvoie la liste de tous les souvenirs vectorisés de l'utilisateur.

- **`search_memories(email: str, query: str, top_k: int = 5) -> list[MemoryResponse]`**
  - *Description* : Recherche sémantique dans l'historique (avec le champ `score` rempli).

- **`delete_memory(memory_id: int) -> bool`**
  - *Description* : Supprime définitivement un souvenir précis de la mémoire vectorielle.

## 5. Configuration et Système

- **`get_status() -> StatusResponse`**
  - *Description* : Vérifie l'état de santé du framework (connexion BDD et API).

- **`set_active_model(model_name: str) -> bool`**
  - *Description* : Change le modèle LLM actif à la volée.
