#!/usr/bin/env python3
"""Builds docs/index.html — the GitHub Pages architecture document — from the
existing sources in docs/architecture/ (D1/D2 PNGs, the four Mermaid flow
files). Single source of truth stays the .md files; this script only
assembles them for Pages, which cannot render ```mermaid fences on its own.

Run:  docs/architecture/.venv/bin/python docs/build_site.py
"""

import html
import pathlib
import re

import markdown

ROOT = pathlib.Path(__file__).parent
ARCH = ROOT / "architecture"

FLOWS = [
    ("flow_login.md", "S1"),
    ("flow_authorized_request.md", "S2"),
    ("flow_institution_connect.md", "S3"),
    ("flow_caregiver_revoke.md", "S4"),
]

MERMAID_RE = re.compile(r"```mermaid\n(.*?)```", re.S)


def md_to_html(src: str) -> str:
    """Markdown -> HTML, with ```mermaid fences pulled out first so python-markdown
    doesn't turn them into an escaped generic <code> block."""
    blocks = []

    def stash(m: re.Match) -> str:
        blocks.append(m.group(1))
        return f"\n\n<!--MERMAID{len(blocks) - 1}-->\n\n"

    stashed = MERMAID_RE.sub(stash, src)
    rendered = markdown.markdown(stashed, extensions=["tables", "fenced_code"])
    for i, block in enumerate(blocks):
        placeholder = f"<!--MERMAID{i}-->"
        diagram = f'<pre class="mermaid">\n{html.escape(block)}</pre>'
        # python-markdown wraps stray comments in <p>...</p>; strip that.
        rendered = rendered.replace(f"<p>{placeholder}</p>", diagram)
        rendered = rendered.replace(placeholder, diagram)
    return rendered


sections = []
for fname, sid in FLOWS:
    src = (ARCH / fname).read_text()
    # First line is the "# S1 — Title" heading; use it for the nav + anchor,
    # keep the rest of the file as the section body.
    title_line, _, rest = src.partition("\n")
    title = title_line.lstrip("# ").strip()
    sections.append({"id": sid, "title": title, "body": md_to_html(rest)})

nav_items = "\n".join(
    f'<li><a href="#{s["id"]}">{s["id"]} — {html.escape(s["title"].split("—", 1)[-1].strip())}</a></li>'
    for s in sections
)

flow_sections_html = "\n".join(
    f'<section id="{s["id"]}" class="flow">\n<h2>{html.escape(s["title"])}</h2>\n{s["body"]}\n</section>'
    for s in sections
)

