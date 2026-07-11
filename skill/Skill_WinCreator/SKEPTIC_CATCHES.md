# Skeptic Catches — patterns capitalisés

| Date | Classe de trou | Comment il a été raté | Question qui l'aurait attrapé |
|------|----------------|----------------------|-------------------------------|
| 2026-07-11 | contradiction doc↔outil | la spec exigeait `\|` mais l'outil n'avait jamais été exécuté contre sa propre spec | "l'outil de vérification a-t-il été lui-même attaqué avec les entrées que sa doc prescrit ?" |
| 2026-07-11 | faux positifs rendant une gate inutilisable | le parser lisait TOUTES les tables du fichier, jamais testé hors cas idéal | "la gate mécanique survit-elle à un fichier réel, pas seulement à l'exemple de la doc ?" |
| 2026-07-11 | pseudo-évidence passant le seuil | MIN_EVIDENCE_LEN mesurait la longueur, pas la nature de la preuve | "l'évidence contient-elle une trace d'exécution, ou juste de la prose ?" |
| 2026-07-11 | enforcement asymétrique spec↔outil (PENDING) | la spec exige un command dans l'évidence PENDING ; l'outil ne l'imposait qu'à EVIDENCED → PENDING vague accepté, exit 0 | "chaque statut dont la spec impose un contenu est-il vérifié, ou seulement le plus visible ?" |
| 2026-07-11 | enforcement asymétrique spec↔outil (WAIVED) | la spec exige date+citation dans l'évidence WAIVED ; l'outil ne l'imposait pas → WAIVED sans date accepté, exit 0 | "la même règle 'must contain' de la spec est-elle appliquée à TOUS les statuts concernés ?" |
| 2026-07-11 | durcissement non propagé à une nouvelle surface | le schema-gating (fix B) du parser de ledger n'a jamais été porté au checker --catches de v2.1 → table étrangère comptée comme catch, exit 0 | "toute NOUVELLE surface exécutable hérite-t-elle des durcissements déjà acquis ailleurs ? (même méta-classe qu'EVO-001)" |
| 2026-07-11 | ligne ledger orpheline silencieusement ignorée | une ligne CLAIMED après une ligne vide sort de l'état in_ledger → jamais auditée, ledger lu CLEAN exit 0 (faux négatif : le pire cas — une claim non prouvée échappe) | "une ligne qui RESSEMBLE à une ligne de ledger mais tombe hors table est-elle signalée, ou disparaît-elle en silence ?" |
| 2026-07-11 | régression introduite PAR un patch, attrapée par le self-test | le fix EVO-002 a fait stripper un backtick de fin par `_clean`, tuant le marqueur d'une commande légitime → self-test 12/14 AVANT ship | "chaque patch relance-t-il la suite complète, ou fait-on confiance au changement isolé ?" |
