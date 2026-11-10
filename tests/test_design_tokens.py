"""Design system (#46): tokens.css is the one source of color.

The stylesheets and the Cytoscape graph page reference tokens only; the graph page
inlines the tokens and theme switcher so the exported file still works offline."""

import re
from pathlib import Path

from cultural_signal_graph.viz import render_html

STATIC = Path(__file__).resolve().parents[1] / "src" / "cultural_signal_graph" / "static"
COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b(?!;)|rgba?\(")


def _colors(text: str) -> list[str]:
    return [m.group(0) for m in COLOR.finditer(text)]


def test_stylesheets_use_tokens_only():
    for name in ["app.css", "futures/futures.css"]:
        assert _colors((STATIC / name).read_text(encoding="utf-8")) == [], name


def test_every_token_used_is_defined():
    defined = set(re.findall(r"(--[\w-]+)\s*:", (STATIC / "tokens.css").read_text(encoding="utf-8")))
    for name in ["app.css", "futures/futures.css"]:
        used = set(re.findall(r"var\((--[\w-]+)", (STATIC / name).read_text(encoding="utf-8")))
        assert used <= defined, (name, used - defined)


def test_dark_theme_overrides_every_color_token():
    css = (STATIC / "tokens.css").read_text(encoding="utf-8")
    light, dark = css.split(':root[data-theme="dark"]', 1)
    dark = dark.split("}", 1)[0]
    colored = {n for n, v in re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", light) if COLOR.search(v)}
    assert colored and colored <= set(re.findall(r"(--[\w-]+)\s*:", dark))


def test_graph_page_inlines_tokens_and_reads_them():
    page = render_html({"nodes": [], "edges": []})
    assert "--graph-entity" in page and "window.csgTheme" in page  # inlined, offline
    script = page[page.index("function graphStyle"):page.index("const cy = cytoscape")]
    assert _colors(script) == []
    assert "tok('--graph-entity')" in script
