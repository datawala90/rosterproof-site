#!/usr/bin/env python3
"""Generate the per-state pages (/states/<state>/) and the index (/states/) from stats.json.

    python3 tools/build_state_pages.py            # rewrites states/**/index.html + the sitemap entries

Every number on a state page comes from stats.json `state_sources` (written by pipeline.publish_stats
from the PUBLISHED views): the HTML carries the values as fallbacks for no-JS/preview surfaces, and
the page re-renders them live from /stats.json on load. Re-run this script after a stats.json refresh
that changes a state's figures (the weekly CI step only pushes stats.json; the live JS covers the gap
until the next regeneration). Footer markup/CSS come from tools/sync_footer.py (canonical).
"""
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from sync_footer import FOOTER_CSS, FOOTER_HTML  # noqa: E402

STATE_NAMES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois", "IN": "Indiana",
    "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan",
    "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}
FORMAT_WORDS = {"XLSX": "an Excel workbook", "XLS": "an Excel workbook", "CSV": "a CSV file", "TSV": "a tab-separated file", "PDF": "a PDF",
                "HTML_TABLE": "a table on a web page", "JSON": "a JSON feed"}
FORMAT_SHORT = {"XLSX": "Excel", "XLS": "Excel", "CSV": "CSV", "TSV": "TSV", "PDF": "PDF", "HTML_TABLE": "web page", "JSON": "JSON"}
CADENCE_WORDS = {"DAILY": "the agency updates it daily", "SEMIMONTHLY": "the agency updates it about twice a month",
                 "MONTHLY": "the agency updates it monthly", "IRREGULAR": "the agency updates it on no fixed schedule",
                 "EMAIL_REQUEST": "the agency sends it on request by email (RosterProof requests it every month)"}
CADENCE_SHORT = {"DAILY": "daily", "SEMIMONTHLY": "twice a month", "MONTHLY": "monthly", "IRREGULAR": "irregular", "EMAIL_REQUEST": "by email request"}
# agency notices that attribution.html carries for a state (keep in step with that page)
NOTICES = {"TX": "Texas HHSC asks that copies name HHSC as the source with the web address and copy date, and that any modification is labeled.",
           "NC": "North Carolina DHHS permits non-commercial copying of its list, unaltered and cited.",
           "VT": "Vermont DVHA requires a disclaimer: its list covers providers terminated for cause by DVHA and the Agency of Human Services and may not include every excluded provider.",
           "ID": "The Idaho Department of Health and Welfare notes that its list holds Idaho-issued exclusions only and directs users to check the federal lists as well."}

E = html.escape
fmt = lambda n: f"{n:,}"
slug = lambda code: STATE_NAMES[code].lower().replace(" ", "-")


