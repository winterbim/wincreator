"""The README's false-green transcript and hero SVG must match what the demo really prints."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
START, END = "<!-- demo:false-green:start -->", "<!-- demo:false-green:end -->"


def demo_output():
    result = subprocess.run(
        [sys.executable, str(REPO / "examples" / "false-green" / "run_demo.py")],
        capture_output=True, text=True, cwd=REPO,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


def embedded_block(path):
    text = path.read_text(encoding="utf-8")
    assert START in text and END in text, f"{path.name} lost its demo markers"
    block = text.split(START, 1)[1].split(END, 1)[0].strip("\n")
    lines = block.split("\n")
    assert lines[0].startswith("```") and lines[-1] == "```"
    return "\n".join(lines[1:-1]) + "\n"


def test_demo_shows_a_green_gate_judged_insufficient():
    output = demo_output()
    assert "VERDICT INSUFFICIENT" in output
    assert "VERDICT ADEQUATE" in output
    assert output.index("VERDICT INSUFFICIENT") < output.index("VERDICT ADEQUATE")


def test_readme_transcripts_match_the_real_demo_output():
    output = demo_output()
    for name in ("README.md", "README.fr.md", "examples/false-green/README.md"):
        assert embedded_block(REPO / name) == output, f"{name} transcript is stale"


def test_hero_svg_is_generated_from_the_real_demo_output():
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "render_demo_svg.py"), "--check"],
        capture_output=True, text=True, cwd=REPO,
    )
    assert result.returncode == 0, result.stdout + result.stderr
