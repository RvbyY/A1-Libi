# User Stories

Format : *En tant que [utilisateur], je veux [action], afin de [résultat].*

## Outils (tools)

### Tool de test `tools_selftest`

- En tant que développeur, je veux demander à l'assistant de « tester les outils » et voir le tool `tools_selftest` renvoyer mon message, afin de vérifier en une commande que le modèle sait appeler un outil et que son résultat revient dans la conversation.
- En tant que développeur, je veux pouvoir forcer un échec du tool (`mode: fail`), afin de vérifier que les erreurs d'outils sont bien affichées et transmises au modèle sans faire planter la session.

### Logs d'utilisation des tools dans la CLI

- En tant qu'utilisateur du terminal, je veux voir chaque outil appelé par l'assistant avec ses arguments, son statut et sa durée, afin de savoir exactement quelles actions ont été faites en mon nom.
- En tant que développeur, je veux que chaque appel d'outil soit aussi journalisé par le logger `sensai.tools`, afin de pouvoir diagnostiquer un outil lent ou en échec.

### Confirmation des actions critiques

- En tant qu'utilisateur, je veux que l'assistant me demande mon accord avant d'envoyer un email, un message Discord/Telegram ou une notification, afin qu'aucun message ne parte sans ma décision.
- En tant qu'utilisateur, je veux qu'une action refusée soit annulée et signalée à l'assistant, afin qu'il me réponde en conséquence au lieu de prétendre l'avoir faite.
