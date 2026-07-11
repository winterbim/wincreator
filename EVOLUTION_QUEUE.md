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

## EVO-004 — ligne ledger orpheline (faux négatif HIGH)

- **Statut** : APPLIED (v2.4.0, 2026-07-11)
- **Pattern** : *faux négatif structurel — une ligne de ledger valide sort de
  l'état de parsing et échappe à l'audit.* Découvert par le red-team du cycle 2
  sur v2.3.0. Reproduit : `c1_orphan.md` (ligne CLAIMED après ligne vide) →
  `LEDGER CLEAN` exit 0 ; même ligne sans la ligne vide → exit 1. Le pire cas
  possible pour cet outil : une claim non prouvée passe.
- **Cible** : `scripts/ledger_check.py`
- **Patch** : `_looks_like_ledger_row` — une ligne à ≥6 cellules dont la col 5
  est un statut valide, apparaissant HORS d'une table reconnue, est signalée
  (détachée par une ligne vide, ou orpheline par faute de frappe du header).
  La règle « ligne vide = fin de table » (isolation des tables étrangères,
  fix B) est préservée : une table étrangère n'a jamais de statut ledger en
  col 5 (prouvé par le self-test `foreign_6col_not_orphan`).
- **Test de véracité** : self-test `orphan_ledger_row_caught` (caught) +
  `foreign_6col_not_orphan` (clean) ; suite 14 → 16.

## EVO-005 — durcissement parser (Two-Failure escalade depuis EVO-004)

- **Statut** : APPLIED (v2.5.0, 2026-07-11)
- **[AUDIT]** 2 échecs de l'heuristique orpheline au niveau ligne (EVO-004
  shippé au cycle 2 ; cycle 3 : faux positif BUG1 + faux négatifs BUG2/BUG3)
  → la cause vivait un niveau au-dessus : le parser n'était pas conscient des
  frontières de table ni des blocs code. Escalade Micro → Meso, conforme à la
  Two-Failure Rule.
- **Défauts corrigés (tous reproduits avant/après)** :
  - BUG1 (faux positif HAUTE, régression d'EVO-004) : table étrangère avec
    colonne "Status" → ledger valide rejeté. Fix : suivi header+séparateur ;
    les lignes sous un header non-ledger sont ignorées (fix B restauré).
  - BUG2 (faux négatif) : orphelin à 5 cellules raté. Fix : orphan gate ≥5.
  - BUG4 (faux positif) : exemple ledger dans un bloc ``` parsé (+ landmine :
    la spec elle-même mal parsée). Fix : saut des fences ``` / ~~~.
  - MINOR5 : table --catches à 3 colonnes lue STALE. Fix : ligne catch ≥2 cell.
- **Limite documentée (PAS un code-fix)** : BUG3 — ligne sans pipe de bord
  droppée. Ajouter une heuristique pour la rattraper reproduirait la fragilité
  d'EVO-004 ; consignée comme exigence de format dans proof-ledger.md.
- **Test de véracité** : 4 nouveaux self-tests + 4 fichiers red-team rejoués
  (BUG1→CLEAN, BUG2→exit1, BUG4→CLEAN, spec doc→exit2) ; suite 16→20.

## EVO-006 — DÉCLINÉE (décision de niveau, pas un bug non corrigé)

- **Statut** : DECLINED (décision Macro, 2026-07-11), consignée avant tout patch.
- **Trouvaille (réelle, reproduite par le Skeptic sur v2.5.0)** : une ligne
  CLAIMED collée SANS ligne vide sous une table étrangère est avalée comme
  ligne de cette table → `LEDGER CLEAN` exit 0 (faux négatif). Miroir exact du
  faux positif qu'EVO-004 avait créé et qu'EVO-005 a corrigé.
- **[AUDIT] Two-Failure (étape 2 — la gate est-elle la bonne ?)** : EVO-004 a
  échoué comme faux positif, EVO-005 comme faux négatif symétrique. La
  distinction "ligne détachée du ledger" vs "ligne d'une autre table" est
  **indécidable à partir d'une seule ligne**. Ajouter une 3e heuristique
  positionnelle rééchangerait un faux contre son opposé — fragilité, pas
  fiabilité.
- **Décision** : NE PAS coder de nouveau patch. Documenter la limite (fait,
  proof-ledger.md), garder le Skeptic comme backstop (rôle explicitement prévu
  par la doctrine), et respecter l'invariant : *un système auto-modifiant qui
  peut ajouter de la fragilité à ses propres gates ne doit pas le faire sans
  raison prouvée.* La convergence ici n'est pas "plus de bugs" mais "ce défaut
  est intrinsèque à une gate structurelle ; le bon remède est écrit, pas codé".

## Différé (loggé, PAS opéré ce cycle — retenue délibérée)

- **Header ledger « tout ou rien »** : une faute de frappe dans une colonne du
  header rend TOUT le ledger invisible (`no ledger table found`, exit 2).
  Fail-safe (non-zero, pas de faux-clean) mais diagnostic trompeur. Non corrigé :
  ajoute de la complexité pour un gain fail-safe ; à reprendre si ça récidive.
  Le noter ici est la doctrine : un catch isolé se logge, il ne déclenche pas
  une chirurgie.
