# Audit VEOR → décision d'intégration au Guardian de WinCreator

Statut : **audit exécuté**, décision proposée, non encore implémentée.
Objet audité : `https://github.com/winterbim/veor` @ `87a6fb3` (master, clone jetable
`/tmp/veor-audit`, aucune modification poussée).

Ce document ne remplace aucune preuve : chaque résultat ci-dessous vient d'une
commande réellement exécutée le 2026-10-23, ou est explicitement étiqueté
« lecture de code, non exécuté ».

## 1. Méthode et résultats bruts

| Commande | Résultat réel | Verdict |
|---|---|---|
| `git clone --depth 50` | 129 fichiers, Node `v24.21.0`, npm `11.19.0` | exécuté |
| `npm ci` | `added 94 packages in 935ms` | exécuté |
| `npm test` | `tests 67 / pass 67 / fail 0`, 746 ms | CAPTURED_PASS |
| `npm run check` (syntaxe + tests) | 67/67, 649 ms | CAPTURED_PASS |
| `node src/cli.js sandbox-info` | `{platform:"linux", bwrap:true, seatbelt:false, docker:true, podman:false, strongestLocal:"bubblewrap"}` | exécuté |
| `node examples/self-demo.js` | ALLOW + DENY signés, vérif offline OK, tamper KO, `denyBlockedBeforeDownstream:true` | CAPTURED_PASS |
| `node src/cli.js verify receipt ... --public ...` | `{"ok":true,"checks":{"structure":true,"digest":true,"signature":true}}`, exit 0 | CAPTURED_PASS |
| Canonical JSON croisé Node/Python | hash identique `5be729bf…fd85` sur objet imbriqué + Unicode | CAPTURED_PASS |
| `npm view veor-runtime version` | `E404` — **non publié sur npm** | exécuté |

Deux constats de dérive documentaire, même classe que les catches WinCreator :

- `DEV_EVIDENCE.md` annonce « Current 0.4.0-dev.4 gate » et « 61/61 » alors que
  `package.json` est `0.4.0-dev.6` et que la suite réelle fait **67** tests ;
- `docs/SECURITY_MATRIX.md` titre encore `0.4.0-dev.1`.

Aucun audit de sécurité externe n'est revendiqué (`DEV_EVIDENCE.md` : PENDING).

## 2. Ce que VEOR fournit réellement (code, pas README)

| Capacité | Fichier(s) | Preuve exécutée |
|---|---|---|
| Décision déterministe `ALLOW/REVIEW/DENY`, ordre monotone, défaut deny | `src/decision.js`, `src/policy-bundle.js`, `src/kernel/decision-kernel.js` | tests « advisory can only tighten », « probabilistic safety cannot override deterministic denial », « missing capability grant fails closed » |
| Grants de capacité Ed25519 + fenêtre de validité + binding outil | `src/grants.js` | « tampering a grant payload invalidates its signature » |
| Approbation humaine one-shot Ed25519 (TTL, args digest, reviewer distinct, consommée) | `src/security/approval-store.js` | tests approval-store |
| Reçus d'exécution Ed25519 + canonicalisation JSON stricte | `src/security/receipt-signer.js`, `src/canonical.js` | self-demo + verify CLI exit 0 |
| Vérification offline tierce (digest + signature + ledger optionnel) | `src/security/receipt-verify.js` | `veor verify receipt` |
| Ledger hash-chaîné JSONL + tête externe | `src/security/persistent-ledger.js` | mutation / suppression milieu / troncature queue détectées |
| Passerelle MCP fail-closed + empreinte de catalogue + advisory qui ne peut que durcir | `src/mcp/gateway.js`, `catalog-guard.js`, `advisory-provider.js` | gateway + SDK tests, self-demo DENY avant downstream |
| Sandbox OS honnête (`bwrap`, Seatbelt, fallback process non isolé) | `src/sandbox/*` | `sandbox-info`, tests `osEnforced` seulement après démarrage réel |
| Secret broker + redaction | `src/security/secret-broker.js`, `redact.js` | secret vu par l'effet, absent du reçu et des logs |
| Failure guard (2 échecs identiques → escalade) | `src/failure-guard.js` | test dédié |

