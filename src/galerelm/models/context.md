# Documentation : Context (`context.py`)

## Description Générale
Le modèle `Context` représente la **Mémoire à Court Terme (Relationnelle)** du système de double mémoire. 
Il a pour but de maintenir le fil exact et immédiat de la conversation (historique brut). Il est sauvegardé de manière persistante dans une base de données SQL via SQLAlchemy.

Afin de ne pas dépasser la fenêtre de contexte maximale du modèle LLM, ce contexte est limité par `context_limit`. Au-delà de cette limite, un mécanisme d'overflow (débordement) transfère les messages les plus anciens vers la mémoire à long terme (`DeepContext`).

## Attributs Principaux
- `profile_id` (str) : L'identifiant du profil utilisateur auquel ce contexte appartient.
- `context_limit` (int) : Le nombre maximum de messages conservés en mémoire à court terme (par défaut 10).
- `messages` (relationship) : Une relation un-à-plusieurs vers les objets `Message`.
- `deep_context` (relationship) : Une relation un-à-un vers le `DeepContext` associé (la mémoire à long terme).

## Méthodes Clés
### `add(message: Message, api_client=None)`
Ajoute un nouveau message dans le contexte et appelle `_check_limit_and_save()` pour vérifier si le contexte dépasse sa limite autorisée.

### `_check_limit_and_save(api_client=None)`
Logique d'overflow :
1. Vérifie si le nombre de messages dépasse `context_limit`.
2. Si oui, calcule le nombre de messages en excès (`overflow_count`).
3. Sépare les messages les plus anciens et les transfère au `DeepContext` via la méthode `save()`.
4. Supprime les messages archivés de la mémoire à court terme.

### `get_messages_copy() -> MessageList`
Méthode utilitaire très importante. Elle crée des copies *détachées* (sans identité ORM) de tous les messages actuels.
Cela permet de passer la liste de messages à l'objet éphémère `Chat` sans provoquer d'effets de bord avec SQLAlchemy (comme des modifications accidentelles de clés étrangères).
