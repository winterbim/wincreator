#!/usr/bin/env python3
"""Render the false-green demo transcript as an animated terminal SVG.

    python3 tools/render_demo_svg.py            # rewrite docs/assets/false-green.svg
    python3 tools/render_demo_svg.py --check    # fail if the committed SVG is stale

The SVG is generated from what `examples/false-green/run_demo.py` really prints,
so the README hero cannot drift from the tool's behavior. Pure stdlib, no
recording tool, no raster: lines fade in with CSS, and readers who prefer
reduced motion get the full static transcript.
"""
from html import escape
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "examples" / "false-green" / "run_demo.py"
OUT = ROOT / "docs" / "assets" / "false-green.svg"

WIDTH = 820
LINE_HEIGHT = 21
TOP = 58
LEFT = 24
STEP_SECONDS = 0.8
HOLD_SECONDS = 9.0


def demo_lines():
    result = subprocess.run(
        [sys.executable, str(DEMO)], capture_output=True, text=True, check=True, cwd=ROOT
    )
    return result.stdout.rstrip("\n").split("\n")


def css_class(line):
    stripped = line.strip()
    if stripped.startswith("VERDICT INSUFFICIENT"):
        return "bad"
    if stripped.startswith("VERDICT ADEQUATE"):
        return "good"
    if stripped.startswith("$ "):
        return "cmd"
    if stripped.startswith("CLAIM"):
        return "claim"
    if line.startswith("        ") or stripped.startswith("seed the bug"):
        return "note"
    return "out"


def render(lines):
    visible = [(index, line) for index, line in enumerate(lines) if line.strip()]
    total = len(visible) * STEP_SECONDS + HOLD_SECONDS
    height = TOP + len(lines) * LINE_HEIGHT + 22
    rules, texts = [], []
    for order, (index, line) in enumerate(visible):
        start = 100 * (order * STEP_SECONDS) / total
        shown = min(start + 1.2, 97.0)
        rules.append(
            f"@keyframes l{order} {{ 0%, {start:.2f}% {{ opacity: 0; }} "
            f"{shown:.2f}%, 97% {{ opacity: 1; }} 100% {{ opacity: 0; }} }}\n"
            f"      .l{order} {{ animation: l{order} {total:.2f}s linear infinite; }}"
        )
        y = TOP + index * LINE_HEIGHT
        texts.append(
            f'  <text x="{LEFT}" y="{y}" class="m {css_class(line)} l{order}" '
            f'xml:space="preserve">{escape(line)}</text>'
        )
    style = "\n      ".join(rules)
    body = "\n".join(texts)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" role="img" aria-labelledby="title desc">
  <title id="title">A green test that proves nothing, caught by WinCreator</title>
  <desc id="desc">Terminal transcript: a check passes, the bug the claim is about is seeded and the check still passes, so the verdict is INSUFFICIENT. One added check kills the fault and the verdict becomes ADEQUATE.</desc>
  <defs>
    <style>
      .m {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace; font-size: 14px; }}
      .cmd {{ fill: #f8fafc; font-weight: 600; }}
      .out {{ fill: #cbd5e1; }}
      .note {{ fill: #7c8aa0; }}
      .claim {{ fill: #7dd3fc; font-weight: 600; }}
      .bad {{ fill: #fb7185; font-weight: 700; }}
      .good {{ fill: #34d399; font-weight: 700; }}
      .bar {{ font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; font-size: 12px; fill: #7c8aa0; }}
      {style}
      @media (prefers-reduced-motion: reduce) {{ .m {{ animation: none !important; opacity: 1 !important; }} }}
    </style>
  </defs>
  <rect width="{WIDTH}" height="{height}" rx="12" fill="#0b1220"/>
  <rect width="{WIDTH}" height="34" rx="12" fill="#111a2e"/>
  <rect y="22" width="{WIDTH}" height="12" fill="#111a2e"/>
  <circle cx="22" cy="17" r="5.5" fill="#fb7185"/>
  <circle cx="40" cy="17" r="5.5" fill="#fbbf24"/>
  <circle cx="58" cy="17" r="5.5" fill="#34d399"/>
  <text x="{WIDTH // 2}" y="21" text-anchor="middle" class="bar">python3 examples/false-green/run_demo.py</text>
{body}
</svg>
"""


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    svg = render(demo_lines())
    if "--check" in argv:
        current = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if current != svg:
            print(f"STALE: {OUT.relative_to(ROOT)} does not match the demo output; "
                  "run python3 tools/render_demo_svg.py", file=sys.stderr)
            return 1
        print(f"UP TO DATE: {OUT.relative_to(ROOT)}")
        return 0
    OUT.write_text(svg, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
