# Documentation : DeepContext (`deep_context.py`)

## Description Générale
La classe `DeepContext` et le modèle `LongTermMemory` forment la **Mémoire à Long Terme (Vectorielle)** du framework SensAI. 
Ce module persisté en base de données SQLAlchemy permet de stocker l'historique complet d'un utilisateur sans limite stricte, en utilisant des **embeddings vectoriels** pour réaliser une recherche sémantique (RAG : Retrieval-Augmented Generation).

## Composants Principaux

### Fonction `cosine_similarity(a, b)`
Implémentation mathématique pure Python du calcul de la similarité cosinus. Utilisée pour comparer la proximité sémantique entre deux vecteurs d'embedding.

### Classe `DeepContext`
Modèle ORM parent gérant les paramètres de la vectorisation.
- `vector_limit` (int) : Limite théorique maximale des vecteurs.
- `embed_model` (str) : Nom du modèle utilisé pour l'embedding via Ollama (par défaut `nomic-embed-text`).
- `memories` (relationship) : La liste de toutes les `LongTermMemory` stockées.

#### `save(message_list, api_client=None)`
Reçoit une liste de messages (généralement provenant de l'overflow du `Context`) et :
1. Extrait leur contenu textuel.
2. Utilise `api_client` pour appeler `/api/embed` et générer un vecteur mathématique par lot (`_embed_batch`).
3. Crée et sauvegarde une entité `LongTermMemory` pour chaque message avec son vecteur (ou un vecteur vide si l'API est absente).

#### `search(query, api_client, top_k=3)`
Le cœur du système RAG. 
1. Génère un vecteur pour la requête (`query`).
2. Calcule la similarité cosinus contre toutes les mémoires stockées (`LongTermMemory`).
3. Trie les mémoires par pertinence (score le plus proche de 1.0) et retourne les `top_k` meilleurs résultats.

### Classe `LongTermMemory`
Modèle ORM représentant une seule ligne dans la mémoire à long terme.
- `role` (str) : Le rôle (user, assistant, etc.).
- `content` (str) : Le texte de la mémoire.
- `embedding` (list[float]) : Le vecteur mathématique de ce texte, stocké sous forme JSON.
