# A5 : Personas

[Retour aux user stories](README.md)

**Statut :** Fait

---

## Ce que demande le sujet

- Le nom, le ton, le rôle et le périmètre de l'agent se configurent sans modifier le code.
- Plusieurs agents existent, et on change d'agent en cours de session **sans effacer l'historique**.

## Ce que fait SensAI

- Un persona a un nom, une description et des instructions (le texte qui définit son rôle et son ton).
- Trois personas sont fournis : `alibi` (assistant général, instructions du profil), `tuteur` (mathématiques) et `juriste`.
- D'autres se déclarent dans `config.yaml`, section `personas`, et le persona par défaut avec `prompt.persona`.
- On change d'agent avec `/persona <nom>` dans le terminal, `--persona` au lancement, ou la liste « Agent » de la webapp.
- Le changement porte sur le prompt système des messages suivants : la conversation est gardée.

---

## User story 1 : un agent spécialisé sans toucher au code

**En tant que** responsable d'une plateforme éducative,
**je veux** déclarer un agent « tuteur de mathématiques » dans `config.yaml`,
**afin de** proposer un assistant au rôle et au ton adaptés sans modifier le code.

### Critères d'acceptation

- [x] Un persona déclaré dans `config.yaml` (nom, description, instructions) est disponible au lancement.
- [x] `prompt.persona` ou `--persona` choisit l'agent par défaut.
- [x] Un persona inconnu, un champ inconnu ou un nom manquant arrêtent le lancement avec un message clair.
- [x] Le nom et les instructions du persona remplacent ceux du profil dans le prompt système.

**Vérifié par :** `test_personas_from_yaml`, `test_persona_yaml_errors`, `test_cli_persona_flag`,
`test_default_persona_keeps_profile_instructions`.

---

## User story 2 : changer d'agent en pleine conversation

**En tant qu'** utilisateur,
**je veux** passer de l'assistant général au tuteur en cours de discussion,
**afin d'** avoir une explication pas à pas sans perdre ce que j'ai déjà dit.

### Critères d'acceptation

- [x] `/persona` liste les agents et indique l'agent actif.
- [x] `/persona tuteur` change l'agent ; l'historique de la conversation est conservé.
- [x] Le changement vaut aussi pour le mode anti-hallucination et pour les tâches planifiées.
- [x] Dans la webapp, la liste « Agent » change l'agent sans effacer le chat.

**Vérifié par :** `test_switching_persona_keeps_history_and_changes_prompt`, `test_persona_applies_to_anti_hallucination_workflow`,
`test_persona_command_lists_and_rejects_unknown`, `test_webapp_changes_agent_without_losing_history`.

---

## Preuves

### Code

- [`src/config.py`](../../src/config.py) : `DEFAULT_PERSONAS`, section `personas`, `prompt.persona`
- [`src/commands/persona.py`](../../src/commands/persona.py) : commande `/persona`
- [`src/galerelm/models/prompt.py`](../../src/galerelm/models/prompt.py) : `PromptBuilder.with_agent`
- [`src/galerelm/engine.py`](../../src/galerelm/engine.py) : `ChatEngine.set_persona`
- [`src/webapp/views.py`](../../src/webapp/views.py) : liste « Agent »

### Tests automatisés

```bash
.venv/bin/python -m pytest -q src/galerelm/unit_tests/test_persona_webapp.py
```

Résultat au 1er novembre 2026 : 15 tests passés, 0 en échec (personas et webapp).

### Démonstration manuelle

1. Lancer le chat et taper `/persona` : la liste des agents s'affiche, l'agent actif est marqué d'une étoile.
2. Écrire une question, puis taper `/persona tuteur`.
3. Poser une question de mathématiques : la réponse suit le rôle du tuteur ; `/messages` montre que l'historique est intact.
4. Exemple de déclaration dans `config.yaml` :

   ```yaml
   prompt:
     persona: support
   personas:
     support:
       name: Agent support
       description: Aide les clients de la boutique
       instructions: Tu es {persona}. Tu réponds poliment et brièvement aux questions sur les commandes.
   ```

### Vérification avec le vrai modèle

Avec l'agent `tuteur`, le prompt système envoyé commence bien par « Tu es Tuteur de mathématiques ».
Le modèle 2B a pourtant répondu à une question hors mathématiques (« Quelle est la capitale de la France ? »)
au lieu de rediriger : le périmètre d'un persona dépend de la capacité du modèle à suivre ses instructions.

---

## Limites

- Le respect du périmètre (« ne réponds qu'aux questions de mathématiques ») dépend du modèle ; le 2B l'ignore parfois.
- Dans la webapp, l'agent choisi est partagé entre les utilisateurs connectés en même temps.
