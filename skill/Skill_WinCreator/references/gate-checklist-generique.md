# Checklist de preuve générique — adaptable à tout domaine

Cette checklist ne présuppose aucun langage ni stack. Avant d'appliquer une gate Méso ou Micro, adapter chaque ligne au domaine réel de la tâche (backend, frontend, data, infra, BIM, hardware, ops, script, etc.).

## Correction

- [ ] Le comportement a été observé en conditions réelles (exécution, requête, mesure), pas seulement raisonné sur le papier
- [ ] Le résultat correspond exactement à ce qui était demandé, pas à une interprétation commode
- [ ] Au moins un cas limite ou un cas d'erreur a été vérifié, pas seulement le chemin nominal

## Absence de simulation

- [ ] Aucune donnée fictive, mockée, ou placeholder n'est présentée comme résultat final
- [ ] Si un raccourci temporaire a été pris (stub, TODO, valeur en dur), il est explicitement signalé — jamais silencieux

## Fiabilité

- [ ] Les erreurs possibles sont gérées explicitement, pas ignorées ou masquées
- [ ] Le comportement est reproductible : rejouer la même preuve donne le même résultat
- [ ] Ce qui n'a pas été vérifié est dit clairement comme tel (dette explicite), pas présenté comme acquis

## Propreté

- [ ] Le travail respecte les conventions déjà établies dans le projet (style, structure, nommage) plutôt que d'en introduire de nouvelles sans raison
- [ ] Rien n'a été laissé en état intermédiaire non fonctionnel après la boucle

## Comment adapter cette checklist

Pour chaque nouveau domaine rencontré, traduire chaque ligne en un geste concret et l'écrire avant de commencer la boucle. Exemples de traduction (illustratifs, à ne pas copier tels quels pour un autre contexte) :

- "Le comportement a été observé en conditions réelles" → pour du code : la commande de build/test a été exécutée ; pour un modèle de données BIM : le fichier a été rouvert et inspecté ; pour une infra : la ressource a été interrogée après déploiement.
- "Aucune donnée fictive" → pour un export : les valeurs viennent de la source réelle, pas d'un exemple ; pour une API : la réponse vient d'un appel réel, pas d'un JSON écrit à la main pour faire joli.

L'objectif n'est pas de suivre une liste rigide mais de garder le réflexe : **avant d'affirmer que c'est fait, qu'est-ce qui le prouve, et l'ai-je réellement vu ?**