## 3. Correspondance avec le Guardian de WinCreator

Le Guardian doit répondre à : *cette action a-t-elle le droit d'exister ?*
WinCreator répond à : *cette affirmation est-elle prouvée ?* Les deux sont
orthogonaux et ne doivent pas se substituer l'un à l'autre.

| Besoin Guardian | Composant VEOR | Décision | Justification technique |
|---|---|---|---|
| Politique ALLOW/REVIEW/DENY déterministe, fail-closed, monotone | `policy-bundle.js` + `decision.js` + `decision-kernel.js` | **REUSE** (sidecar) | 67 tests verts, invariant de monotonie testé, zéro dépendance npm hors SDK MCP ; réécrire en Python créerait une deuxième autorité |
| Habilitation humaine one-shot | `approval-store.js`, `grants.js` | **REUSE** + **ADAPT** garde des clés | Ed25519, TTL, binding outil+args, reviewer distinct, consommation unique ; l'adaptation porte sur la garde des clés et le binding du `scope`, pas sur le code |
| Reçus d'exécution signés Ed25519 | `receipt-signer.js`, `receipt-verify.js` | **REUSE** | digest + signature vérifiables hors ligne ; canonicalisation **byte-identique** à `canonical_digest` WinCreator (mesuré) |
| Vérification tierce des reçus | `verify receipt` CLI | **REUSE** | sortie JSON stable, exit code exploitable comme gate |
| Ledger d'évidence hash-chaîné | `persistent-ledger.js` | **ADAPT** — ne pas adopter comme second ledger | duplique le journal SQLite de G01 ; pas de verrou fichier ; append O(n²) ; deux chaînes = deux vérités |
| Sandbox des gates/effets | `src/sandbox/*` | **REUSE** (phase ultérieure) | `osEnforced` n'est vrai qu'après démarrage effectif, `requireOsIsolation` fail-closed ; bwrap disponible sur cette machine, pas de backend Windows |
| Passerelle MCP + dérive de catalogue | `mcp/gateway.js`, `catalog-guard.js` | **REUSE** (phase 2, si MCP) | utile seulement quand le Guardian route des outils MCP ; pas nécessaire aux gates locales |
| Redaction avant persistance | `redact.js` | **ADAPT** (conception seule) | WinCreator rédige déjà avant hachage dans le kernel ; ne pas porter le JS |
| Two-Failure Rule | `failure-guard.js` | **ADAPT** (doctrine déjà présente) | WinCreator possède déjà la règle ; l'implémentation VEOR est en mémoire, non persistante — G01 fournit le journal persistant |
| Validation de schéma de politique | `policy-schema.js` | **REUSE** comme contrat | valide zéro-dépendance, interdit explicitement les champs de relâchement |

**Aucun composant ne justifie un REBUILD.** Le seul `REBUILD` candidat serait
Ed25519 en Python, où la stdlib ne fournit rien : c'est précisément l'argument
pour réutiliser le signataire VEOR plutôt que réimplémenter de la cryptographie.

## 4. Intégration modulaire proposée (sans fusionner les dépôts)

```
WinCreator (Python, stdlib)                     VEOR (Node ≥ 22, épinglé par SHA)
┌──────────────────────────────┐               ┌────────────────────────────────┐
│ harness runtime (G01)        │               │ veor-kernel (stdio JSON-lines) │
│  contracts / store / journal │  decide  ────► │  policy + grants + approvals   │
│  proofs (Proof Kernel v3)    │  receipt ────► │  canonical + Ed25519 signer    │
│  governance adapter (G02)    │  status  ◄──── │  sandbox descriptor            │
│  verifier (verify)           │               │ veor verify receipt (offline)  │
└──────────────────────────────┘               └────────────────────────────────┘
        │                                                    │
        └────────── reçu signé + digest de politique ────────┘
```

