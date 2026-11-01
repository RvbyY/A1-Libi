# EV2 : Guardrails

[Retour aux user stories](README.md)

**Statut :** Fait

---

## Ce que demande le sujet

- Un filtre en entrée qui bloque les requêtes hors périmètre.
- Un filtre en sortie qui anonymise les données personnelles.

## Ce que fait SensAI

- `IntentGuardrail` classe chaque demande en `LEGAL`, `ILLEGAL` ou `AMBIGUOUS` avec le LLM.
- Le classement est fait en JSON, à température 0.
- Une demande ambiguë passe par un second prompt qui tranche.
- Selon la politique (`safety`, `alibi`, `none`), la demande est bloquée avec un message de refus.

---

## User story 1 : bloquer une demande dangereuse

**En tant qu'** utilisateur responsable du déploiement,
**je veux** que les demandes illégales ou dangereuses soient refusées avant d'atteindre le modèle,
**afin que** l'assistant ne produise pas de contenu nuisible.

### Critères d'acceptation

- [x] La demande est classée avant la génération.
- [x] Une demande classée `ILLEGAL` reçoit un message de refus, sans appel au modèle de chat.
- [x] Le refus est enregistré dans l'historique.

**Vérifié par :** `test_chat_engine_guardrail_blocking`, `test_evaluate_policies`.

---

## User story 2 : un classement robuste

**En tant que** développeur,
**je veux** que le classifieur gère les réponses floues ou mal formées du modèle,
**afin que** le guardrail ne laisse pas passer une demande par erreur.

### Critères d'acceptation

- [x] Le JSON est extrait même s'il est entouré de texte.
- [x] Les booléens (`controlled_substance`, `criminal_activity`…) priment sur la catégorie annoncée.
- [x] Une réponse `AMBIGUOUS` ou un JSON invalide déclenche la résolution d'ambiguïté.

**Vérifié par :** `test_extract_json_and_parse_simple_category`, `test_classify_boolean_overrides_category`,
`test_classify_triggers_resolve_ambiguity_on_ambiguous_or_invalid_json`.

---

## Ce qui a été ajouté pour terminer la feature

- **Filtre de sortie** (`src/galerelm/output_guardrail.py`) : email, téléphone, IBAN, carte bancaire (contrôle de Luhn)
  et numéro de sécurité sociale sont détectés dans les réponses.
- Deux modes : `anonymize` remplace chaque donnée par une étiquette (`[EMAIL]`, `[TELEPHONE]`…),
  `refuse` remplace toute la réponse par un message de refus.
- Le filtre s'applique **à l'affichage et à la base** : la donnée n'est jamais enregistrée.
  En streaming, le texte est filtré phrase par phrase, pour reconnaître une donnée coupée en plusieurs tokens.
- Règles configurables : section `guardrails` de `config.yaml` (`input`, `output`, `pii`),
  options `--guardrail` et `--output-filter`, case à cocher dans la webapp.
- Les règles du prompt par défaut qui demandaient de répondre aux questions illégales sont remplacées
  par une règle de refus.

### Tests de la finalisation

```bash
.venv/bin/python -m pytest -q \
  src/galerelm/unit_tests/test_output_guardrail.py
```

Résultat au 1er novembre 2026 : 23 tests passés, 0 en échec.

### Vérification avec le vrai modèle

Avec le vrai modèle, la phrase « mon email est alice@exemple.fr et mon numéro est le 06 12 34 56 78 » est devenue « mon email est [EMAIL] et mon numéro est le [TELEPHONE] », à l'écran et en base.

---

## Preuves

### Code

- [`src/galerelm/intent_classifier.py`](../../src/galerelm/intent_classifier.py)
- [`src/galerelm/engine.py`](../../src/galerelm/engine.py)

### Tests automatisés

Les tests cités dans les critères d'acceptation se relancent avec :

```bash
.venv/bin/python -m pytest -q \
  src/galerelm/unit_tests/test_engine_and_repl.py::test_chat_engine_guardrail_blocking \
  src/galerelm/unit_tests/test_intent_classifier.py::test_evaluate_policies \
  src/galerelm/unit_tests/test_intent_classifier.py::test_extract_json_and_parse_simple_category \
  src/galerelm/unit_tests/test_intent_classifier.py::test_classify_boolean_overrides_category \
  src/galerelm/unit_tests/test_intent_classifier.py::test_classify_triggers_resolve_ambiguity_on_ambiguous_or_invalid_json
```

Résultat au 1er novembre 2026 : 5 tests passés, 0 en échec.

### Démonstration manuelle

1. Lancer la webapp (`./scripts/A1Libi -run`) et cocher la case guardrail.
2. Envoyer une demande clairement illégale : le message de refus s'affiche et le visualiseur marque l'étape guardrail en erreur.

---

## Limites

- La détection repose sur des expressions régulières : un numéro écrit en toutes lettres n'est pas reconnu.
- En mode `refuse`, la réponse n'est affichée qu'à la fin (pas de streaming), puisqu'elle peut être remplacée en entier.
- Le classement d'intention (entrée) dépend du modèle : un petit modèle se trompe plus souvent.