def common_css():
    return """body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;background:#0a1128;color:#eef2fb;margin:0}
.wrap{max-width:960px;margin:0 auto;padding:56px 24px}
h1{font-size:28px;font-weight:600;margin:0 0 6px;line-height:1.25}
h2{font-size:20px;margin:44px 0 6px;color:#7fd4c8}
p{color:#c7d2ea;line-height:1.7}
.tag{color:#8fa3c7;font-size:13px;letter-spacing:2px;margin-bottom:28px;text-transform:uppercase}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:14px;margin:24px 0 8px}
.stat{background:#111a36;border:1px solid #2f3b55;border-radius:14px;padding:22px 14px}
.stat .big{font-size:26px;font-weight:600;color:#7fd4c8;margin-bottom:6px;font-variant-numeric:tabular-nums}
.stat .small{color:#8fa3c7;font-size:13px;line-height:1.5}
.card{background:#111a36;border:1px solid #2f3b55;border-left:3px solid #7fd4c8;border-radius:14px;padding:18px 24px;margin:18px 0}
.card p{margin:0}
.tablewrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px;margin:12px 0}
th,td{border:1px solid #2f3b55;padding:9px 12px;text-align:left;vertical-align:top;line-height:1.55}
th{background:#111a36;color:#8fa3c7;font-weight:600}
td.num{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
code{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.92em;color:#7fd4c8}
a{color:#7fd4c8}
ul,ol{color:#c7d2ea;line-height:1.7}
.sitehdr{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 36px}
.sitehdr .brand{display:flex;align-items:center;gap:10px;text-decoration:none}
.sitehdr .brand img{display:block;border-radius:6px}
.sitehdr .brand span{color:#eef2fb;letter-spacing:3px;font-weight:600;font-size:14px}
.sitehdr nav{margin-left:auto;display:flex;gap:16px;flex-wrap:wrap}
.sitehdr nav a{color:#8fa3c7;font-size:13px;text-decoration:none}
.sitehdr nav a:hover{color:#7fd4c8}
.cta{display:inline-block;background:#7fd4c8;color:#0a1128;font-weight:700;font-size:15px;padding:12px 22px;border-radius:12px;text-decoration:none;margin:6px 10px 6px 0}
.cta:hover{background:#a5e6dc}
.gbtn{display:inline-block;border:1px solid #7fd4c8;color:#7fd4c8;font-weight:600;font-size:14px;padding:10px 18px;border-radius:12px;text-decoration:none;margin:6px 10px 6px 0}
.notice{background:#0d1530;border:1px solid #2f3b55;border-radius:10px;padding:12px 16px;color:#8fa3c7;font-size:13.5px;line-height:1.6;margin-top:28px}
.crumbs{color:#8fa3c7;font-size:13px;margin-bottom:18px}.crumbs a{color:#8fa3c7}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px 18px;margin:14px 0}
.grid a{color:#c7d2ea;text-decoration:none;font-size:14.5px;line-height:1.8}.grid a:hover{color:#7fd4c8}
.grid a span{color:#5b6b85;font-size:12.5px;margin-left:6px;font-variant-numeric:tabular-nums}
""" + FOOTER_CSS


HEADER = ('<header class="sitehdr"><a class="brand" href="/"><img src="/icon-512.png" width="26" height="26" alt="RosterProof"><span>rosterproof</span></a>'
          '<nav><a href="/">Home</a><a href="/investigator/">Investigator</a><a href="/states/">States</a><a href="/screen.html">Screen my providers</a><a href="/api.html">API</a>'
          '<a href="/federal-gap.html">The Federal Gap</a><a href="/attribution.html">Attribution</a></nav></header>')