Règles de l'intégration :

1. **Une seule autorité de preuve** reste le Proof Kernel WinCreator. Un reçu VEOR
   `executed:true` avec `verified:null` n'est jamais un statut `EVIDENCED`.
2. **Une seule chaîne d'évidence** reste le journal SQLite de G01. La chaîne VEOR
   n'est conservée que si la passerelle VEOR est déployée ; sinon on ne garde que
   le reçu et son digest.
3. **Sidecar fail-closed** : si Node, VEOR ou le SHA épinglé manquent, le Guardian
   retourne `BLOCKED` (jamais `ALLOW` par défaut) ; le chemin de preuve reste
   utilisable sans VEOR.
4. **Aucune dépendance ajoutée au cœur** : le paquet `skill/wincreator` reste
   stdlib-only ; l'adaptateur vit hors du paquet et déclare sa dépendance.
5. **Épinglage** : SHA git + version Node dans `tools/veor-pin.json`, vérifiés par
   un gate CI qui clone et exécute `npm test` ; pas de submodule, pas de fork,
   pas de `npm install` implicite. VEOR n'étant pas publié (E404), un pin git est
   la seule option reproductible aujourd'hui.
6. **Isolation des clés** : la clé privée d'approbation ne doit pas être lisible
   par l'agent ; signature hors processus (autre utilisateur OS, agent externe,
   ou étape manuelle). Sinon l'approbation « humaine » n'est qu'un self-approval
   signé.

## 5. Liaison des preuves VEOR au Proof Ledger

Ordre réel des faits, sans inversion :

1. **Avant l'effet** — le Guardian demande `decide(tool,args)`. VEOR renvoie
   décision, raisons, `policyDigest`, et un challenge si `REVIEW`. Le JSON de
   décision est écrit dans `.harness/governance/<task>.decision.json` et bindé
   par le kernel WinCreator (`--file`) : il est haché **avant** l'exécution.
2. **Pendant l'effet** — le gate WinCreator s'exécute normalement et produit son
   attestation (inchangé).
