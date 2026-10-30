#!/usr/bin/env python3
"""Stamp the Cloudflare Web Analytics beacon into every page (2026-10-30).

    python3 tools/add_beacon.py <site token>        # idempotent: replaces an existing beacon line

The free beacon is a JavaScript snippet; no proxying, no DNS change. Pages covered: every *.html at the root,
every states/**/index.html (the generator tools/build_state_pages.py also emits it once BEACON_TOKEN is set in
tools/beacon_token.txt), and investigator/index.html (the entry page). The token is public by design (it is in
the page source), so it is committed in tools/beacon_token.txt.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT / "tools" / "beacon_token.txt"


def snippet(token: str) -> str:
    return f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon=\'{{"token": "{token}"}}\'></script>'


def stamp(path: pathlib.Path, token: str) -> bool:
    s = path.read_text(encoding="utf-8")
    s2 = re.sub(r"\n?<script defer src=\"https://static\.cloudflareinsights\.com/beacon\.min\.js\"[^\n]*</script>", "", s)
    if "</body>" not in s2:
        return False
    s2 = s2.replace("</body>", snippet(token) + "\n</body>", 1)
    if s2 != s:
        path.write_text(s2, encoding="utf-8")
    return True


def main():
    token = sys.argv[1] if len(sys.argv) > 1 else (TOKEN_FILE.read_text().strip() if TOKEN_FILE.exists() else "")
    if not re.fullmatch(r"[0-9a-f]{32}", token):
        sys.exit("usage: tools/add_beacon.py <32-hex site token from Cloudflare > Web Analytics > Add a site>")
    TOKEN_FILE.write_text(token + "\n")
    pages = sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("states/**/index.html")) + sorted(ROOT.glob("investigator/index.html"))
    n = sum(stamp(p, token) for p in pages)
    print(f"beacon on {n} pages (token {token[:6]}…)")


if __name__ == "__main__":
    main()
