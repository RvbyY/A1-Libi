
# Projet Sensai - Assistant IA Local

## Directives pour l'Assistant IA

Ce document constitue le cahier des charges de référence. Lors de toute intervention sur ce dépôt (lecture de code, génération de correctifs, architecture), vous devez impérativement respecter les contraintes techniques ci-dessous. Les nouvelles implémentations doivent correspondre aux spécifications du catalogue de fonctionnalités.

## Contraintes Techniques Strictes

* **Langage :** Python 3.10 ou supérieur.
* **Interdiction des Frameworks LLM :** LangChain, LlamaIndex, Haystack ou tout framework similaire sont strictement interdits. Les bibliothèques standards (requests, sqlite3, fastapi, etc.) sont autorisées pour la logique classique.
* **Communication Modèle :** Tous les appels au modèle de langage doivent s'effectuer directement via l'API HTTP d'Ollama.

## Architecture du Socle de Base (MVP)

Avant toute fonctionnalité avancée, le projet doit intégrer cette boucle fondamentale :

* **Interface :** Chatbot fonctionnel en ligne de commande (CLI).
* **Affichage :** Rendu des réponses en streaming continu.
* **Contexte :** Maintien de l'historique de conversation injecté à chaque tour de parole au sein d'une session.
* **Gestion des erreurs :** Traitement des modèles indisponibles, des entrées vides et des échecs de connexion réseau.
* **Configuration :** Sélection du modèle dynamiquement via argument CLI ou fichier de configuration.

## Catalogue des Fonctionnalités

**Mémoire et Contexte**

* **[M1] Persistance & Profils :** Sauvegarde des historiques de session et injection automatique de profils utilisateurs persistants.
* **[M2] Budget Tokens & Compression :** Résumé par fenêtre glissante des anciens messages à l'approche de la limite de tokens pour préserver le contexte critique.
* **[M3] Mémoire Structurée Externe :** Intégration SQLite/NoSQL permettant à l'agent d'effectuer des opérations CRUD sur des faits et entités au fil des interactions.
* **[M4] Artefact d'État :** Maintien et mise à jour incrémentielle d'un document distinct de l'historique de conversation (ex: résumé de code, spécification).

**Outils et Exécution**

* **[T1] Model Context Protocol (MCP) :** L'agent émet des requêtes structurées pour appeler des fonctions externes et intègre les résultats retournés.
* **[T2] Exécution Sandbox :** Environnement isolé (Docker ou sous-processus) permettant à l'agent d'exécuter du code, de capturer les erreurs et de se corriger.
* **[T3] Recherche Web :** Exécution de requêtes web en direct, analyse des résultats et injection dans le contexte.
* **[T4] Système de Fichiers & Permissions :** Lecture et écriture sur le disque avec une couche de validation des permissions.
* **[T5] Sortie Structurée :** Obligation pour le modèle de générer des réponses respectant un schéma JSON précis.

**Génération Augmentée par la Recherche (RAG)**

* **[R1] RAG Basique :** Ingestion locale, découpage, vectorisation, stockage et recherche sémantique de documents pour enrichir le contexte.
* **[R2] RAG Avancé :** Ajout de filtrage par métadonnées, reclassement (reranking) et score de pertinence par fragment.

**Orchestration et Raisonnement**

* **[A1] Boucles ReAct :** Processus de raisonnement explicite et itératif de l'agent avant la génération de la réponse finale.
* **[A2] Multi-Agents :** Coordination de plusieurs agents spécialisés se passant le relais sur une tâche complexe.
* **[A3] Human-in-the-Loop :** Suspension de l'exécution et demande de confirmation explicite à l'utilisateur avant toute action critique.
* **[A4] Versionnage de Prompts :** Historisation des invites avec horodatage pour comparaison et retour en arrière.
* **[A5] Personas Dynamiques :** Basculement du rôle, du ton et des instructions système de l'agent en cours de session via configuration.
* **[A6] Cache Sémantique :** Fourniture de réponses pré-calculées pour les requêtes sémantiquement similaires afin de réduire la latence.
* **[A7] Optimisation Automatisée :** Construction dynamique des prompts avec sélection d'exemples "few-shot" adaptés au contexte.

**Évaluation et Sécurité**

* **[EV1] Évaluation Automatique :** Utilisation d'un LLM comme juge pour noter la cohérence, détecter les hallucinations et valider les sources.
* **[EV2] Guardrails :** Filtres en entrée (blocage de requêtes hors périmètre) et en sortie (anonymisation des données personnelles).
* **[EV3] Dashboard de Monitoring :** Journalisation structurée (latence, tokens, prompts) connectée à une interface de visualisation des métriques.
* **[EV4] Tests Adversariaux :** Suite de tests automatisés (jailbreaks, injections) pour valider la robustesse de l'agent.

**Expérience Utilisateur (UX)**

* **[X1] Interface Web :** Frontend web découplé reposant sur le backend CLI.
* **[X2] Branchement et Interruption :** Possibilité d'éditer un ancien message pour créer une nouvelle branche, ou d'interrompre une génération en cours.
* **[X3] Exportation :** Génération de fichiers (JSON, Markdown, PDF) et création de liens de partage sans authentification.
* **[X4] Formulaires :** Interface permettant à l'utilisateur de répondre facilement aux questions de clarification de l'IA.
* **[X5] Planification :** Exécution autonome de tâches récurrentes à intervalles réguliers (ex: rapports quotidiens).

## Livrables Requis

* Dépôt contenant l'intégralité du code source.
* Fichier `requirements.txt` listant les dépendances autorisées.
* Fichier `USER_STORIES.md` détaillant au moins deux user stories par fonctionnalité implémentée (Format : En tant que [utilisateur], je veux [action], afin de [résultat]).
* Fichier `README.md` mis à jour avec les instructions d'installation locales et les commandes de lancement.
