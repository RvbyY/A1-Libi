# 🛡️ EV2 : Guardrails

[⬅️ Retour aux user stories](README.md)

**Statut :** 🟡 Partiel (filtre en entrée fait ; anonymisation en sortie à faire)

---

## 📋 Ce que demande le sujet

- Un filtre en entrée qui bloque les requêtes hors périmètre.
- Un filtre en sortie qui anonymise les données personnelles.

## ⚙️ Ce que fait SensAI

- `IntentGuardrail` classe chaque demande en `LEGAL`, `ILLEGAL` ou `AMBIGUOUS` avec le LLM.
- Le classement est fait en JSON, à température 0.
- Une demande ambiguë passe par un second prompt qui tranche.
- Selon la politique (`safety`, `alibi`, `none`), la demande est bloquée avec un message de refus.

---

## 👤 User story 1 : bloquer une demande dangereuse

**En tant qu'** utilisateur responsable du déploiement,
**je veux** que les demandes illégales ou dangereuses soient refusées avant d'atteindre le modèle,
**afin que** l'assistant ne produise pas de contenu nuisible.

### ✅ Critères d'acceptation

- [x] La demande est classée avant la génération.
- [x] Une demande classée `ILLEGAL` reçoit un message de refus, sans appel au modèle de chat.
- [x] Le refus est enregistré dans l'historique.

**Vérifié par :** `test_chat_engine_guardrail_blocking`, `test_evaluate_policies`.

---

## 👤 User story 2 : un classement robuste

**En tant que** développeur,
**je veux** que le classifieur gère les réponses floues ou mal formées du modèle,
**afin que** le guardrail ne laisse pas passer une demande par erreur.

### ✅ Critères d'acceptation

- [x] Le JSON est extrait même s'il est entouré de texte.
- [x] Les booléens (`controlled_substance`, `criminal_activity`…) priment sur la catégorie annoncée.
- [x] Une réponse `AMBIGUOUS` ou un JSON invalide déclenche la résolution d'ambiguïté.

**Vérifié par :** `test_extract_json_and_parse_simple_category`, `test_classify_boolean_overrides_category`,
`test_classify_triggers_resolve_ambiguity_on_ambiguous_or_invalid_json`.

---

## ⚠️ Limites

- Pas de filtre en sortie : les données personnelles ne sont pas anonymisées.
- Activable dans la webapp (case à cocher), pas encore depuis la CLI.
- Les règles par défaut du prompt système demandent de répondre aux questions illégales :
  elles contredisent ce guardrail et devraient être retirées.
