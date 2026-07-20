"""Generate the Examples gallery for the wiki and guide from examples/*.py.

For each example: extract its title/description from the module docstring, show
the source (minus the run-boilerplate and docstring), run it, and capture the
output. Adapter examples that need an uninstalled tool show a "requires" note
instead of output; the long-running CFD examples are listed with a note.

Outputs:
    docs/wiki/22_examples.md        (wiki page, markdown)
    docs/_examples_section.html     (fragment injected into ANVIL_GUIDE.html)

Run:  python docs/build_examples.py
"""
from __future__ import annotations

import ast
import html
import os
import subprocess
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXDIR = os.path.join(ROOT, "examples")

# Long-running solves: list with a note rather than running at build time.
NO_RUN = {"ex_cfd_subsonic_bump.py", "ex_cfd_supersonic_ramp.py",
          "ex_cfd_wedge.py", "tank_blowdown.py"}
MAX_OUT_LINES = 34
RUN_TIMEOUT = 60


def title_and_desc(src, fname):
    """(title, description) from the module docstring, else the filename."""
    try:
        doc = ast.get_docstring(ast.parse(src)) or ""
    except SyntaxError:
        doc = ""
    lines = [l.strip() for l in doc.splitlines() if l.strip()]
    stem = fname[:-3]
    if lines:
        title = lines[0].rstrip(":").strip()
        # skip a decorative underline line if present
        rest = [l for l in lines[1:] if set(l) - set("=-~")]
        desc = rest[0].strip() if rest else ""
        if desc.lower().startswith("demonstrates"):
            desc = desc[len("demonstrates"):].lstrip(": ").strip()
        desc = desc.rstrip(":").strip()
    else:
        title, desc = stem.replace("_", " "), ""
    return title, desc


def clean_source(src):
    """Drop the module docstring and the sys.path run-boilerplate for display."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return src.strip()
    lines = src.splitlines()
    drop = set()
    # docstring span
    body = tree.body
    if body and isinstance(body[0], ast.Expr) and isinstance(
        getattr(body[0], "value", None), ast.Constant
    ) and isinstance(body[0].value.value, str):
        for i in range(body[0].lineno - 1, body[0].end_lineno):
            drop.add(i)
    kept = []
    for i, line in enumerate(lines):
        if i in drop:
            continue
        s = line.strip()
        if s.startswith("sys.path.insert") or s == "import os, sys" or \
           (s.startswith("import ") and "sys" == s.replace("import", "").strip()):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def run_example(path):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        r = subprocess.run([sys.executable, path], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=RUN_TIMEOUT,
                           cwd=ROOT, env=env)
        return (r.stdout or "") + (r.stderr or ""), r.returncode
    except subprocess.TimeoutExpired:
        return "__TIMEOUT__", 1


def classify(out, code):
    low = out.lower()
    if out == "__TIMEOUT__":
        return "timeout"
    if "not installed" in low or "skipping" in low or (
            "requires" in low and "install" in low):
        return "skip"
    if code != 0 or "traceback (most recent call last)" in low:
        return "error"
    return "ok"


def trim(out):
    lines = out.splitlines()
    # strip trailing blank lines
    while lines and not lines[-1].strip():
        lines.pop()
    if len(lines) > MAX_OUT_LINES:
        head = lines[:MAX_OUT_LINES]
        head.append(f"... ({len(lines) - MAX_OUT_LINES} more lines)")
        return "\n".join(head)
    return "\n".join(lines)


def main():
    files = sorted(f for f in os.listdir(EXDIR) if f.endswith(".py"))
    md = ["# Examples\n",
          "Every runnable example from the `examples/` folder, with its code and "
          "output. Examples that wrap an external tool show what to install; the "
          "CFD cases note that they run a full solve locally.\n"]
    guide = ['<section id="examples">', "<h2>Examples</h2>",
             "<p>Every runnable example from the <code>examples/</code> folder, "
             "with its code and output.</p>"]
    n_ok = n_skip = n_other = 0

    for fname in files:
        path = os.path.join(EXDIR, fname)
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
        title, desc = title_and_desc(src, fname)
        code = clean_source(src)

        if fname in NO_RUN:
            status, out = "norun", ""
        else:
            raw, rc = run_example(path)
            status = classify(raw, rc)
            out = "" if status in ("skip", "timeout") else trim(raw)

        # --- markdown ---
        md.append(f"\n## {title}\n")
        md.append(f"`examples/{fname}`" + (f" — {desc}" if desc else "") + "\n")
        md.append("```python\n" + code + "\n```\n")
        if status == "ok":
            md.append("**Output:**\n\n```\n" + out + "\n```\n"); n_ok += 1
        elif status == "skip":
            md.append("> Requires an external tool that is not installed here. "
                      "Run `anvil doctor` for the exact install command, then run "
                      "the script to see its output.\n"); n_skip += 1
        elif status in ("timeout", "norun"):
            md.append("> Runs a full solve that takes a while; run the script "
                      "locally to see its output.\n"); n_other += 1
        else:  # error captured (rare)
            md.append("**Output:**\n\n```\n" + out + "\n```\n"); n_ok += 1

        # --- guide HTML ---
        guide.append(f"<h3>{html.escape(title)}</h3>")
        guide.append(f'<p class="muted"><code>examples/{fname}</code>'
                     + (f" &mdash; {html.escape(desc)}" if desc else "") + "</p>")
        guide.append("<pre>" + html.escape(code) + '<span class="lang-label">python</span></pre>')
        if status in ("ok", "error"):
            guide.append('<div class="out-wrap"><div class="out-label">Output</div>'
                         '<div class="out-block">' + html.escape(out) + "</div></div>")
        elif status == "skip":
            guide.append('<div class="tip">Requires an external tool not installed '
                         'here. Run <code>anvil doctor</code> for the install command.</div>')
        else:
            guide.append('<div class="tip">Runs a full solve that takes a while; '
                         'run the script locally to see its output.</div>')
    guide.append("</section>")

    with open(os.path.join(HERE, "wiki", "22_examples.md"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(md))
    with open(os.path.join(HERE, "_examples_section.html"), "w",
              encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(guide))
    print(f"examples: {len(files)} total, {n_ok} with output, {n_skip} require a tool, "
          f"{n_other} long-running")


if __name__ == "__main__":
    main()
