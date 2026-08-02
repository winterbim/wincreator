# CLAUDE.md — wincreator repository

The skill lives in `skill/wincreator/`. Paths below are relative to
that skill root unless stated otherwise; project-level machinery
(`.claude/agents/`, `EVOLUTION_QUEUE.md`, this file) lives at the repo root.

## WinCreator — boucle d'évolution active

- Toute tâche non triviale suit wincreator (classification, gate annoncée, Panel).
- Chaque claim est validée par le subagent `wincreator-skeptic` (jamais d'auto-notation).
- À chaque verdict INSUFFICIENT et à chaque fermeture de boucle Meso+ : invoquer `wincreator-retro-analyst`.
- Quand EVOLUTION_QUEUE.md contient ≥1 proposition avec pattern confirmé, OU tous les 10 catches, OU sur demande : invoquer `wincreator-skill-surgeon` (une proposition = une boucle Meso).
- Jamais de réécriture du skill hors de ce circuit. Les invariants (les 7 statuts, Builder/Skeptic, no-upward-propagation, Two-Failure) ne bougent qu'avec waiver explicite de l'utilisateur. Le passage de 4 à 7 statuts (`DISPROVEN`, `SUPERSEDED`, `BLOCKED`) est couvert par le waiver de l'audit utilisateur du 2026-08-02.
- Une preuve se capture, elle ne se raconte pas : dès qu'une commande est exécutable, utiliser `wincreator.py prove <ID> -- <commande>` plutôt qu'écrire la cellule Evidence à la main.

### Fichiers de la boucle (chemins réels dans ce dépôt)

- Catches capitalisés : `skill/wincreator/SKEPTIC_CATCHES.md`
- File de propositions : `EVOLUTION_QUEUE.md` (racine du dépôt)
- Gate mécanique : `python3 skill/wincreator/scripts/ledger_check.py`
  (`--self-test` avant de faire confiance à la gate)
- Capture de preuve : `python3 skill/wincreator/scripts/wincreator.py prove`
  puis `verify` (`--self-test` avant de faire confiance à la capture)
- Conformité du package : `python3 skill/wincreator/scripts/package_check.py skill/wincreator`

La chaîne complète : **usage réel → catch (Skeptic) → capitalisation
(Retro-Analyst) → récurrence prouvée → proposition → chirurgie gated
(Surgeon) → skill vN+1 → usage réel**. La télémétrie de l'amélioration,
c'est `SKEPTIC_CATCHES.md` : pas de catches, pas d'évolution.
