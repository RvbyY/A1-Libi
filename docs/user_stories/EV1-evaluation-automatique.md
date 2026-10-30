# ⚖️ EV1 : Évaluation automatique (anti-hallucination)

[⬅️ Retour aux user stories](README.md)

**Statut :** 🟡 Partiel (détection d'hallucinations faite ; note de cohérence et validation des sources à faire)

---

## 📋 Ce que demande le sujet

- Un LLM utilisé comme juge.
- Noter la cohérence, détecter les hallucinations et valider les sources.

## ⚙️ Ce que fait SensAI

- `HallucinationGrader` compare la réponse aux faits connus : souvenirs RAG et résultats d'outils.
- Il répond en JSON : `{"grounded": true/false, "critique": "…"}`.
- `AntiHallucinationWorkflow` est un graphe en pur Python : `retrieve → generate → tools → generate → grade`.
- Si la réponse n'est pas fondée, elle est régénérée avec la critique, jusqu'à `--max-retries` fois.

---

## 👤 User story 1 : des réponses vérifiées

**En tant qu'** utilisateur,
**je veux** activer une vérification des réponses avec `--anti-hallucination`,
**afin de** ne pas recevoir d'informations inventées.

### ✅ Critères d'acceptation

- [x] `--anti-hallucination` active le graphe ; il est désactivé par défaut.
- [x] Une réponse jugée non fondée est régénérée, avec la critique ajoutée au prompt.
- [x] `--max-retries N` limite le nombre de régénérations (2 par défaut).
- [x] Dans la webapp, une case à cocher active le même mode.

**Vérifié par :** `test_anti_hallucination_flag_enables_workflow`, `test_max_retries_is_forwarded`,
`test_anti_hallucination_workflow_regenerates_on_hallucination`.

---

## 👤 User story 2 : un juge qui connaît les faits

**En tant qu'** utilisateur,
**je veux** que le juge vérifie la réponse à partir de mes souvenirs et des résultats des outils,
**afin que** la vérification porte sur des faits réels et pas sur l'avis du modèle.

### ✅ Critères d'acceptation

- [x] Les souvenirs RAG et les sorties d'outils sont transmis au juge comme faits de référence.
- [x] Le juge évalue la réponse finale, rédigée après les outils.
- [x] Une régénération ne relance jamais les outils (pas de double envoi d'email).

**Vérifié par :** `test_hallucination_grader_detects_ungrounded_claim`,
`test_workflow_reprompts_after_tools_and_grades_final_answer`, `test_workflow_regeneration_never_reruns_tools`.

---

## ⚠️ Limites

- Pas encore de note de cohérence ni de validation des sources.
- Si le juge plante ou renvoie un JSON illisible, la réponse est acceptée sans avertissement.
- Le même modèle génère et juge : un petit modèle détecte peu d'erreurs.
- Dans ce mode, la réponse s'affiche d'un bloc, sans streaming.
