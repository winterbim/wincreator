# Gabarit — Loop Ticket

À utiliser pour toute tâche Méso ou Macro non triviale, dans n'importe quel domaine, pour garder une trace honnête de ce qui est prouvé vs supposé.

```
## Loop Ticket — [nom court de la tâche]

Niveau: Macro (Exploration | Décision) | Méso | Micro
Domaine: (ex: backend, frontend, data, infra, BIM, hardware, ops...)
Date:

### Objectif de la boucle
(une phrase, vérifiable)

### Gate de vérité choisie
(quelle preuve concrète établira le succès — décidée AVANT de commencer)

### Itérations

| # | Action | Preuve exécutée | Résultat brut | Gate passée ? |
|---|--------|------------------|----------------|----------------|
| 1 |        |                  |                | oui/non        |
| 2 |        |                  |                | oui/non        |

### Décision finale
Remontée au niveau parent avec: (ce qui est réellement prouvé, sans enjolivement)

### Dette explicite restante (si gate partiellement échouée)
(ne jamais masquer — lister ce qui reste non prouvé)
```

## Exemple rempli (illustratif, domaine backend)

```
## Loop Ticket — Endpoint de génération de rapport

Niveau: Méso
Domaine: backend

### Objectif de la boucle
L'endpoint /report génère un rapport conforme pour tous les cas actifs du jeu de données réel.

### Gate de vérité choisie
Génération réelle sur le jeu de données complet + comparaison avec 3 cas témoins connus.

### Itérations
| # | Action | Preuve exécutée | Résultat brut | Gate passée ? |
|---|--------|------------------|----------------|----------------|
| 1 | Implémentation initiale | Exécution sur jeu de test réduit | 2 champs manquants détectés | non |
| 2 | Correction du mapping | Régénération + comparaison 3 cas témoins | Concordance 100% | oui |

### Décision finale
Endpoint prouvé fonctionnel sur les cas témoins et le jeu complet.

### Dette explicite restante
Aucune sur le périmètre testé. Non testé: cas ajoutés après la date de vérification.
```