def head(title, desc, canonical, ldjson, og_type="article"):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{E(title)}</title>
<link rel="canonical" href="{canonical}">
<meta name="description" content="{E(desc)}">
<meta property="og:title" content="{E(title)}">
<meta property="og:description" content="{E(desc)}">
<meta property="og:image" content="https://rosterproof.com/assets/og-image.png">
<meta property="og:url" content="{canonical}">
<meta property="og:type" content="{og_type}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="https://rosterproof.com/assets/og-image.png">
<link rel="icon" href="/favicon.ico" sizes="48x48">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16.png">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<style>
{common_css()}
</style>
<script type="application/ld+json">
{json.dumps(ldjson, indent=1)}
</script>
</head>
<body>
<div class="wrap">
{HEADER}
<main>
"""


def state_page(s, stats, all_states):
    code = s["state"]; name = STATE_NAMES[code]; url = f"https://rosterproof.com/states/{slug(code)}/"
    is_dc = code == "DC"
    kind = "excluded parties list" if is_dc else "Medicaid exclusion list"
    title = f"{name} {kind.title()} — Search & Screen NPIs" if len(f"{name} {kind.title()} — Search & Screen NPIs") <= 62 else f"{name} {kind.title()} — Screen NPIs"
    gap = s["gap_pct"]; active = s["records_active"]; asof = stats["last_refresh_utc"][:10]
    gap_txt = f"{gap:g}%" if gap is not None else "n/a"
    desc = (f"The {name} {kind}: {fmt(active)} active records as of {asof}, {gap_txt} not on the federal LEIE. "
            f"Official source, update schedule, and how to check a provider in seconds.")
    cad = CADENCE_WORDS.get(s["update_cadence"], "updated on the agency's own schedule")
    fmtw = FORMAT_WORDS.get(s["source_format"], "a published file")
    ld = [{"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "RosterProof", "item": "https://rosterproof.com/"},
            {"@type": "ListItem", "position": 2, "name": "State exclusion lists", "item": "https://rosterproof.com/states/"},
            {"@type": "ListItem", "position": 3, "name": name, "item": url}]},
          {"@context": "https://schema.org", "@type": "Dataset", "name": f"{name} {kind} (RosterProof unified schema)",
           "description": desc, "url": url, "isAccessibleForFree": True, "license": "https://rosterproof.com/terms.html",
           "creator": {"@type": "GovernmentOrganization", "name": s["source_name"], "url": s["source_url"]},
           "publisher": {"@type": "Organization", "name": "Shoonya", "url": "https://rosterproof.com/"},
           "isPartOf": {"@type": "Dataset", "name": "RosterProof — Unified Provider Exclusions (Federal + State)", "url": "https://rosterproof.com/"},
           "spatialCoverage": {"@type": "Place", "name": f"{name}, United States"},
           "distribution": [{"@type": "DataDownload", "encodingFormat": "text/csv", "contentUrl": "https://rosterproof.com/download.html"}]}]
    dates = ""
    if s["earliest_start"] and s["latest_start"]:
        dates = (f" The earliest exclusion start date the agency publishes is {s['earliest_start']} and the most recent is {s['latest_start']}"
                 f"{' (dates are shown exactly as published)' if s['earliest_start'] < '1975-01-01' else ''}.")
    elif not s["earliest_start"]:
        dates = " The agency does not publish exclusion start dates for these records."
    multi = s["multi_jurisdiction"]
    notice = NOTICES.get(code)
    others = sorted((o for o in all_states if o["state"] != code), key=lambda o: STATE_NAMES[o["state"]])   # alphabetical, never ranked
    body = f"""<div class="crumbs"><a href="/">Home</a> › <a href="/states/">State exclusion lists</a> › {E(name)}</div>
<h1>{E(name)} {kind}</h1>
<div class="tag">{E(s['source_name'])} · in the RosterProof dataset<span id="asof"> · as of {asof}</span></div>

<p>{E(name)} publishes its {kind} as {fmtw}; {cad}. RosterProof loads it every week into the same schema as the
federal OIG LEIE, SAM.gov and {stats['states'] - 1} other state lists, resolves names to NPIs where the national registry confirms
them, and keeps every change. The official list is the record of truth:
<a href="{E(s['source_url'])}" target="_blank" rel="noopener">{E(s['source_name'])}</a>.</p>

<div class="stats" data-state="{code}">
<div class="stat"><div class="big" data-k="records_active">{fmt(active)}</div><div class="small">active exclusion records</div></div>
<div class="stat"><div class="big" data-k="individuals">{fmt(s['individuals'])}</div><div class="small">individuals</div></div>
<div class="stat"><div class="big" data-k="organizations">{fmt(s['organizations'])}</div><div class="small">organizations</div></div>
<div class="stat"><div class="big" data-k="verified_npis">{fmt(s['verified_npis'])}</div><div class="small">NPPES-verified NPIs</div></div>
<div class="stat"><div class="big" data-k="gap_pct" data-suffix="%">{gap_txt}</div><div class="small">of active records not on the federal LEIE</div></div>
<div class="stat"><div class="big" data-k="multi_jurisdiction">{fmt(multi)}</div><div class="small">also excluded in another jurisdiction</div></div>
</div>
<p style="color:#8fa3c7;font-size:13px">Counts are from the published RosterProof dataset, refreshed weekly; the page re-reads them on load. Format: {FORMAT_SHORT.get(s['source_format'], s['source_format'])} · cadence: {CADENCE_SHORT.get(s['update_cadence'], s['update_cadence'].lower())} · last change RosterProof observed: <span data-k="last_changed">{s['last_changed'] or 'n/a'}</span>.</p>