PAGE = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MedVault — Architecture</title>
<meta name="description" content="MedVault architecture: C4 component and deployment diagrams, and the four security-critical request flows.">
<style>
  :root {{
    --bg: #ffffff;
    --bg-alt: #f6f8fa;
    --fg: #1f2328;
    --fg-muted: #57606a;
    --border: #d0d7de;
    --accent: #0969da;
    --code-bg: #f6f8fa;
    --authz: #b7410e;
    --session: #1f6feb;
    --oauth: #8250df;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --bg: #0d1117;
      --bg-alt: #161b22;
      --fg: #e6edf3;
      --fg-muted: #8b949e;
      --border: #30363d;
      --accent: #4493f8;
      --code-bg: #161b22;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    background: var(--bg);
    color: var(--fg);
    font: 16px/1.6 -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  }}
  .wrap {{ max-width: 980px; margin: 0 auto; padding: 0 24px 96px; }}
  header.hero {{
    border-bottom: 1px solid var(--border);
    padding: 48px 0 32px;
    margin-bottom: 40px;
  }}
  header.hero h1 {{ margin: 0 0 8px; font-size: 2rem; }}
  header.hero p.tag {{ color: var(--fg-muted); margin: 0; font-size: 1.05rem; }}
  .badges {{ margin-top: 16px; display: flex; gap: 8px; flex-wrap: wrap; }}
  .badge {{
    display: inline-block; font-size: 0.78rem; padding: 3px 9px;
    border-radius: 999px; border: 1px solid var(--border); color: var(--fg-muted);
  }}
  nav.toc {{
    background: var(--bg-alt); border: 1px solid var(--border); border-radius: 8px;
    padding: 20px 24px; margin-bottom: 48px;
  }}
  nav.toc h2 {{ font-size: 0.95rem; text-transform: uppercase; letter-spacing: .04em;
    color: var(--fg-muted); margin: 0 0 12px; }}
  nav.toc ul {{ margin: 0; padding-left: 20px; columns: 2; }}
  nav.toc li {{ margin: 4px 0; break-inside: avoid; }}
  nav.toc a {{ color: var(--accent); text-decoration: none; }}
  nav.toc a:hover {{ text-decoration: underline; }}
  h1, h2, h3 {{ line-height: 1.25; scroll-margin-top: 20px; }}
  h2 {{ margin-top: 56px; padding-top: 8px; border-top: 1px solid var(--border); font-size: 1.5rem; }}
  h3 {{ font-size: 1.15rem; margin-top: 32px; }}
  a {{ color: var(--accent); }}
  code {{ background: var(--code-bg); padding: 2px 5px; border-radius: 4px; font-size: 0.9em; }}
  table {{ border-collapse: collapse; width: 100%; margin: 16px 0; font-size: 0.92rem; }}
  th, td {{ border: 1px solid var(--border); padding: 8px 10px; text-align: left; }}
  th {{ background: var(--bg-alt); }}
  blockquote {{
    margin: 16px 0; padding: 4px 16px; border-left: 3px solid var(--accent);
    color: var(--fg-muted); background: var(--bg-alt);
  }}
  figure {{ margin: 24px 0; text-align: center; }}
  figure img {{ max-width: 100%; border: 1px solid var(--border); border-radius: 8px; }}
  figcaption {{ color: var(--fg-muted); font-size: 0.88rem; margin-top: 10px; }}
  .diagram-card {{
    border: 1px solid var(--border); border-radius: 10px; padding: 24px;
    margin: 24px 0; background: var(--bg-alt);
  }}
  pre.mermaid {{
    background: var(--bg); border: 1px solid var(--border); border-radius: 8px;
    padding: 16px; overflow-x: auto; margin: 20px 0;
  }}
  section.flow {{ margin-bottom: 8px; }}
  .legend {{ display: flex; gap: 18px; flex-wrap: wrap; font-size: 0.85rem; color: var(--fg-muted); margin: 12px 0 28px; }}
  .legend span.dot {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 6px; vertical-align: middle; }}
  footer {{ margin-top: 64px; padding-top: 24px; border-top: 1px solid var(--border); color: var(--fg-muted); font-size: 0.85rem; }}
  .status-table td:nth-child(2) {{ font-family: ui-monospace, monospace; font-size: 0.85em; }}
  @media (max-width: 640px) {{ nav.toc ul {{ columns: 1; }} }}
</style>
</head>
<body>
<div class="wrap">

<header class="hero">
  <h1>MedVault — Architecture</h1>
  <p class="tag">C4 component &amp; deployment diagrams, and the four request flows where an implementation mistake has a security consequence.</p>
  <div class="badges">
    <span class="badge">Spec v1.1 (English revision — §2.3, R1–R6)</span>
    <span class="badge">MVP — Internship, September</span>
    <span class="badge">Status: Pending approval</span>
  </div>
</header>

<blockquote>
  <strong>Note.</strong> Two documents both labelled <em>v1.1</em> have circulated.
  This page follows the later English revision — the one with §2.3
  <em>Database Setup &amp; Migration Strategy</em>, Alembic in the stack table, and risk
  <strong>R6</strong>. Diagrams here are intentionally simple; they will get more
  abstract and larger as the design settles.
</blockquote>

