# 📘 Documentation SensAI

Bienvenue.

Cette documentation explique le projet **SensAI**.

Elle est écrite pour être **facile à lire**.

---

## 👓 Comment cette documentation est écrite

Elle suit des règles pour aider les personnes **dyslexiques**.

- Des phrases **courtes**.
- **Une idée** par ligne.
- Des **listes** plutôt que des paragraphes.
- Des **titres** clairs avec une icône.
- **Pas d'italique**. Pas de texte souligné.
- Les mots techniques sont expliqués dans le [Glossaire](08-glossaire.md).
- Les étapes sont **numérotées**.

> [!TIP]
> Pour un meilleur confort de lecture, dans votre éditeur :
> - Police : **OpenDyslexic**, **Lexend** ou **Atkinson Hyperlegible**.
> - Taille : 14 px ou plus.
> - Interligne : 1,5 ou plus.
> - Fond : crème ou gris clair, plutôt que blanc pur.

---

## 🗺️ Sommaire

Lisez les pages dans l'ordre si vous découvrez le projet.

| N° | Page | Ce que vous allez apprendre |
|----|------|-----------------------------|
| 1 | [Démarrage](01-demarrage.md) | Installer et lancer SensAI |
| 2 | [Architecture](02-architecture.md) | Comment le projet est organisé |
| 3 | [Mémoire](03-memoire.md) | Comment l'IA se souvient |
| 4 | [Modèles](04-modeles.md) | Les classes de données |
| 5 | [Wrapper](05-wrapper.md) | Les fonctions pour Gradio |
| 6 | [Terminal](06-terminal.md) | Les commandes `/help`, `/quit`… |
| 7 | [RapideAPI](07-rapideapi.md) | Le client HTTP |
| 8 | [Glossaire](08-glossaire.md) | Les mots techniques expliqués |
| 9 | [Problèmes connus](09-problemes-connus.md) | Ce qui reste à corriger |

---

## ⚡ SensAI en 5 lignes

1. SensAI est un **framework** pour discuter avec une **IA locale**.
2. L'IA tourne sur votre machine grâce à **Ollama**.
3. Les conversations sont **sauvegardées** dans une base de données.
4. L'IA a une **mémoire courte** (les derniers messages).
5. L'IA a une **mémoire longue** (les anciens messages, retrouvés par le sens).
