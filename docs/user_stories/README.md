# 📖 User stories

Cette page regroupe les user stories de chaque fonctionnalité implémentée.

Le sujet demande **au moins deux user stories par fonctionnalité**, au format :

> En tant que [utilisateur], je veux [action], afin de [résultat].

Chaque fiche contient :

- ce que demande le sujet ;
- ce que fait SensAI ;
- les user stories, avec leurs **critères d'acceptation** ;
- les **tests** qui vérifient chaque critère ;
- les **limites** connues.

Une case cochée `[x]` est vérifiée par un test automatisé.
Une case vide `[ ]` reste à faire.

[⬅️ Retour au sommaire](../README.md)

---

## 🗂️ Fonctionnalités implémentées

| Fiche | Catalogue | Statut |
|-------|-----------|--------|
| [Socle MVP](00-socle-mvp.md) | Chatbot CLI, streaming, historique, erreurs, choix du modèle | ✅ Fait |
| [M1 : Persistance et profils](M1-persistance-profils.md) | Mémoire et contexte | ✅ Fait |
| [R1 : RAG basique](R1-rag-basique.md) | RAG | 🟡 Partiel |
| [T1 : Appel d'outils](T1-appel-outils.md) | Outils et exécution | ✅ Fait |
| [A3 : Human-in-the-loop](A3-human-in-the-loop.md) | Orchestration | ✅ Fait (CLI) |
| [EV1 : Évaluation automatique](EV1-evaluation-automatique.md) | Évaluation et sécurité | 🟡 Partiel |
| [EV2 : Guardrails](EV2-guardrails.md) | Évaluation et sécurité | 🟡 Partiel |
| [EV3 : Monitoring](EV3-monitoring.md) | Évaluation et sécurité | 🟡 Partiel |
| [X1 : Interface web](X1-interface-web.md) | Expérience utilisateur | ✅ Fait |
| [X5 : Planification](X5-planification.md) | Expérience utilisateur | 🟡 Partiel |

---

## ⬜ Fonctionnalités non implémentées

Elles n'ont pas de user stories : le sujet en demande pour les fonctionnalités **implémentées**.

M2, M3, M4, T2, T3, T4, T5, R2, A1, A2, A4, A5, A6, A7, EV4, X2, X3, X4.

> [!NOTE]
> Pour ajouter une fiche, copiez une fiche existante et gardez la même structure.
> Ajoutez-la ensuite dans le tableau ci-dessus et dans `USER_STORIES.md` à la racine.
