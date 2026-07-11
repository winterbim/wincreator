# Skeptic Catches — patterns capitalisés

| Date | Classe de trou | Comment il a été raté | Question qui l'aurait attrapé |
|------|----------------|----------------------|-------------------------------|
| 2026-07-11 | contradiction doc↔outil | la spec exigeait `\|` mais l'outil n'avait jamais été exécuté contre sa propre spec | "l'outil de vérification a-t-il été lui-même attaqué avec les entrées que sa doc prescrit ?" |
| 2026-07-11 | faux positifs rendant une gate inutilisable | le parser lisait TOUTES les tables du fichier, jamais testé hors cas idéal | "la gate mécanique survit-elle à un fichier réel, pas seulement à l'exemple de la doc ?" |
| 2026-07-11 | pseudo-évidence passant le seuil | MIN_EVIDENCE_LEN mesurait la longueur, pas la nature de la preuve | "l'évidence contient-elle une trace d'exécution, ou juste de la prose ?" |
