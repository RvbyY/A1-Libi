# 🧠 3. La mémoire

Cette page explique comment l'IA **se souvient**.

[⬅️ Retour au sommaire](README.md)

---

## 🎯 Le problème

Une IA ne peut lire qu'une **quantité limitée** de texte à la fois.

Si on lui envoie toute la conversation, elle finit par **saturer**.

---

## 💡 La solution : deux mémoires

| | 🟢 Mémoire courte | 🔵 Mémoire longue |
|---|---|---|
| **Classe** | `Context` | `DeepContext` |
| **Contenu** | Les derniers messages | Tous les anciens messages |
| **Taille** | 10 messages (réglable) | Sans limite |
| **Envoyée à l'IA ?** | Oui, en entier | Non, seulement les 3 souvenirs les plus utiles |
| **Recherche** | Par ordre d'arrivée | Par le **sens** |

Image pour retenir :

- 🟢 La mémoire courte, c'est **votre bureau**. Seulement ce qui sert maintenant.
- 🔵 La mémoire longue, c'est **la bibliothèque**. On y va chercher un livre précis.

---

## 🟢 La mémoire courte (`Context`)

### Comment elle marche

1. Chaque message est ajouté avec `context.add(message)`.
2. Elle compte les messages.
3. S'il y en a **plus de 10**, elle retire les plus vieux.
4. Les messages retirés partent dans la mémoire longue.

### Exemple avec une limite de 4

```
Avant :  [ A, B, C, D ]        ← plein
Ajout :  [ A, B, C, D, E ]     ← 5, trop !
Après :  [ B, C, D, E ]        ← A part en mémoire longue
```

---

## 🔵 La mémoire longue (`DeepContext`)

### Étape 1 : Transformer le texte en nombres

Chaque message archivé est transformé en **vecteur**.

Un vecteur, c'est une **liste de nombres** qui représente le **sens** du texte.

```
"J'habite à Paris"   →  [0.12, -0.48, 0.91, ...]   (768 nombres)
```

Ce travail est fait par le modèle `nomic-embed-text`, via Ollama.

> [!NOTE]
> Deux phrases au **sens proche** donnent des vecteurs **proches**.
> Même si les mots sont différents.

### Étape 2 : Chercher par le sens

Quand vous posez une question :

1. La question est transformée en vecteur.
2. Ce vecteur est comparé à **tous** les souvenirs.
3. La comparaison donne un **score** entre 0 et 1.
4. Les **3 meilleurs** scores sont gardés.

| Score | Signification |
|-------|---------------|
| proche de **1** | Même sens |
| proche de **0** | Aucun rapport |

Ce calcul s'appelle la **similarité cosinus**.

### Étape 3 : Donner les souvenirs à l'IA

Les souvenirs sont ajoutés aux **instructions** de l'IA :

```
Tu es SensAI, un assistant intelligent et concis.

Voici des informations pertinentes issues de conversations précédentes :
- [user] J'habite à Paris
- [assistant] Noté, vous habitez à Paris.
```

Cette technique s'appelle le **RAG**.

Le code se trouve dans `SensAI._build_augmented_prompt()`.

---

## 🛟 Si Ollama ne répond pas

SensAI ne plante pas.

- Les messages sont **quand même archivés**.
- Mais leur vecteur est **vide**.
- Ces souvenirs ne seront **jamais retrouvés** par la recherche.

C'est le **mode dégradé**.

> [!WARNING]
> Les souvenirs archivés en mode dégradé ne sont pas vectorisés plus tard.
> Pour l'instant, il n'existe pas de fonction pour les réparer.

---

## 💾 Ce qui est sauvegardé

Tout est dans `galerelm.db`.

| Table | Contenu |
|-------|---------|
| `profiles` | Les utilisateurs |
| `contexts` | Les conversations |
| `messages` | Les messages de la mémoire courte |
| `deep_contexts` | Un par conversation |
| `long_term_memories` | Les souvenirs, avec leur vecteur |

Quand vous relancez SensAI :

- La mémoire courte est **rechargée**.
- La mémoire longue est **rechargée**.
- L'IA se souvient donc des conversations passées.

---

## 🔍 Vérifier la mémoire

Dans le terminal :

| Commande | Effet |
|----------|-------|
| `/messages` | Voir la mémoire courte |
| `/memories` | Voir la mémoire longue |
| `/recall Paris` | Chercher "Paris" par le sens |
| `/payload` | Voir exactement ce qui est envoyé à l'IA |

---

[⬅️ Page précédente : Architecture](02-architecture.md) · [➡️ Page suivante : Modèles](04-modeles.md)