<h2>What the federal gap means in {E(name)}</h2>
<p>{(f"Of the {fmt(active)} active records on the {name} list, <strong>{gap_txt} do not appear on the federal OIG LEIE</strong>. A program that screens only the federal lists, as 42 CFR 455.436 requires at minimum, never sees those providers. " if gap is not None else "")}Under ACA §6501, an exclusion or for-cause termination in one state's Medicaid program is grounds for termination in every other state, so a {E(name)} exclusion matters to any payer or employer in any state.{dates}{(f" {fmt(multi)} of the records belong to providers that at least one other jurisdiction has also excluded.") if multi else ""} How the gap is measured, for every state: <a href="/federal-gap.html">The federal gap, measured</a>.</p>

<h2>How to check a provider against the {E(name)} list</h2>
<ol>
<li><strong>In the browser, no account:</strong> paste or upload NPIs on <a href="/screen.html">Screen my providers</a>. Each NPI is checked against the {E(name)} list and every other list at once; results download as CSV.</li>
<li><strong>By API:</strong> <code>POST /v1/screen</code> with NPIs, names or organizations; a free key allows 500 lookups a month. <a href="/api.html">API documentation</a>.</li>
<li><strong>In your warehouse:</strong> the <a href="https://app.snowflake.com/marketplace/listing/GZSXZ2K49BC/" target="_blank" rel="noopener">free Snowflake listing</a> or the <a href="/download.html">weekly CSV / Parquet download</a>; filter <code>JURISDICTION = '{code}'</code> in <code>EXCLUSIONS_SCREENABLE</code>.</li>
<li><strong>Then confirm with the agency.</strong> A hit identifies a published record and, where present, an NPI match with a stated confidence. Before any adverse action, verify against <a href="{E(s['source_url'])}" target="_blank" rel="noopener">the official {E(name)} list</a> (and OIG's SSN-based search for LEIE matches).</li>
</ol>
<p><a class="cta" href="/screen.html">Screen my providers →</a> <a class="gbtn" href="{E(s['source_url'])}" target="_blank" rel="noopener">Official {E(code)} list ↗</a></p>

<h2>About this source</h2>
<div class="tablewrap"><table>
<tr><th>Official list</th><td><a href="{E(s['source_url'])}" target="_blank" rel="noopener">{E(s['source_name'])}</a></td></tr>
<tr><th>Published as</th><td>{E(fmtw)}</td></tr>
<tr><th>Update cadence</th><td>{E(cad[0].upper() + cad[1:])}</td></tr>
<tr><th>Records in RosterProof</th><td><span data-k="records_total">{fmt(s['records_total'])}</span> total, <span data-k="records_active">{fmt(active)}</span> active, <span data-k="started_last_90d">{fmt(s['started_last_90d'])}</span> with a start date in the last 90 days</td></tr>
<tr><th>Identity resolution</th><td><span data-k="verified_npis">{fmt(s['verified_npis'])}</span> distinct NPIs confirmed in the CMS NPPES registry; the rest are name-only records, matched by exact name and state. Match tiers: <a href="/dictionary.html">data dictionary</a>.</td></tr>
<tr><th>Source identifier</th><td><code>SOURCE_ID = '{code}'</code>, <code>JURISDICTION = '{code}'</code></td></tr>
<tr><th>Attribution</th><td>{E(notice) + ' ' if notice else ''}Full notices for every source: <a href="/attribution.html">Attribution &amp; notices</a>.</td></tr>
</table></div>

<h2>Other state lists</h2>
<p>Every list RosterProof loads, each with its official source and how to screen against it (<a href="/states/">all states + DC</a>):</p>
<div class="grid">{''.join(f'<a href="/states/{slug(o["state"])}/">{E(STATE_NAMES[o["state"]])}</a>' for o in others)}</div>

<div class="notice"><strong>Verify before adverse action.</strong> RosterProof is a screening data layer, not a fraud detector. A hit identifies a published exclusion record and, where present, an NPI match with a stated confidence. Confirm against the source agency before taking any action. Free for compliance screening under the <a href="/terms.html">Terms of Use</a>.</div>
</main>
<script>
fetch('/stats.json').then(r => r.json()).then(d => {{
  const s = (d.state_sources || []).find(x => x.state === '{code}'); if (!s) return;
  document.querySelectorAll('[data-k]').forEach(el => {{ const v = s[el.dataset.k]; if (v == null) return;
    el.textContent = typeof v === 'number' ? (el.dataset.suffix ? v + el.dataset.suffix : v.toLocaleString('en-US')) : v }});
  document.getElementById('asof').textContent = ' · as of ' + d.last_refresh_utc.slice(0, 10);
}}).catch(() => {{}});
</script>
"""
    return head(title, desc, url, ld) + body + FOOTER_HTML + "\n</div>\n" + beacon() + "</body>\n</html>\n"


def index_page(states, stats):
    url = "https://rosterproof.com/states/"
    n = stats["states"]
    title = "State Medicaid Exclusion Lists — All 42 States + DC in One Place"
    desc = (f"All {n} state Medicaid exclusion lists + DC: official source, format, update schedule, active records and the share "
            "missing from the federal LEIE. Check a provider against every list at once.")
    ld = {"@context": "https://schema.org", "@type": "CollectionPage", "name": title, "description": desc, "url": url,
          "isPartOf": {"@type": "WebSite", "name": "RosterProof", "url": "https://rosterproof.com/"}}
    total_active = sum(s["records_active"] for s in states)
    rows = "\n".join(
        f'<tr><td><a href="/states/{slug(s["state"])}/">{E(STATE_NAMES[s["state"]])}</a></td>'
        f'<td><a href="{E(s["source_url"])}" target="_blank" rel="noopener">{E(s["source_name"])}</a></td>'
        f'<td>{FORMAT_SHORT.get(s["source_format"], s["source_format"])}</td><td>{CADENCE_SHORT.get(s["update_cadence"], s["update_cadence"].lower())}</td>'
        f'<td class="num" data-state="{s["state"]}" data-k="records_active">{fmt(s["records_active"])}</td>'
        f'<td class="num" data-state="{s["state"]}" data-k="gap_pct" data-suffix="%">{(str(s["gap_pct"]) + "%") if s["gap_pct"] is not None else "n/a"}</td></tr>'
        for s in sorted(states, key=lambda s: STATE_NAMES[s["state"]]))
    missing = sorted(set(STATE_NAMES) - {s["state"] for s in states}, key=lambda c: STATE_NAMES[c])
    body = f"""<div class="crumbs"><a href="/">Home</a> › State exclusion lists</div>
<h1>State Medicaid exclusion lists, all in one place</h1>
<div class="tag">{n} states + DC · {fmt(total_active)} active records · updated weekly<span id="asof"> · as of {stats['last_refresh_utc'][:10]}</span></div>

<p>Every state Medicaid program can exclude or terminate providers on its own authority, and most publish a list. The lists come
in {len(stats['source_formats'])} different formats on {n + 1} different schedules, and <strong>about {stats['federal_gap_overall_pct']:g}% of their active records never
appear on the federal OIG LEIE</strong>, so a federal-only screen misses them. RosterProof loads every list below weekly into one
schema, so one check covers all of them. Each state page shows the official source, the update schedule, the counts, and how to screen against it.</p>

<p><a class="cta" href="/screen.html">Screen my providers against every list →</a> <a class="gbtn" href="/federal-gap.html">The federal gap by state</a></p>

<div class="tablewrap"><table>
<tr><th>State</th><th>Official list</th><th>Format</th><th>Cadence</th><th>Active records</th><th>Not on LEIE</th></tr>
{rows}
</table></div>
<p style="color:#8fa3c7;font-size:13px">Counts from the published RosterProof dataset; the page re-reads them on load. "Not on LEIE" = share of a state's active records with no matching federal LEIE record (<a href="/federal-gap.html">method</a>).</p>

<h2>States not yet loaded</h2>
<p>{', '.join(E(STATE_NAMES[c]) for c in missing)}. Some publish no list by design (Virginia and Oklahoma refer screeners to the federal lists); others are being pursued with the agency. The federal lists — OIG LEIE, SAM.gov, the FDA debarment and investigator-disqualification lists — cover every state and are in every RosterProof check.</p>

<h2>Checking a provider against all of them</h2>
<ol>
<li><a href="/screen.html">Screen my providers</a> — paste or upload NPIs in the browser, no account.</li>
<li><a href="/api.html">API</a> — <code>POST /v1/screen</code>, free key, 500 lookups a month.</li>
<li><a href="https://app.snowflake.com/marketplace/listing/GZSXZ2K49BC/" target="_blank" rel="noopener">Snowflake listing</a> or <a href="/download.html">CSV / Parquet download</a> — the whole dataset in your own warehouse.</li>
</ol>
<p>New to exclusion screening? Start with <a href="/how-to-check-provider-exclusion.html">how to check whether a provider is excluded</a> and <a href="/leie-vs-sam.html">LEIE vs SAM.gov: what each list covers</a>.</p>

<div class="notice"><strong>Verify before adverse action.</strong> A hit identifies a published exclusion record and, where present, an NPI match with a stated confidence. Confirm against the source agency before taking any action. Free for compliance screening under the <a href="/terms.html">Terms of Use</a>.</div>
</main>
<script>
fetch('/stats.json').then(r => r.json()).then(d => {{
  const by = Object.fromEntries((d.state_sources || []).map(s => [s.state, s]));
  document.querySelectorAll('[data-state][data-k]').forEach(el => {{ const s = by[el.dataset.state]; if (!s) return; const v = s[el.dataset.k]; if (v == null) return;
    el.textContent = el.dataset.suffix ? v + el.dataset.suffix : v.toLocaleString('en-US') }});
  document.getElementById('asof').textContent = ' · as of ' + d.last_refresh_utc.slice(0, 10);
}}).catch(() => {{}});
</script>
"""
    return head(title, desc, url, ld, "website") + body + FOOTER_HTML + "\n</div>\n" + beacon() + "</body>\n</html>\n"


def beacon() -> str:
    """Cloudflare Web Analytics beacon, once tools/beacon_token.txt exists (tools/add_beacon.py)."""
    t = ROOT / "tools" / "beacon_token.txt"
    return (f'<script defer src="https://static.cloudflareinsights.com/beacon.min.js" data-cf-beacon=\'{{"token": "{t.read_text().strip()}"}}\'></script>\n' if t.exists() else "")


def update_sitemap(states, today):
    sm = (ROOT / "sitemap.xml").read_text()
    sm = re.sub(r"\s*<url><loc>https://rosterproof.com/states/[^<]*</loc>.*?</url>", "", sm)
    entries = [f'  <url><loc>https://rosterproof.com/states/</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.9</priority></url>']
    entries += [f'  <url><loc>https://rosterproof.com/states/{slug(s["state"])}/</loc><lastmod>{today}</lastmod><changefreq>weekly</changefreq><priority>0.7</priority></url>' for s in states]
    sm = sm.replace("</urlset>", "\n".join(entries) + "\n</urlset>")
    sm = re.sub(r"\n{2,}", "\n", sm)
    (ROOT / "sitemap.xml").write_text(sm)


def main():
    stats = json.load(open(ROOT / "stats.json"))
    states = stats["state_sources"]
    today = stats["generated_at_utc"][:10]
    out = ROOT / "states"; out.mkdir(exist_ok=True)
    (out / "index.html").write_text(index_page(states, stats))
    for s in states:
        d = out / slug(s["state"]); d.mkdir(exist_ok=True)
        (d / "index.html").write_text(state_page(s, stats, states))
    update_sitemap(states, today)
    print(f"wrote states/index.html + {len(states)} state pages; sitemap updated")


if __name__ == "__main__":
    main()
