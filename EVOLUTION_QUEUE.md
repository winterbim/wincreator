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

---

## EVO-002 — enforcement symétrique des règles d'évidence par statut (PENDING/WAIVED)

- **Statut** : APPLIED (v2.2.0, 2026-07-11)
- **Pattern CONFIRMÉ** : *enforcement asymétrique spec↔outil* — la règle « must
  contain » de `references/proof-ledger.md` était appliquée au seul statut
  EVIDENCED. Occurrences datées (SKEPTIC_CATCHES.md, 2026-07-11), 2 sur 2
  statuts distincts → confirmé sans généralisation :
  1. PENDING sans command accepté (`LEDGER CLEAN` exit 0 sur ledger spec-invalide).
  2. WAIVED sans date accepté (idem).
  Reproduit : `b1_pending.md`/`b2_waived.md` → exit 0 (attendu non-zero).
- **Cible** : `scripts/ledger_check.py` (+ `references/proof-ledger.md` "Known limits")
- **Patch** : dans `check_text`, exiger un EXEC_MARKER pour PENDING (proxy du
  « command ») et une date ISO pour WAIVED (proxy du « date »). Documenter ces
  règles dans la spec pour ne PAS recréer une contradiction doc↔outil.
- **Test de véracité** : 3 nouveaux SELF_TESTS (PENDING sans command → caught,
  WAIVED sans date → caught, WAIVED avec date → clean) ; les exemples
  spec-valides PENDING/WAIVED restent CLEAN (garde-fou anti-faux-positif).

## EVO-003 — porter le schema-gating au checker `--catches`

- **Statut** : APPLIED (v2.3.0, 2026-07-11)
- **Pattern CONFIRMÉ** : *durcissement non propagé à une nouvelle surface* —
  même méta-classe qu'EVO-001 (« un vérificateur expédié sans être vérifié »),
  ici récurrente : le fix B (schema-gating) du parser de ledger n'a jamais été
  porté à `check_catches_text`. Occurrence datée 2026-07-11 + lignée EVO-001.
  Reproduit : `b3_foreign.md` → `CATCHES ALIVE` exit 0 sur une table étrangère.
- **Cible** : `scripts/ledger_check.py`
- **Patch** : `check_catches_text` ne compte que les lignes situées SOUS un
  header de catches (`Date | Class(e)…`), miroir de `_is_ledger_header`.
- **Test de véracité** : 1 nouveau CATCH_TEST (table étrangère avec date ISO →
  STALE) ; le vrai `SKEPTIC_CATCHES.md` reste ALIVE.

## Différé (loggé, PAS opéré ce cycle — retenue délibérée)

- **Header ledger « tout ou rien »** : une faute de frappe dans une colonne du
  header rend TOUT le ledger invisible (`no ledger table found`, exit 2).
  Fail-safe (non-zero, pas de faux-clean) mais diagnostic trompeur. Non corrigé :
  ajoute de la complexité pour un gain fail-safe ; à reprendre si ça récidive.
  Le noter ici est la doctrine : un catch isolé se logge, il ne déclenche pas
  une chirurgie.
