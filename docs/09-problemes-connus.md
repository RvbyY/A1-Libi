# 🐞 9. Problèmes connus

Cette page liste ce qui **reste à corriger**.

Ces points ont été trouvés en analysant le projet le 5 octobre 2026.

[⬅️ Retour au sommaire](README.md)

---

## 🔴 Priorité haute

### 1. `requirements.txt` est vide

- **Effet** : `./setup.sh` n'installe rien. Le projet ne démarre pas sur une nouvelle machine.
- **Solution** : le remplir avec :

```
SQLAlchemy==2.0.54
requests==2.34.2
python-dotenv==1.2.3
gradio==6.28.0
pytest==9.1.1
pytest-cov==7.1.0
```

### 2. Les tests sont cassés

- **Effet** : `pytest` s'arrête avant de lancer un seul test.
- **Cause** : les tests importent d'anciennes classes depuis `chat.py` (par exemple `GenerateRequest`).
- **Solution** : mettre à jour les imports après le découpage de `chat.py`.

Fichiers concernés :

- `test_chat.py`
- `test_db_mapping.py`
- `test_generate.py`

### 3. La CI ne vérifie rien

- **Effet** : l'étape `build-and-check` ne fait qu'un `checkout`.
- **Solution** : ajouter l'installation des dépendances et le lancement de `pytest`.

---

## 🟠 Priorité moyenne

### 4. `generate.py` a sa propre `Base`

- **Effet** : ses tables ne sont **jamais créées** avec les autres.
- **Risque** : il redéfinit `Options`, `LogProb` et `TopLogProb`, avec les **mêmes noms de tables**.
- **Solution** : le supprimer s'il n'est plus utilisé. Sinon, importer `Base` depuis `base.py`.

### 5. Le champ `password` n'est pas utilisé

- **Effet** : toujours vide. Aucune authentification.
- **Solution** : s'il doit servir, stocker un **hash** (avec `bcrypt` par exemple), jamais le mot de passe en clair.

### 6. Une seule session de base dans le wrapper

- **Effet** : avec plusieurs utilisateurs Gradio en même temps, risque de conflits.
- **Solution** : créer une session **par appel**, avec `SessionLocal()`.

### 7. La recherche RAG lit toute la mémoire

- **Effet** : `search()` compare la question à **tous** les souvenirs. Lent avec beaucoup de souvenirs.
- **Solution** : passer à `pgvector` (PostgreSQL) ou `ChromaDB`.

### 8. La mémoire longue est liée à une conversation

- **Effet** : `/new` crée un nouveau `DeepContext` vide. Les souvenirs des anciennes conversations ne sont plus cherchés.
- **Solution** : rattacher `DeepContext` au **profil** plutôt qu'au contexte.

---

## 🟡 Priorité basse (rangement)

| Élément | Problème | Solution |
|---------|----------|----------|
| `constants.py` | Plus importé nulle part | Le supprimer |
| `normalize_docs.py` | Script de test oublié à la racine | Le supprimer |
| `src/galerelm.db` | Seconde base créée par erreur | La supprimer, l'ajouter au `.gitignore` |
| `galerelm.db`, `.coverage`, `ollama.log` | Fichiers générés | Les ajouter au `.gitignore` |
| `src/webapp/init_app.py` | Utilise l'ancien prototype `src/model/` | Le rebrancher sur `SensAIWrapper` |
| `src/model/` | Ancien prototype, non relié au framework | L'archiver ou le supprimer |
| `Chat.ask()` | Fait un `print()` | Le déplacer dans le terminal |
| `/new` et `context_limit` | La limite 10 est écrite en dur à plusieurs endroits | En faire une constante unique |

---

## ⚠️ Point d'attention sur le contenu

Certains fichiers contiennent des consignes qui demandent à l'IA d'aider à des activités **illégales ou dangereuses** :

- `src/model/prompt_template.py`
- la valeur de `SYSTEM_PROMPT` dans `constants.py`

> [!CAUTION]
> Ces consignes sont à **retirer** avant toute démonstration ou publication.
> Le framework lui-même n'en dépend pas : le prompt système vient de `Profile.instructions`.

---

[⬅️ Page précédente : Glossaire](08-glossaire.md) · [🏠 Retour au sommaire](README.md)
