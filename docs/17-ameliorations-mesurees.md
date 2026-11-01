# 17. Améliorations mesurées

Cette page montre, chiffres à l'appui, ce que chaque amélioration apporte par rapport à avant.

Chaque amélioration est comparée à une **baseline** : le comportement de SensAI avant le changement,
sur le même jeu de questions, avec le même modèle et les mêmes réglages.

[Retour au sommaire](README.md)

---

## Méthode

### Le principe

1. Un **jeu de référence** fixe : des demandes avec le résultat attendu.
2. Pour chaque amélioration, deux variantes (ou plus) de SensAI :
   - la **baseline**, qui reproduit le comportement d'avant ;
   - la ou les **variantes** améliorées.
3. Chaque variante répond au même jeu, plusieurs fois.
4. On compare le **taux de réussite**, la **taille du prompt** (tokens lus par le modèle) et la **durée**.

### Les améliorations évaluées

| Expérience | Baseline (avant) | Variante (après) | Commit du changement |
|------------|------------------|------------------|----------------------|
| `relance_outils` | Après un outil, le modèle n'est pas relancé (`max_tool_rounds = 0`) | Le modèle est relancé avec le résultat de l'outil | `51e0fce` |
| `memoire_inter_chats` | Un nouveau chat n'archive pas les précédents | `/new` archive les chats précédents en mémoire longue | `0696e36` |
| `description_outils` | Outils décrits en signatures complètes dans le prompt (comportement d'avant cette mesure) | Noms seulement, ou aucune liste | Décidé ici, d'après la mesure |

La baseline est reproduite par un réglage du code actuel, pas en revenant à un ancien commit.
Ainsi, seule l'amélioration change entre deux variantes : tout le reste du code est identique.

### Le jeu de référence

Fichier : [`benchmark/datasets/quality.yaml`](../benchmark/datasets/quality.yaml).

| Partie | Nombre de cas | Ce qu'on vérifie |
|--------|---------------|------------------|
| `tool_answer` | 5 | « Teste les outils avec le message X » : la réponse finale doit reprendre le **résultat renvoyé par l'outil** (« Selftest OK: X »). Recopier l'appel ne compte pas. |
| `memory` | 5 | Un fait est dit dans un chat (« mon chien s'appelle Rex »). Dans un **nouveau** chat, la réponse à la question doit contenir le mot attendu. |
| `tool_choice` | 12 | 8 demandes qui exigent un outil précis (agenda, email, Telegram, tâche, mémoire, résumé, test) et 4 qui n'en exigent aucun. Réussite : le bon outil est appelé, ou aucun outil quand il n'en faut pas. |

La comparaison des mots ignore la casse et les accents (« Lyon » = « lyon »).

### Les conditions

- **Modèle** : celui du projet, Qwen3.8 2B (Q4_K_M), sur GPU (voir le [benchmark des ressources](16-benchmark-ressources.md)).
- **Génération** : `temperature` 0 et `seed` 42, pour que les variantes ne diffèrent que par le changement mesuré.
- **3 répétitions** de chaque cas. Même à température 0, les résultats varient un peu d'un passage à l'autre sur GPU :
  un premier essai à une seule répétition donnait 3/5 puis 2/5 sur la mémoire.
- **Une instance de SensAI neuve par cas**, avec une base en mémoire : aucun souvenir ne passe d'un cas à l'autre.
- **Aucune action réelle** : les outils à effet de bord (email, Telegram…) sont refusés par la confirmation.
  L'appel est compté, rien n'est envoyé.

### Reproduire

Ollama doit tourner. Depuis la racine du projet :

```bash
PYTHONPATH=. .venv/bin/python -m benchmark.quality --reps 3
```

Une seule expérience :

```bash
PYTHONPATH=. .venv/bin/python -m benchmark.quality --experiments memoire_inter_chats --reps 3
```

Le script écrit dans `benchmark/results/` un rapport `<date>_quality.md` (tableaux et détail par cas)
et un fichier `<date>_quality.json` (chaque réponse).

Le code est dans [`benchmark/quality.py`](../benchmark/quality.py).
Sa logique (variantes, critères de réussite, rapport) est testée sans Ollama, avec un faux modèle,
dans [`test_benchmark_quality.py`](../src/galerelm/unit_tests/test_benchmark_quality.py).

---

## Résultats

Mesures du 1er novembre 2026, 3 répétitions de chaque cas.
Rapport complet, avec chaque réponse : [`benchmark/results/2026-11-01_2002_quality.md`](../benchmark/results/2026-11-01_2002_quality.md)
et [`2026-11-01_2002_quality.json`](../benchmark/results/2026-11-01_2002_quality.json).

### Bilan

| Amélioration | Baseline (avant) | Après | Gain mesuré |
|--------------|------------------|-------|-------------|
| Relance du modèle après un outil | 0 / 15 (0 %), 12 réponses vides | 6 / 15 (40 %), aucune réponse vide | **+40 points** |
| Mémoire entre les chats | 0 / 15 (0 %) | 6 / 15 (40 %) | **+40 points** |
| Outils décrits par leur nom seulement | 2 277 tokens par requête, 12 / 36 (33,3 %) | 1 989 tokens, 15 / 36 (41,7 %) | **-288 tokens (-12,6 %)**, sans perte de réussite |

Une amélioration de ressources s'ajoute, mesurée dans le [benchmark des ressources](16-benchmark-ressources.md) :
`num_ctx` passé de 4096 à 8192, pour 104 Mo de VRAM et sans perte de vitesse.

### 1. Relance du modèle après un outil (`relance_outils`)

| Variante | Réussite | Outil appelé | Réponses vides | Durée moyenne |
|----------|----------|--------------|----------------|---------------|
| Sans relance (baseline) | 0 / 15 | 12 / 15 | 12 | 1,46 s |
| Avec relance | 6 / 15 | 12 / 15 | 0 | 3,10 s |

- **Avant** : quand le modèle appelait l'outil, la réponse affichée était **toujours vide**.
- **Après** : il n'y a plus de réponse vide, et 6 fois sur 12 la réponse reprend le résultat de l'outil (« Selftest OK: kiwi »).
- **Coût** : environ 1,6 seconde de plus, le temps d'une seconde génération.
- **Reste à corriger** : dans 9 cas sur 12, le modèle rappelle l'outil pendant la relance,
  ou recopie son appel en JSON au lieu de répondre.

### 2. Mémoire entre les chats (`memoire_inter_chats`)

| Variante | Réussite | Prompt moyen | Durée moyenne |
|----------|----------|--------------|---------------|
| Sans archivage (baseline) | 0 / 15 | 2 271 tokens | 0,64 s |
| Avec archivage | 6 / 15 | 2 363 tokens | 0,86 s |

- **Avant** : un fait dit dans un chat court n'était jamais retrouvé dans un nouveau chat.
- **Après** : les souvenirs sont injectés (+92 tokens en moyenne dans le prompt).
  Le chien (« Rex ») et le plat préféré (« raclette ») sont retrouvés à chaque répétition.
- **Reste à corriger** : la ville, l'entreprise et la couleur ne sont jamais retrouvées,
  alors que les souvenirs sont bien dans le prompt. C'est une limite du modèle 2B, qui ne s'en sert pas.

### 3. Description des outils dans le prompt (`description_outils`)

| Variante | Réussite | Demandes avec outil | Demandes sans outil | Prompt moyen |
|----------|----------|---------------------|---------------------|--------------|
| Signatures complètes (baseline) | 12 / 36 | 0 / 24 | 12 / 12 | 2 277 tokens |
| Noms seulement | 15 / 36 | 3 / 24 | 12 / 12 | 1 989 tokens |
| Aucune liste | 15 / 36 | 3 / 24 | 12 / 12 | 1 952 tokens |

D'où viennent les tokens des outils, pour le premier message :

| Prompt | Tokens |
|--------|--------|
| Sans aucun outil | 184 |
| Schéma JSON des outils envoyé à Ollama + règles d'utilisation | 1 952 |
| + liste des noms | 1 989 |
| + signatures complètes | 2 277 |

- Le schéma JSON natif (champ `tools` d'Ollama) pèse environ 1 770 tokens. Il est indispensable : c'est lui qui permet l'appel d'outils.
- La description en double dans le prompt système ne coûtait « que » 288 tokens, et n'apportait rien au modèle.

**Décision** : le prompt liste désormais les outils **par leur nom seulement** (`prompt.tools_listing: names`).

- 288 tokens de moins à chaque requête (-12,6 %).
- Aucune perte : mêmes résultats sur les demandes sans outil, et 3 réussites de plus sur les demandes avec outil.
  Ces 3 réussites correspondent à un seul cas (la recherche en mémoire) répété 3 fois : on ne les compte pas comme un gain de qualité.
- La liste des noms est gardée plutôt que rien : elle ne coûte que 37 tokens et indique au modèle quels outils existent.

Les trois modes restent disponibles : `prompt.tools_listing` dans `config.yaml`, ou `--tools-listing` en ligne de commande.

---

## Ce que les mesures révèlent aussi

- **Le modèle 2B appelle rarement les outils.** Sur les 24 demandes qui en exigent un,
  il en appelle au mieux 3, quelle que soit la description.
- **Il fait croire qu'il a agi.** Dans 18 à 21 de ces 24 cas, il ne déclenche aucun outil, mais répond comme si l'action était faite
  (« Email envoyé à alice@example.com », « Calendar event added successfully »).
  C'est une hallucination d'action : la confirmation des outils sensibles empêche les envois non voulus, mais pas ces fausses confirmations.
- **Les mêmes réglages ne donnent pas toujours le même résultat.** À température 0 et graine fixe,
  deux passages complets ont donné 3 / 5 puis 2 / 5 sur la mémoire. D'où les 3 répétitions.

---

## Prochaines améliorations à mesurer

Le même outil permet de les évaluer contre la version actuelle, qui devient la nouvelle baseline.

| Piste | Mesure attendue |
|-------|-----------------|
| Un modèle plus gros (7 à 8 milliards de paramètres) | Appels d'outils corrects et mémoire : `--model <nom>` |
| Ne pas proposer d'outils pendant la relance | Moins d'appels répétés, plus de réponses qui reprennent le résultat |
| Détecter les fausses confirmations d'action (réponse « envoyé » sans appel d'outil) | Taux d'hallucination d'action |

---

## Limites

- **Petit jeu de référence** : 22 cas. Il suffit pour voir des écarts de 40 points, pas des écarts de quelques points.
- **Un seul modèle**, petit (2B). Les taux absolus sont bas ; ce sont les écarts entre variantes qui comptent.
- **Critères par mots-clés** : une réponse juste mais formulée autrement (« la ville des Lumières » pour Lyon) est comptée comme un échec.
- **Baseline par réglage** : elle reproduit le comportement d'avant dans le code actuel.
  Les autres corrections faites depuis (paramètres de génération, prompt) s'appliquent aux deux variantes.

