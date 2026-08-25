# WinCreator v3.0.1

Close-out after the 2026-08-25 audit.

- waiting is not a freeze: re-check `PENDING`/`BLOCKED` before closing a loop;
- CI runs `--catches` on the live `SKEPTIC_CATCHES.md`;
- scripts read `VERSION` from the package file;
- operator surfaces (surgeon, CLAUDE.md, CONTRIBUTING) match the 8-status v3 protocol.

Install remains one command:

```bash
npx skills add winterbim/wincreator
```

Or migrate a local v1/v2 Claude install:

```bash
python3 tools/migrate_v2_to_v3.py
```

See `README.md` for capture/review, HMAC limits, and development gates.
