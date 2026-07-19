#!/usr/bin/env python3
"""Stamp the ONE canonical site footer into every page.

The footer regressed once (2026-07-19: subpage footers hugged the left edge
because they inherited their page-wrap's text-align while the homepage wrap
was centered). The fix: the footer centers ITSELF (.siteftr) and this script
is the single source of truth — edit FOOTER_HTML / FOOTER_CSS here, run
`python3 tools/sync_footer.py`, and every page gets the identical block.
A page whose footer drifts from canonical is rewritten; the script fails loud
if it can't find a footer to replace.
"""
import re
import sys
import pathlib

PAGES = ["index.html", "federal-gap.html", "dictionary.html",
         "attribution.html", "terms.html", "privacy.html"]

FOOTER_CSS = """/* shared footer (canonical in tools/sync_footer.py — do not hand-edit per page) */
.siteftr{margin-top:72px;padding:56px 12px 10px;border-top:1px solid #232e4a;text-align:center;color:#5b6b85;font-size:13px}
.siteftr .flinks{display:flex;flex-wrap:wrap;justify-content:center;gap:12px 30px;margin:0 0 34px}
.siteftr .flinks a{color:#7fd4c8;text-decoration:none;font-size:13.5px;letter-spacing:.5px}
.siteftr .flinks a:hover{color:#a5e6dc;text-decoration:underline;text-underline-offset:4px}
.siteftr .fbrand{display:flex;align-items:center;justify-content:center;gap:12px;color:#46536b;font-size:12px;flex-wrap:wrap}
.siteftr .fbrand img{opacity:.75;display:block;border-radius:50%}"""

FOOTER_HTML = """<footer class="siteftr">
<nav class="flinks" aria-label="Footer">
<a href="/attribution.html">Attribution &amp; Notices</a>
<a href="/dictionary.html">Data Dictionary</a>
<a href="/federal-gap.html">The Federal Gap</a>
<a href="/terms.html">Terms of Use</a>
<a href="/privacy.html">Privacy Policy</a>
<a href="mailto:support@rosterproof.com">support@rosterproof.com</a>
</nav>
<div class="fbrand"><img src="/shoonya-logo.png" alt="Shoonya enso logo" width="34" height="34" loading="lazy"><span>© 2026 Shoonya — RosterProof is a Shoonya product</span></div>
</footer>"""


def sync(path: pathlib.Path) -> bool:
    s = path.read_text()
    orig = s
    # markup: replace the whole footer block
    if "<footer" not in s:
        sys.exit(f"{path}: no <footer> found — page structure changed, fix by hand")
    s = re.sub(r"<footer[^>]*>.*?</footer>", FOOTER_HTML, s, count=1, flags=re.S)
    # css: replace the legacy footer rule or a previous shared block
    if "/* shared footer" in s:
        s = re.sub(r"/\* shared footer.*?\.siteftr \.fbrand img\{[^}]*\}",
                   FOOTER_CSS, s, count=1, flags=re.S)
    elif re.search(r"footer\{[^}]*\}", s):
        s = re.sub(r"footer\{[^}]*\}", FOOTER_CSS, s, count=1)
        # legacy helper rules superseded by the shared block
        s = re.sub(r"\n\.legal\{[^}]*\}", "", s)
    else:
        # page never had footer CSS (privacy.html) -- add before </style>
        s = s.replace("</style>", FOOTER_CSS + "\n</style>", 1)
    if ".siteftr{" not in s:
        sys.exit(f"{path}: shared footer CSS did not land — fix by hand")
    if s != orig:
        path.write_text(s)
        return True
    return False


if __name__ == "__main__":
    root = pathlib.Path(__file__).resolve().parent.parent
    for page in PAGES:
        changed = sync(root / page)
        print(f"{'updated' if changed else 'already canonical'}  {page}")
