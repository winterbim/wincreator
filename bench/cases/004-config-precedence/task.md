# Task 004 — configuration precedence

Fix `resolve(defaults, file_cfg, env)` in `config.py`.

Contract:
- start from keys present in `defaults` only;
- precedence is environment > file_cfg > defaults;
- environment keys are `APP_<UPPERCASE_KEY>`;
- unknown file/environment keys are ignored;
- environment strings are coerced from the type of the default:
  - bool accepts true/false/1/0/yes/no (case-insensitive), otherwise `ValueError`;
  - int uses base-10 `int`;
  - str remains a string;
- inputs must not be mutated;
- keep the public function name/signature and use only the standard library.

Do not inspect files outside the workspace.