<nav class="toc">
  <h2>Contents</h2>
  <ul>
    <li><a href="#d1">D1 — Backend components (C4 L3)</a></li>
    <li><a href="#d2">D2 — Deployment</a></li>
    {nav_items}
    <li><a href="#invariants">Invariants</a></li>
  </ul>
</nav>

<section id="d1">
  <h2>D1 — Backend Components (C4 level 3)</h2>
  <p>The inside of the FastAPI container: modules, their boundaries, and which
  store each one touches. The point of the picture: no feature module reaches
  PostgreSQL on its own — every data path goes through <code>authorization</code>,
  which opens the transaction and sets <code>app.current_user_id</code> with
  <code>SET LOCAL</code> (ADR-02).</p>
  <div class="diagram-card">
    <figure>
      <img src="architecture/backend_components.png" alt="D1 backend components diagram">
      <figcaption>Generated by <code>docs/architecture/backend_components.py</code> (Python <code>diagrams</code> / Graphviz).</figcaption>
    </figure>
  </div>
</section>

<section id="d2">
  <h2>D2 — Deployment</h2>
  <p>One DigitalOcean Droplet, one Docker Compose stack, manual deploys.
  Caddy is the only process with a port published to the host. Schema changes
  reach the database only through a blocking <code>alembic upgrade head</code>
  step, run by <code>migrator</code>, before the app serves traffic (§2.3, R6).</p>
  <div class="diagram-card">
    <figure>
      <img src="architecture/deployment.png" alt="D2 deployment diagram">
      <figcaption>Generated by <code>docs/architecture/deployment.py</code> (Python <code>diagrams</code> / Graphviz).</figcaption>
    </figure>
  </div>
</section>

{flow_sections_html}

<section id="invariants">
  <h2>Invariants every diagram keeps</h2>
  <ol>
    <li><strong>JWT never appears for a user session.</strong> It exists only in S3, as an institution-mock OAuth2 access token (ADR-01). User sessions are an opaque id in a cookie, with state in Redis.</li>
    <li><strong>No feature module reaches PostgreSQL directly</strong> — every module routes through <code>authorization</code> (D1).</li>
    <li><strong>Missing RLS context = zero rows</strong>, never an error and never data (S2, <strong>TC-SEC-01</strong>).</li>
    <li><strong><code>GET /Observation</code> takes no <code>patient</code> query parameter</strong> (S3, ADR-03, R2).</li>
    <li><strong>The SMS code exists only in the sms-mock container log</strong> (S1, ADR-05).</li>
    <li><strong>Self-upload stores and categorises — it never parses</strong> (D1, ADR-04).</li>
    <li><strong>DDL never runs as <code>app_user</code></strong> — only the blocking migration step, run by <code>migrator</code> (D2, §2.3, R6).</li>
  </ol>
  <div class="legend">
    <span><span class="dot" style="background: var(--authz)"></span>RLS context</span>
    <span><span class="dot" style="background: var(--session)"></span>session / cookie</span>
    <span><span class="dot" style="background: var(--oauth)"></span>OAuth2 + JWT (institution-mock only)</span>
  </div>
  <p>Full source, regeneration instructions, and known gaps are in
  <a href="https://github.com/igortacu/medvault/tree/main/docs/architecture">docs/architecture/README.md</a>.</p>
</section>

<footer>
  MedVault — architecture document, generated from
  <code>docs/architecture/*.py</code> and <code>docs/architecture/flow_*.md</code>.
  Source of truth: <em>MedVault — Technical Requirements Specification v1.1</em>.
</footer>

</div>

<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<script>
  function mermaidTheme() {{
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "default";
  }}
  mermaid.initialize({{ startOnLoad: true, theme: mermaidTheme(), securityLevel: "loose" }});
</script>
</body>
</html>
"""

(ROOT / "index.html").write_text(PAGE)
print(f"wrote {ROOT / 'index.html'}  ({len(PAGE):,} bytes)")
