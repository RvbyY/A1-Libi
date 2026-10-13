# 📖 8. Glossaire

Les mots techniques, expliqués simplement.

Classés par ordre **alphabétique**.

[⬅️ Retour au sommaire](README.md)

---

### API
Une **porte d'entrée** vers un programme.
On lui envoie une demande, elle renvoie une réponse.

### Base de données
Un **fichier** qui range les informations en tableaux.
Ici : `galerelm.db`.

### Context
La **mémoire courte**. Les derniers messages de la conversation.

### DeepContext
La **mémoire longue**. Les anciens messages, retrouvés par le sens.

### DTO
Un **objet simple** qui transporte des données.
Exemple : `ProfileResponse`.

### Embedding
Voir **Vecteur**.

### Endpoint
Une **adresse précise** d'une API.
Exemple : `api/chat`.

### Facade
Une classe qui **cache** la complexité derrière des fonctions simples.
Ici : `SensAIWrapper`.

### Framework
Une **boîte à outils** pour construire une application.

### Gradio
Une bibliothèque Python pour créer une **interface web** rapidement.

### JSON
Un **format de texte** pour ranger des données.
Exemple : `{"nom": "Alice"}`.

### LLM
**Large Language Model**. Une IA qui comprend et écrit du texte.

### Log
Une **ligne de suivi** écrite par le programme.
Elle dit ce qui se passe.

### NDJSON
Du JSON avec **un objet par ligne**.
Utilisé pour le streaming.

### Ollama
Un logiciel qui fait tourner une IA **sur votre machine**.

### ORM
Un outil qui relie **les classes Python** aux **tables de la base**.
Ici : SQLAlchemy.

### Overflow
Un **débordement**. Quand la mémoire courte est trop pleine.

### Payload
Le **contenu** d'une requête.
Ici : le JSON envoyé à Ollama.

### Profile
Un **utilisateur** et ses consignes pour l'IA.

### Prompt
Le **texte** envoyé à l'IA.

### Prompt système
Les **consignes** données à l'IA avant la conversation.
Exemple : "Tu es un assistant concis."

### RAG
**Retrieval-Augmented Generation**.
On **cherche** des informations utiles, puis on les **donne** à l'IA avant qu'elle réponde.

### REPL
Une boucle : **lire**, **exécuter**, **afficher**, **recommencer**.
C'est le mode terminal de SensAI.

### Similarité cosinus
Un calcul qui dit si deux vecteurs ont le **même sens**.
Score de 0 (aucun rapport) à 1 (identique).

### SQLAlchemy
La bibliothèque Python qui gère la **base de données**.

### SQLite
Une base de données dans **un seul fichier**.

### Streaming
Recevoir la réponse **morceau par morceau**, pendant qu'elle s'écrit.

### Token
Un **morceau de mot**. L'IA écrit token par token.

### Vecteur
Une **liste de nombres** qui représente le **sens** d'un texte.
Deux textes proches ont des vecteurs proches.

### Wrapper
Voir **Facade**.

---

[⬅️ Page précédente : RapideAPI](07-rapideapi.md) · [➡️ Page suivante : Problèmes connus](09-problemes-connus.md)
