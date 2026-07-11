# Evolution Queue — WinCreator

Propositions d'évolution émises par `wincreator-retro-analyst` à partir de
patterns confirmés (≥2 occurrences datées sur ≥2 tâches dans
`skill/Skill_WinCreator/SKEPTIC_CATCHES.md`). Seul `wincreator-skill-surgeon`
applique une proposition, une boucle Meso à la fois, sous gate. Statuts :
QUEUED → APPLIED (version, date) | REJECTED (motif).

---

## EVO-001 — rendre la rétro-boucle elle-même machine-checkable (`--catches`)

- **Statut** : APPLIED (v2.1.0, 2026-07-11)
- **Pattern** : *self-verification gap — un artefact de vérification du skill
  est expédié sans être contrôlé contre sa propre spec / réalité / croissance.*
  Occurrences datées (SKEPTIC_CATCHES.md, 2026-07-11) :
  1. `contradiction doc↔outil` — l'outil jamais exécuté contre la spec qu'il prétend appliquer.
  2. `faux positifs rendant une gate inutilisable` — le parser jamais testé hors cas idéal.
  3. `pseudo-évidence passant le seuil` — le seuil mesurait la longueur, pas la nature de la preuve.
  **Note d'honnêteté (anti-bruit)** : au niveau des classes *étroites*, chacune
  n'apparaît qu'une fois → aucune ne serait « confirmée » isolément. Le pattern
  n'est confirmé qu'au niveau *généralisé* ci-dessus (3 occurrences d'un même
  méta-défaut : « le vérificateur n'a jamais été vérifié »). La proposition est
  donc émise sur cette généralisation, assumée explicitement — pas sur une
  récurrence étroite qui n'existe pas encore.
- **Cible** : `scripts/ledger_check.py` (+ mention 1 ligne dans SKILL.md Retro Loop)
- **Patch proposé** : ajouter un flag `--catches [chemin]` qui vérifie que le
  fichier de catches existe et est « vivant » — proxy stateless honnête :
  au moins une ligne de catch bien formée (date ISO + classe non vide). La
  rétro-boucle, jusqu'ici hors de portée de toute gate mécanique, devient
  elle-même machine-checkable. Ferme exactement le méta-défaut que le pattern nomme.
- **Coût** : +~30 lignes sur le script ; +1 phrase (~90 caractères) sur SKILL.md.
- **Test de véracité** : 2 nouveaux cas dans `--self-test` (catches sain → ok ;
  catches vide/malformé → détecté) ; démonstration RED (flag absent en v2.0.0 →
  exit 2) puis GREEN (flag présent → exit 0 sur le vrai fichier, exit 1 sur un
  fichier vide).
