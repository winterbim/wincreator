# CLAUDE.md — wincreator repository

The skill lives in `skill/Skill_WinCreator/`. Paths below are relative to
that skill root unless stated otherwise; project-level machinery
(`.claude/agents/`, `EVOLUTION_QUEUE.md`, this file) lives at the repo root.

## WinCreator — boucle d'évolution active

- Toute tâche non triviale suit skill-wincreator (classification, gate annoncée, Panel).
- Chaque claim est validée par le subagent `wincreator-skeptic` (jamais d'auto-notation).
- À chaque verdict INSUFFICIENT et à chaque fermeture de boucle Meso+ : invoquer `wincreator-retro-analyst`.
- Quand EVOLUTION_QUEUE.md contient ≥1 proposition avec pattern confirmé, OU tous les 10 catches, OU sur demande : invoquer `wincreator-skill-surgeon` (une proposition = une boucle Meso).
- Jamais de réécriture du skill hors de ce circuit. Les invariants (4 statuts, Builder/Skeptic, no-upward-propagation, Two-Failure) ne bougent qu'avec waiver explicite de l'utilisateur.

### Fichiers de la boucle (chemins réels dans ce dépôt)

- Catches capitalisés : `skill/Skill_WinCreator/SKEPTIC_CATCHES.md`
- File de propositions : `EVOLUTION_QUEUE.md` (racine du dépôt)
- Gate mécanique : `python3 skill/Skill_WinCreator/scripts/ledger_check.py`
  (`--self-test` avant de faire confiance à la gate)

La chaîne complète : **usage réel → catch (Skeptic) → capitalisation
(Retro-Analyst) → récurrence prouvée → proposition → chirurgie gated
(Surgeon) → skill vN+1 → usage réel**. La télémétrie de l'amélioration,
c'est `SKEPTIC_CATCHES.md` : pas de catches, pas d'évolution.