3. **Après l'effet** — `receipt(decisionRecord, resultDigest, executed, verified,
   sandbox)` produit un reçu Ed25519. `resultDigest` = sha256 canonique de
   `{exit_code, stdout_sha256, stderr_sha256, attestation_digest}` : le reçu est
   donc lié à la preuve WinCreator par digest, sans recopier son contenu.
4. **Vérification réelle du reçu** — une commande `veor verify receipt` est
   elle-même capturée comme gate WinCreator (ligne de ledger dédiée). Le reçu
   n'est jamais déclaré valide sur la foi de sa présence : le code de sortie de
   son vérificateur est l'évidence.

Contraintes honnêtes de ce montage :

- l'attestation WinCreator ne peut pas binder un fichier créé **après** le gate ;
  c'est pourquoi la validité du reçu passe par un second gate réel, pas par une
  phrase dans la cellule Evidence ;
- un reçu prouve l'authenticité et le contenu de la traversée, pas la justesse
  sémantique de l'effet (`verified:null` côté gateway) ;
- `--ledger` VEOR ne peut pas être vérifié si le ledger VEOR n'est pas conservé :
  il faut le conserver ou renoncer explicitement à cette clause.

## 6. Failles et limitations relevées (avec statut d'observation)

| # | Constat | Statut | Impact Guardian | Adaptation |
|---|---|---|---|---|
| 1 | `ApprovalStore.verifyAndConsume` : lecture `consumed`, vérification, puis append — pas de verrou fichier | lecture de code, non exploité | deux processus simultanés peuvent consommer la même approbation (TOCTOU) | sérialiser par lock OS ou par le store SQLite WinCreator avant consommation |
| 2 | `challenge.scope` (digest de politique) est recopié dans le payload signé mais jamais comparé au digest courant | lecture de code | une approbation émise sous l'ancienne politique reste valide pendant son TTL | rejeter si `scope != policyDigest` courant |
| 3 | `PersistentLedger.append` : read-modify-write + `appendFileSync`, sans lock | lecture de code | deux gateways concurrents peuvent forker la chaîne | ne pas s'appuyer dessus en multi-agent ; journal G01 seul |
| 4 | `evidence/current/` est réécrit par les démos (observé pendant l'audit) | exécuté | une « preuve » peut être écrasée | archiver les artefacts hors zone mutable, digest dans le ledger |
| 5 | `DEV_EVIDENCE`/`SECURITY_MATRIX` dérivent de l'objet (61 vs 67, dev.4 vs dev.6) | exécuté | confiance documentaire | gate CI qui re-dérive les compteurs |
| 6 | `veor-runtime` absent du registre npm (E404) | exécuté | pas de garantie de version sémantique | pin git + test du SHA |
| 7 | Fallback process non isolé, aucun backend Windows | documenté + `sandbox-info` | « sandboxé » serait faux sous Windows | `requireOsIsolation` obligatoire dès que la politique l'exige |
| 8 | `ReceiptSigner.sign` : `{kind, keyId, ...receipt}` — un appelant peut écraser `kind`/`keyId` | lecture de code | reçu signé mais rejeté à la vérification (déni, pas forge) | ne jamais passer `kind`/`keyId` au signer ; valider à l'entrée |
| 9 | Pas de révocation, pas d'ancrage distant, pas d'audit externe | documenté | fenêtre de clé compromise non fermable | assumer et documenter ; rotation par pin de clé |
| 10 | `verified:null` sur la passerelle MCP | documenté | le reçu ne prouve pas l'effet | preuve fonctionnelle = gate WinCreator uniquement |
| 11 | Node ≥ 22 requis pour tout le governance | mesuré | dépendance d'exécution nouvelle | sidecar optionnel, cœur Python intact |
| 12 | Politique non signée (seul son digest est enregistré) | lecture de code | remplacement de politique visible mais non empêché | signer les bundles de politique avec la clé de l'autorité |

## 7. Décision

**REUSE** pour : policy kernel, grants, approbations one-shot, reçus Ed25519,
vérificateur offline, sandbox, catalogue MCP, schéma de politique.
**ADAPT** pour : binding approbation↔preuve WinCreator, conservation du ledger,
redaction (conception), failure guard (déjà couvert par G01).
**REBUILD** : aucun composant. **Ne pas fusionner les dépôts** ; sidecar épinglé,
protocole JSON-lines versionné, adaptateur Python mince hors paquet skill.

Conséquence immédiate : **G02 (Guardian) ne réimplémente ni politique ni
signature** ; il ajoute (a) l'adaptateur sidecar, (b) le binding décision/reçu au
runtime et au ledger, (c) les gates de vérification. G01 (runtime, SQLite,
journal, reprise) reste la base et n'est pas remis en cause par cet audit.

## 8. Décisions validées (2026-10-23)

1. **Node.js optionnel** via adaptateur : le cœur reste stdlib-only ; un
   sidecar épinglé porte la gouvernance → ADR
   [`0001`](adr/0001-veor-optional-sidecar.md).
2. **Clés d'approbation isolées du Builder** : signature hors processus, jamais
   dans le dépôt ni lisible par l'agent → ADR
   [`0003`](adr/0003-approval-key-custody.md).
3. **Reçus VEOR Ed25519, attestations WinCreator inchangées** : les deux
   artefacts restent distincts et sont liés par digest → ADR
   [`0004`](adr/0004-ed25519-receipts-vs-hmac-attestations.md) et
   [`0002`](adr/0002-single-proof-authority.md).
4. **Pin reproductible** : `tools/veor-pin.json` (SHA + version + plancher Node
   + entrypoint), vérifié par `tools/veor_check.py`, sans submodule ni npm.

État d'implémentation : **G02 PARTIAL / BLOCKED** — voir
[`G02_STATUS.md`](G02_STATUS.md). Aucune claim G02 n'est prouvée : la revue
Skeptic indépendante et la garde des clés restent des prérequis.
