# 🛠️ 13. Utiliser les context tools

Cette page explique comment fonctionne chaque tool.

Chaque appel reçoit :

- un `ToolContext` ;
- un dictionnaire d'arguments ;
- un `ToolResult` en retour.

[⬅️ Retour au sommaire](README.md)

---

## 🧠 Memory

Fichier :
[`src/tools/memory/memory_tools.py`](../src/tools/memory/memory_tools.py)

`Memory` agit sur une conversation persistée en base.

Il reçoit une fabrique de sessions SQLAlchemy :

```python
memory = Memory(
    session_factory=sensai.SessionLocal,
    api_client=sensai.api,
)
```

### Résumer une session

```json
{
  "action": "summarize",
  "session_id": "1"
}
```

Le tool :

1. convertit `session_id` en identifiant numérique ;
2. charge le `Context` ;
3. lit les messages de la mémoire courte ;
4. retourne une ligne par message.

Le résultat est un texte du type :

```text
user: Bonjour
assistant: Bonjour, comment puis-je aider ?
```

Ce résultat est une vue des messages.

Ce n'est pas encore un résumé produit par un modèle.

### Rechercher dans la mémoire longue

```json
{
  "action": "search",
  "session_id": "1",
  "query": "Paris"
}
```

La recherche :

1. charge le `DeepContext` du profil ;
2. vectorise la requête si un client API est disponible ;
3. utilise la similarité cosinus ;
4. retourne les souvenirs les plus proches ;
5. utilise une recherche textuelle comme solution de secours.

Chaque résultat contient :

```json
{
  "id": 12,
  "role": "user",
  "content": "J'habite à Paris",
  "score": 0.91
}
```

### Effacer la mémoire courte

```json
{
  "action": "clear",
  "session_id": "1"
}
```

Cette action supprime les messages du `Context`.

Elle ne supprime pas les souvenirs déjà archivés dans `DeepContext`.

---

## 📅 Calendar

Fichier :
[`src/tools/calendar/calendar_tools.py`](../src/tools/calendar/calendar_tools.py)

`Calendar` est un agenda en mémoire.

Les événements sont associés à `context.user_id`.

### Ajouter un événement

```json
{
  "action": "add",
  "title": "Réunion",
  "start": "2026-10-20T09:00:00",
  "end": "2026-10-20T10:00:00",
  "attendees": ["user-2"]
}
```

Le tool vérifie :

- que le titre existe ;
- que les deux dates existent ;
- que les dates suivent le format ISO 8601 ;
- que la fin est après le début.

### Lister les événements

```json
{
  "action": "list",
  "date_from": "2026-10-20T00:00:00",
  "date_to": "2026-10-21T00:00:00"
}
```

Seuls les événements de l'utilisateur courant sont retournés.

Un événement est inclus si sa période croise la période demandée.

### Annuler un événement

```json
{
  "action": "cancel",
  "event_id": "0"
}
```

Un utilisateur ne peut annuler que son propre événement.

> [!WARNING]
> Les événements disparaissent quand le processus Python s'arrête.
> Ils ne sont pas encore sauvegardés dans SQLite.

---

## 💬 Discord

Fichier :
[`src/tools/communication/discord.py`](../src/tools/communication/discord.py)

`Discord` envoie un message privé à un utilisateur Discord.

### Arguments

```json
{
  "recipient": "123456789012345678",
  "content": "Bonjour depuis SensAI"
}
```

Le tool :

1. lit `DISCORD_TOKEN` depuis l'environnement ;
2. vérifie que l'identifiant contient entre 17 et 20 chiffres ;
3. demande à Discord de créer un canal privé ;
4. envoie le contenu dans ce canal ;
5. transforme la réponse en `ToolResult`.

Le token ne doit jamais être placé directement dans le fichier Python.

---

## ✈️ Telegram

Fichier :
[`src/tools/communication/telegram.py`](../src/tools/communication/telegram.py)

`Telegram` envoie un message avec la Telegram Bot API.

### Arguments

```json
{
  "recipient": "123456789",
  "content": "Bonjour depuis SensAI"
}
```

Le token est lu dans la variable `TOKEN`.

Avant l'envoi, le tool tente de vérifier le destinataire avec une page
publique Telegram.

Ensuite, il appelle :

```text
https://api.telegram.org/bot<TOKEN>/sendMessage
```

Les erreurs HTTP et les erreurs retournées par Telegram deviennent un résultat
en échec.

---

## ✉️ Email

Fichier :
[`src/tools/communication/email.py`](../src/tools/communication/email.py)

`Email` envoie un message avec SMTP.

### Arguments

```json
{
  "recipient": "contact@example.com",
  "subject": "Information",
  "content": "Bonjour"
}
```

L'adresse de l'expéditeur vient de `context.user_email`.

Le tool vérifie :

- que l'utilisateur a une adresse ;
- que l'adresse de l'utilisateur est valide ;
- que l'adresse du destinataire est valide.

Il ouvre ensuite un serveur SMTP local :

```python
with smtplib.SMTP("localhost") as mail_server:
    ...
```

Le serveur doit donc être configuré sur la machine qui exécute SensAI.

---

## ✅ Lire un `ToolResult`

Tous les tools retournent la même structure.

```python
result = tool.execute(context, arguments)

if result.success:
    print(result.message)
    print(result.data)
else:
    print(f"Échec : {result.message}")
```

Exemple d'échec :

```python
ToolResult(
    success=False,
    message="Invalid recipient email format.",
    data=None,
)
```

Le champ `message` est destiné à l'affichage.

Le champ `data` contient les données utiles au programme ou au modèle.

---

## 🧪 Ajouter un nouveau tool

1. Créer une classe qui hérite de `ToolsInterface`.
2. Donner un nom unique à la propriété `name`.
3. Décrire les arguments dans `parameters`.
4. Valider les données dans `execute`.
5. Retourner un `ToolResult`.
6. Ajouter l'instance au `ToolRegistry`.

Exemple minimal :

```python
class Reminder(ToolsInterface):
    @property
    def name(self) -> str:
        return "reminder"

    @property
    def description(self) -> str:
        return "Create a reminder."

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        }

    def execute(self, context: ToolContext, arguments: dict) -> ToolResult:
        text = arguments.get("text")
        if not isinstance(text, str) or not text.strip():
            return ToolResult(False, "text is required.")
        return ToolResult(True, "Reminder created.", {"text": text})
```

---

[⬅️ Page précédente : Architecture des context tools](12-architecture-context-tools.md)
