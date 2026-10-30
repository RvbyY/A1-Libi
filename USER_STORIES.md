# User Stories

Format demandé par le sujet : *En tant que [utilisateur], je veux [action], afin de [résultat].*

Chaque fonctionnalité implémentée a sa fiche détaillée dans [docs/user_stories](docs/user_stories/README.md) :
critères d'acceptation, tests qui les vérifient et limites connues.

## Socle MVP : chatbot en ligne de commande

Statut : ✅ Fait · [fiche détaillée](docs/user_stories/00-socle-mvp.md)

- **Voir la réponse s'écrire** — En tant qu'utilisateur du terminal, je veux voir la réponse de l'assistant s'afficher au fur et à mesure, afin de commencer à lire sans attendre la fin de la génération.
- **Choisir mon modèle** — En tant qu'utilisateur, je veux choisir le modèle avec `--model` ou dans `config.yaml`, afin de changer de modèle sans modifier le code.
- **Comprendre une erreur** — En tant qu'utilisateur, je veux un message clair quand Ollama est éteint ou quand le modèle n'est pas installé, afin de savoir quelle commande lancer pour corriger le problème.

## M1 : Persistance et profils

Statut : ✅ Fait · [fiche détaillée](docs/user_stories/M1-persistance-profils.md)

- **Reprendre ma conversation** — En tant qu'utilisateur, je veux retrouver ma dernière conversation quand je relance SensAI, afin de continuer là où je m'étais arrêté.
- **Un assistant qui me connaît** — En tant qu'utilisateur, je veux que mes instructions de profil soient appliquées à chaque réponse, afin de ne pas répéter mes préférences à chaque conversation.

## R1 : RAG basique

Statut : 🟡 Partiel (RAG sur les conversations, pas encore sur des documents) · [fiche détaillée](docs/user_stories/R1-rag-basique.md)

- **Se souvenir d'une ancienne conversation** — En tant qu'utilisateur, je veux que l'assistant retrouve ce que je lui ai dit dans un autre chat, afin de ne pas avoir à me répéter.
- **Une recherche par le sens** — En tant qu'utilisateur, je veux que la recherche retrouve un souvenir même avec d'autres mots, afin que « où j'habite ? » retrouve « je vis à Lyon ».

## T1 : Appel d'outils (function calling)

Statut : ✅ Fait (appel de fonctions natif d'Ollama, pas le protocole MCP lui-même) · [fiche détaillée](docs/user_stories/T1-appel-outils.md)

- **Faire agir l'assistant** — En tant qu'utilisateur, je veux demander en langage naturel une action comme « ajoute une réunion demain à 10h », afin que l'assistant appelle le bon outil et me confirme le résultat.
- **Voir ce que fait l'assistant** — En tant qu'utilisateur du terminal, je veux voir chaque outil appelé avec ses arguments, son statut et sa durée, afin de savoir exactement quelles actions ont été faites en mon nom.
- **Tester que les outils marchent** — En tant que développeur, je veux demander à l'assistant de « tester les outils » et voir `tools_selftest` me renvoyer mon message, afin de vérifier en une phrase toute la chaîne d'appel d'outils.

## A3 : Human-in-the-loop

Statut : ✅ Fait en CLI (🟡 dans la webapp : les actions critiques y sont toujours refusées) · [fiche détaillée](docs/user_stories/A3-human-in-the-loop.md)

- **Valider avant un envoi** — En tant qu'utilisateur, je veux que l'assistant me demande mon accord avant d'envoyer un email ou un message, afin qu'aucun message ne parte sans ma décision.
- **Refuser sans casser la conversation** — En tant qu'utilisateur, je veux qu'une action refusée soit annulée et signalée à l'assistant, afin qu'il me réponde en conséquence au lieu de prétendre l'avoir faite.

## EV1 : Évaluation automatique (anti-hallucination)

Statut : 🟡 Partiel (détection d'hallucinations faite ; note de cohérence et validation des sources à faire) · [fiche détaillée](docs/user_stories/EV1-evaluation-automatique.md)

- **Des réponses vérifiées** — En tant qu'utilisateur, je veux activer une vérification des réponses avec `--anti-hallucination`, afin de ne pas recevoir d'informations inventées.
- **Un juge qui connaît les faits** — En tant qu'utilisateur, je veux que le juge vérifie la réponse à partir de mes souvenirs et des résultats des outils, afin que la vérification porte sur des faits réels et pas sur l'avis du modèle.

## EV2 : Guardrails

Statut : 🟡 Partiel (filtre en entrée fait ; anonymisation en sortie à faire) · [fiche détaillée](docs/user_stories/EV2-guardrails.md)

- **Bloquer une demande dangereuse** — En tant qu'utilisateur responsable du déploiement, je veux que les demandes illégales ou dangereuses soient refusées avant d'atteindre le modèle, afin que l'assistant ne produise pas de contenu nuisible.
- **Un classement robuste** — En tant que développeur, je veux que le classifieur gère les réponses floues ou mal formées du modèle, afin que le guardrail ne laisse pas passer une demande par erreur.

## EV3 : Monitoring

Statut : 🟡 Partiel (visualiseur temps réel et logs ; pas encore de tableau de métriques) · [fiche détaillée](docs/user_stories/EV3-monitoring.md)

- **Suivre le pipeline en direct** — En tant que développeur, je veux voir dans la webapp quelle étape du pipeline est en cours et comment elle s'est terminée, afin de comprendre où une réponse a échoué ou ralenti.
- **Mesurer les appels** — En tant que développeur, je veux connaître le nombre de tokens et la durée de chaque génération et de chaque outil, afin de repérer ce qui est lent ou coûteux.

## X1 : Interface web

Statut : ✅ Fait · [fiche détaillée](docs/user_stories/X1-interface-web.md)

- **Discuter dans le navigateur** — En tant qu'utilisateur qui n'aime pas le terminal, je veux discuter avec l'assistant dans mon navigateur, afin d'utiliser SensAI sans ligne de commande.
- **Gérer plusieurs conversations** — En tant qu'utilisateur, je veux créer de nouvelles conversations et rouvrir les anciennes depuis une barre latérale, afin de séparer mes sujets sans perdre mon historique.

## X5 : Planification de tâches

Statut : 🟡 Partiel (les tâches sont créées et enregistrées, mais le `TaskRunner` n'est jamais démarré) · [fiche détaillée](docs/user_stories/X5-planification.md)

- **Programmer un rappel** — En tant qu'utilisateur qui apprend le japonais, je veux taper `/schedule in 30m révise tes kanji`, afin que l'assistant me le rappelle au bon moment.
- **Un rapport chaque jour** — En tant qu'utilisateur, je veux programmer `/schedule daily 18:00 résume mes progrès`, afin de recevoir un résumé chaque soir sans le redemander.
