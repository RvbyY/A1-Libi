# EV2 : Guardrails

[Retour aux user stories](README.md)

**Statut :** Partiel (filtre en entrée fait ; anonymisation en sortie à faire)

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

## Ce qu'il reste à faire

Objectif : ajouter le **filtre en sortie**, et rendre les deux filtres configurables.

1. **Détecter les données personnelles.**
   - Créer `src/galerelm/output_guardrail.py` avec une classe `OutputGuardrail`.
   - Détection par expressions régulières : email, téléphone, IBAN, numéro de carte bancaire, numéro de sécurité sociale.
2. **Anonymiser ou refuser.**
   - Mode `anonymize` : remplacer chaque donnée par une étiquette (`[EMAIL]`, `[TELEPHONE]`…).
   - Mode `refuse` : remplacer toute la réponse par un message de refus.
3. **Brancher le filtre.**
   - L'appliquer dans `ChatEngine` avant l'affichage **et** avant la sauvegarde en base.
   - Le streaming envoie des morceaux de mots : il faut filtrer par phrase (tampon jusqu'à la ponctuation),
     ou désactiver le streaming quand le filtre est actif.
4. **Rendre les règles configurables.**
   - Ajouter une section `guardrails` dans `config.yaml` : catégories à anonymiser, mode, politique d'entrée.
   - Ajouter `--guardrail` à la CLI : aujourd'hui, le filtre d'entrée ne s'active que dans la webapp.
5. **Retirer la contradiction du prompt.**
   - Supprimer de `DEFAULT_SYSTEM_RULES` les règles qui demandent de répondre aux questions illégales.
6. **Tester.**
   - Chaque catégorie de données, les deux modes, le filtrage en streaming, la configuration YAML.

**Quand le considérer comme fait :** une réponse contenant un email ou un téléphone est affichée
et enregistrée anonymisée, selon les règles de `config.yaml`.

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

1. Lancer la webapp (`./script/frontend.sh`) et cocher la case guardrail.
2. Envoyer une demande clairement illégale : le message de refus s'affiche et le visualiseur marque l'étape guardrail en erreur.

---

## Limites

- Pas de filtre en sortie : les données personnelles ne sont pas anonymisées.
- Activable dans la webapp (case à cocher), pas encore depuis la CLI.
- Les règles par défaut du prompt système demandent de répondre aux questions illégales :
  elles contredisent ce guardrail et devraient être retirées.
