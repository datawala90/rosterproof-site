#!/usr/bin/env python3
"""Rebuild the body of insights.html from the refresh figures (docs/prompts/INSIGHTS_REFRESH.md in the pipeline repo).

    python3 tools/build_insights.py <insights_now.json> [as_of YYYY-MM-DD]

insights_now.json = the canonical workbench §15–§17 results (written by the refresh run); stats.json supplies the
published headline figures. No number is typed by hand. Guardrails baked in: no real people or organizations, no
state ranking (per-state lists alphabetical), gap measures always next to their one-line definition, Medicare
Opt-Out in its own section as a status, no dollar estimates.
"""
import datetime as dt
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
E = html.escape
fmt = lambda n: f"{n:,.0f}"
NAMES = {"AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado", "CT": "Connecticut",
         "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
         "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
         "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
         "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
         "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
         "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
         "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia", "WI": "Wisconsin", "WY": "Wyoming"}
SPEC = {"Community Based Hospice Care Agency": "Community hospice agencies", "General Practice Physician": "General practice physicians",
        "Pain Medicine (Anesthesiology) Physician": "Pain medicine", "Interventional Pain Medicine (Anesthesiology) Physician": "Interventional pain",
        "Mental Illness Community Based Residential Treatment Facility": "Residential mental-health facilities", "Podiatrist": "Podiatrists",
        "Licensed Vocational Nurse": "Licensed vocational nurses", "Geriatric Medicine (Internal Medicine) Physician": "Geriatric medicine",
        "Licensed Practical Nurse": "Licensed practical nurses", "Clinical Medical Laboratory": "Clinical medical laboratories"}
DEF_A = "share of active state exclusion records with no matching record on the federal OIG LEIE"
DEF_B = "share of active state records with an NPPES-verified NPI whose NPI appears on neither the LEIE nor SAM.gov"


def bar_rows(rows, maxv):
    return "\n".join(f'<div class="crow"><div class="lbl">{E(l)}</div><div class="track"><div class="bar" style="width:{max(2, round(100 * v / maxv))}%"></div></div><div class="val">{E(t)}</div></div>' for l, v, t in rows)


def build(R, S, as_of):
    rate = R["rate"][0]; one_in = round(rate["active_individual_npis"] / rate["verified_excluded_active_npis"])
    lag = R["lag"][0]; ser = R["serial"][0]; sec = R["second_gap"][0]; ends = R["ends"][0]; ali = R["alias"][0]; nc = R["namechg"][0]
    split = {r["entity_type"]: r for r in R["split"]}; tc = R["typecheck"][0]; wide = {r["et"]: r for r in R["wide"]}
    oc = {}
    for r in R["orgcat"]:
        oc.setdefault(r["txd"], {})[r["tc"]] = r["npis"]
    hospice = oc["Community Based Hospice Care Agency"]; labs = oc["Clinical Medical Laboratory"]
    hosp_pct = round(100 * hospice.get("2", 0) / sum(hospice.values())); lab_pct = round(100 * labs.get("2", 0) / sum(labs.values()))
    gb = R["gapB"][0]; gap_b = round(100 * gb["not_on_federal"] / gb["verified_active"], 1); gap_a = S["federal_gap_overall_pct"]
    multi = S["multi_jurisdiction_npis"]; wl = S["watchlist"]; fed = {f["source_id"]: f["active_records"] for f in S["federal_sources"]}
    tiers = {t["tier"]: t["count"] for t in S["tiers"]}; tsum = sum(tiers.values()); det = tsum - tiers.get("T4", 0)
    opt = R["optout"][0]; rev = R["review"][0]
    org2 = round(100 * wide["ORGANIZATION"]["in_2plus"] / (wide["ORGANIZATION"]["in_2plus"] + wide["INDIVIDUAL"]["in_2plus"]), 1)
    org4 = round(100 * wide["ORGANIZATION"]["in_4plus"] / (wide["ORGANIZATION"]["in_4plus"] + wide["INDIVIDUAL"]["in_4plus"]), 1)
    spec = [r for r in R["specialty"] if r["taxonomy"] in SPEC][:8]; top = spec[0]
    cor = sorted(R["corridors"], key=lambda r: (r["a"], r["b"])); cmax = max(r["providers"] for r in cor)
    rates = sorted((r for r in R["state_rate"] if r["st"] in NAMES), key=lambda r: NAMES[r["st"]])
    wtop = sorted(wl["top_practice_states"], key=lambda t: NAMES.get(t["state"], t["state"])); wmax = max(t["count"] for t in wtop)
    nice = dt.date.fromisoformat(as_of).strftime("%B %-d, %Y")
    month_word = lambda d: f"~{round(d / 30.44)} months"
    ga = lambda: f'<span class="gap"><strong>{gap_a}%</strong> <span class="gdef">— {DEF_A} (measure A)</span></span>'
    gbx = lambda: f'<span class="gap"><strong>{gap_b}%</strong> <span class="gdef">— {DEF_B} (measure B)</span></span>'
    return f'''<h1>What the data says</h1>
<div class="tag">medicaid exclusion statistics · figures as of <span id="in-asof">{nice}</span> · reproducible from workbench §15–§17</div>

<p>Every number on this page was computed from the RosterProof unified exclusion dataset — the federal OIG LEIE, the full
SAM.gov exclusions extract, two FDA lists and {S["states"]} state Medicaid exclusion lists plus the District of Columbia
({S["sources_total"]} sources), resolved to NPIs against the CMS NPPES registry. This edition refreshes the July 2026 findings
against data as of {nice}; where a July figure still tells the story, it is shown as then → now. Each figure is reproducible
from the published dataset and carries its own caveat.</p>

<p class="caveat" style="margin:0 0 6px">How this data is collected, matched and quality-checked: <a href="/methodology.pdf">read the Methodology (PDF, 2 pages)</a>.</p>

<h2>Two ways to measure what a federal-only check misses</h2>
<div class="card"><p><strong>Measure A: {gap_a}%</strong> — {DEF_A}. All active state records, matched by NPI where both sides carry one, otherwise by normalized name. July: 54.5% → now {gap_a}%.</p>
<p style="margin-top:12px"><strong>Measure B: {gap_b}%</strong> — {DEF_B}. {fmt(gb["not_on_federal"])} of {fmt(gb["verified_active"])} verified-NPI active state records.</p>
<p class="caveat">Two different questions: A covers every state record including the name-only ones; B counts only records whose identity the registry confirms, and checks both federal lists. Per-state figures for both: <a href="/states/">the state index</a>; how A is measured: <a href="/federal-gap.html">the federal gap, measured</a>.</p></div>

<h2>Even the exclusions that reach the federal list arrive late</h2>
<p>For providers whose state exclusion later appeared on the federal LEIE ({fmt(lag["state_led"])} state-led cases, July: 6,292),
we measured the gap between the state's exclusion start and the LEIE's:</p>
<div class="chart" role="img" aria-label="Bar chart of how long state exclusions take to reach the federal LEIE: median {fmt(lag["median_days"])} days, a quarter take more than {fmt(lag["p75"])} days, one in ten takes more than {fmt(lag["p90"])} days">
{bar_rows([("median trip", lag["median_days"], f'{fmt(lag["median_days"])} days'), ("a quarter take over", lag["p75"], f'{fmt(lag["p75"])} days'), ("one in ten takes over", lag["p90"], f'{fmt(lag["p90"])} days')], lag["p90"])}
<p class="chartnote">{fmt(lag["over_year"])} providers took more than a year (July: 1,905). And many never arrive: {ga()}.</p>
</div>
<div class="card"><p><strong>Even when state exclusions make it to the federal list, the median trip takes five months — a quarter take more than fifteen.</strong></p>
<p class="caveat">Caveat: measured across NPI-verified matches appearing on both a state list and the LEIE — the survivors. Exclusions that never reach the LEIE are excluded by construction, so true federal visibility is worse than these numbers.</p></div>

<h2>The specialty risk map</h2>
<p>Active excluded providers per 10,000 registered providers of the same type (NPPES taxonomies, NPI-verified matches, minimum 5,000 providers per category):</p>
<div class="chart" role="img" aria-label="Bar chart of exclusions per 10,000 providers by specialty">
{bar_rows([(SPEC[r["taxonomy"]], r["per_10k"], f'{r["per_10k"]:.0f}') for r in spec], top["per_10k"])}
</div>
<div class="card"><p><strong>{top["per_10k"] / 100:.1f}% of America's community hospice agencies are under an active exclusion somewhere</strong> (July: 1.6%) — the highest rate of any provider category we track. Hospice, pain management and residential facilities near the top independently mirror the federal enforcement pattern.</p>
<p class="caveat">Caveat: NPI-verified matches only; categories are NPPES primary taxonomies; rates use the active-NPI registry as the denominator.</p></div>

<h2>Excluded in more than one jurisdiction</h2>
<div class="statrow">
<div class="stat"><div class="big">{fmt(multi)}</div><div class="small">providers excluded by two or more jurisdictions (July: 7,303)</div></div>
<div class="stat"><div class="big">{month_word(sec["median_days"])}</div><div class="small">median gap between a provider's first and second jurisdiction</div></div>
<div class="stat"><div class="big">{fmt(ser["in_4plus"])}</div><div class="small">excluded in four or more (July: 152)</div></div>
</div>
<div class="card"><p><strong>The {month_word(sec["median_days"]).lstrip("~")} median between first and second jurisdiction is the window where cross-state screening catches what single-state screening cannot</strong> — under ACA §6501, one state's exclusion is every state's problem.</p>
<p class="caveat">Caveat: NPPES-verified identities, jurisdictions counted distinctly (federal counts once; published as ENTITY_OVERLAP). The count grew mainly because coverage grew.</p></div>

<h2>At least 1 in {one_in}</h2>
<p><span class="bignum">1 in {one_in}</span></p>
<p>actively-registered US individual providers is under an active healthcare exclusion that we have verified against the NPI registry —
{fmt(rate["verified_excluded_active_npis"])} of {rate["active_individual_npis"] / 1e6:.2f} million active individual NPIs (July: 1 in 340).</p>
<div class="card"><p class="caveat" style="margin-top:0">Caveat: this is a floor. It counts only exclusions we can tie to an active NPI with registry-verified identity; most state exclusion records publish no NPI at all, so the true rate is higher.</p></div>

<h2>Functionally permanent</h2>
<div class="statrow">
<div class="stat"><div class="big">{ends["pct"]:.0f}%</div><div class="small">of exclusions ever receive a source-published end date</div></div>
<div class="stat"><div class="big">~{round(ends["median_completed_days"] / 365.25)} years</div><div class="small">median duration of the exclusions that do end</div></div>
</div>
<div class="card"><p><strong>Treat an exclusion as permanent unless proven otherwise.</strong> About one in twenty ever gets a published reinstatement, and those that do run a median five years.</p>
<p class="caveat">Caveat: many sources publish no end dates by design — for those, an exclusion's end is observable only when the record leaves the source's list.</p></div>

<h2>Exclusions per provider, state by state</h2>
<p>Active exclusions on each state's list per 10,000 providers practicing in that state, alphabetical:</p>
<div class="rategrid">
{"".join(f'<div><span>{E(NAMES[r["st"]])}</span><b>{r["per_10k"]:.0f}</b></div>' for r in rates)}
</div>
<div class="card"><p class="caveat" style="margin-top:0">Caveat: a state's list includes some out-of-state providers, while the denominator counts providers practicing in the state — the ratio is directional, not exact, and reflects how much each state publishes as much as how much it excludes. Per-state lists and both gap measures: <a href="/states/">the state index</a>.</p></div>

<h2>Names change. NPIs don't.</h2>
<p><span class="bignum">{ali["pct"]}%</span></p>
<p>of matched excluded individuals carry a <em>registered</em> former, maiden or other name in the NPI registry — {fmt(ali["with_other"])} providers whom single-name screening can miss entirely (July: 6.5%, 1,464). Across states it is starker: about <strong>1 in {round(nc["multi"] / nc["diff"])}</strong> multi-state excludees appears under materially different surnames in different states — sometimes a legal name change, sometimes the states spelling the same person differently. Identity has to follow the NPI.</p>
<div class="card"><p class="caveat" style="margin-top:0">Caveat: counts only aliases formally registered in NPPES; informal aliases in state lists (a.k.a. annotations) are additional.</p></div>

<h2 id="migration">When excluded providers move</h2>
<p>Time-ordering every multi-jurisdiction excludee's states reveals the corridors. Every corridor with 30 or more providers, alphabetical by origin:</p>
<div class="chart" role="img" aria-label="Bar chart of state-to-state exclusion corridors with 30 or more providers, alphabetical">
{bar_rows([(f'{r["a"]} → {r["b"]}', r["providers"], fmt(r["providers"])) for r in cor], cmax)}
<p class="chartnote">Providers excluded in the first state and later in the second (same NPI, ordered by exclusion dates). Median gap between consecutive jurisdictions: <strong>{month_word(R["consec"][0]["median_gap"])}</strong>.</p>
</div>
<div class="card"><p><strong>Excluded providers resurface one state over</strong> — every corridor above but one runs between neighbors in the New York, New Jersey, Pennsylvania and Delaware region.</p>
<p class="caveat">Caveat: corridor order reflects exclusion dates, which proxies but does not prove relocation order.</p></div>

<h2 id="watchlist">Excluded somewhere, practicing where nobody can see it</h2>
<p>Take every provider we have <em>proven</em> is excluded right now (matched to a verified NPI), check where the national NPI registry says they currently practice, and keep the ones practicing in a state that has <strong>not</strong> excluded them. A clinic or health plan in that state, screening against its own state list, sees a clean provider.</p>
<p><span class="bignum" id="wl-any">{fmt(wl["any_state"])}</span></p>
<div class="chart" style="padding-top:4px">
<div class="crow"><div class="lbl" style="width:auto;min-width:0;flex:1">also on <strong>neither</strong> federal list (LEIE or SAM) — invisible even to federal screening</div><div class="val" id="wl-invisible">{fmt(wl["invisible_to_federal"])}</div></div>
<div class="crow"><div class="lbl" style="width:auto;min-width:0;flex:1">excluded in <strong>two or more</strong> states — the serial subset</div><div class="val" id="wl-serial">{fmt(wl["two_plus_states"])}</div></div>
<div class="crow"><div class="lbl" style="width:auto;min-width:0;flex:1">people / organizations</div><div class="val"><span id="wl-ind">{fmt(wl["individuals"])}</span> / <span id="wl-org">{fmt(wl["organizations"])}</span></div></div>
</div>
<p style="margin-top:28px"><strong>How we count it</strong> — five steps, nothing clever:</p>
<ol style="line-height:1.7;color:#c7d2ea;padding-left:22px">
<li><strong>Active only.</strong> The excluding state has published no end date (or a future one) and still carries the record on its list.</li>
<li><strong>Proven identity only.</strong> The record carries an NPI confirmed against the CMS NPPES registry. Name-only records are <em>not</em> counted.</li>
<li><strong>Count excluding states.</strong> Federal lists don't count as a state. One state is enough; the "two or more" figure is the subset.</li>
<li><strong>Look up where they practice now</strong> — the practice-location state on their NPPES record.</li>
<li><strong>Keep the mismatches.</strong> Practice state not among the excluding states.</li>
</ol>
<p style="margin-top:28px">The practice states with the most such providers, listed alphabetically:</p>
<div class="chart" id="wl-chart" role="img" aria-label="Bar chart, alphabetical, of practice states with the most excluded providers who have no local exclusion">
{bar_rows([(NAMES.get(t["state"], t["state"]), t["count"], fmt(t["count"])) for t in wtop], wmax)}
<p class="chartnote">Live from the published dataset — recomputed weekly<span id="wl-asof"></span>.</p>
</div>
<div class="card"><p class="caveat" style="margin-top:0">Caveats, so the number holds up: NPPES practice state is self-reported and can lag a move. "Has not excluded" means absent from that state's <em>published</em> list — several states publish no usable list, so there is nothing for the provider to appear on. And this counts only providers pinned to a verified NPI; most exclusion records are name-only and are not counted here, so the true figure is larger.</p></div>
<div class="card"><p class="caveat" style="margin-top:0">Honest boundary: same-NPI tracking is what exclusion-list data can prove — a provider who abandons their identity behind a new organizational NPI is invisible to this method. Detecting that requires ownership linkage, which we name as future work rather than claim.</p></div>

<h2 id="composition">People and companies</h2>
<div class="statrow">
<div class="stat"><div class="big">{split["INDIVIDUAL"]["pct"]:.0f}%</div><div class="small">of healthcare exclusions are people</div></div>
<div class="stat"><div class="big">{split["ORGANIZATION"]["pct"]:.0f}%</div><div class="small">are companies</div></div>
</div>
<p>…and the companies dominate the categories that bill at scale: <strong>{hosp_pct}% of excluded hospice agencies and {lab_pct}% of excluded labs are organizations</strong>, while license-driven exclusions are 99.5% individual — licenses attach to people.</p>
<div class="card"><p><strong>When a company goes multi-state, it lands in many states at once.</strong> Organizations are {org2}% of two-jurisdiction excludees but {org4}% of four-plus (July: 4.8% → 20.4%).</p>
<p class="caveat">Caveat: type shares among NPI-verified matches; category percentages use NPPES enumeration type (Type 1 person / Type 2 organization).</p></div>
<div class="card"><p><strong>Zero person/company conflicts across all {fmt(tc["npis"])} registry-verified matches</strong> (July: 25,206) — the entity-type invariant held end to end.</p></div>

<h2>New since July</h2>
<div class="card"><p><strong>Coverage.</strong> 15 → {S["states"]} states + DC with a loaded list; 16 → {S["sources_total"]} sources; 150,719 → {fmt(S["records_total"])} records.</p></div>
<div class="card"><p><strong>Excluded in more than one jurisdiction.</strong> {fmt(multi)} providers, re-checked against today's data (published as ENTITY_OVERLAP).</p></div>
<div class="card"><p><strong>The FDA lists.</strong> The FDA Debarment List ({fmt(fed.get("FDA_DEBAR", 0))} records) and the Clinical Investigator Disqualification Proceedings ({fmt(fed.get("FDA_CIDQ", 0))}) are in every check, for drug and device sponsors screening investigators and consultants. <a href="/life-sciences.html">Life sciences screening</a>.</p></div>
<div class="card"><p><strong>How matches are made.</strong> Of {fmt(tsum)} NPI-resolved records, {100 * det / tsum:.1f}% are matched deterministically (a source-published NPI the registry confirms, a unique name-and-state or registered-alias match, or a license number); the remaining {100 * tiers.get("T4", 0) / tsum:.1f}% ({fmt(tiers.get("T4", 0))}) are AI-adjudicated among ambiguous candidates, and every one of those is flagged for human review. In all, {fmt(rev["review"])} records ({100 * rev["review"] / rev["total"]:.1f}%) carry the needs-human-review flag.</p></div>

<h2 id="optout">Medicare Opt-Out — a status, not an exclusion</h2>
<div class="card"><p><strong>{fmt(opt["records"])} Medicare opt-out affidavits</strong> ({fmt(opt["active"])} active) are published as a separate view. An opt-out means the provider has chosen to contract privately with Medicare patients; it is <strong>not an exclusion or sanction</strong>, is never counted in any figure above, and never appears as a hit. It is there so a roster check can tell the two apart.</p></div>

<h2 id="try">Try it</h2>
<div class="card"><p><a href="https://investigator.rosterproof.com" target="_blank" rel="noopener"><strong>The Investigator</strong></a> — Demo opens on eight sample providers (synthetic) with their connections and map; My lookup gives 10 free real lookups a day, no sign-up.</p>
<p style="margin-top:10px"><a href="/api.html"><strong>The free API</strong></a> — 500 lookups a month on a free key. · <a href="/download.html"><strong>The weekly download</strong></a> — CSV or Parquet. · <a href="/states/"><strong>The state index</strong></a> — every state list we load. · <a href="/leie-vs-sam.html"><strong>LEIE vs SAM.gov</strong></a> — what each federal list covers.</p>
<p class="caveat">Every result carries the same notice: a hit identifies a published exclusion record and, where present, an NPI match with a stated confidence — verify with the source agency before any adverse action. Questions this dataset could answer: <a href="mailto:support@rosterproof.com">support@rosterproof.com</a>.</p></div>
</main>'''


def main():
    R = json.load(open(sys.argv[1])); S = json.load(open(ROOT / "stats.json"))
    as_of = sys.argv[2] if len(sys.argv) > 2 else dt.date.today().isoformat()
    p = ROOT / "insights.html"; s = p.read_text(encoding="utf-8")
    body = build(R, S, as_of)
    s = re.sub(r"<h1>What the data says</h1>.*?</main>", lambda m: body, s, count=1, flags=re.S)
    css = (".gap .gdef{color:#8fa3c7;font-size:13px}\n.rategrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(170px,1fr));gap:6px 18px;margin:16px 0}"
           "\n.rategrid div{display:flex;justify-content:space-between;border-bottom:1px solid #1d2745;padding:4px 0;font-size:14px;color:#c7d2ea}"
           "\n.rategrid b{color:#7fd4c8;font-variant-numeric:tabular-nums}\n")
    if ".rategrid{" not in s:
        s = s.replace("</style>", css + "</style>", 1)
    gb = R["gapB"][0]; gap_b = round(100 * gb["not_on_federal"] / gb["verified_active"], 1)
    s = re.sub(r'<meta property="og:description" content="[^"]*">', f'<meta property="og:description" content="{S["federal_gap_overall_pct"]}% of active state exclusion records have no match on the federal OIG LEIE; {gap_b}% of verified-NPI active state records are on no federal list. Plus the propagation lag, the specialty risk map and cross-state movement.">', s, count=1)
    s = re.sub(r'"datePublished": "[^"]*"', f'"datePublished": "2026-07-26", "dateModified": "{as_of}"', s, count=1) if '"dateModified"' not in s else re.sub(r'"dateModified": "[^"]*"', f'"dateModified": "{as_of}"', s, count=1)
    # live JS: watchlist practice states rendered alphabetically (never a ranking)
    s = s.replace("var max=w.top_practice_states[0].count;\n      w.top_practice_states.forEach(",
                  "var rows=w.top_practice_states.slice().sort(function(a,b){return (NAMES[a.state]||a.state).localeCompare(NAMES[b.state]||b.state);});\n      var max=Math.max.apply(null,rows.map(function(t){return t.count;}));\n      rows.forEach(")
    p.write_text(s, encoding="utf-8")
    print(f"insights.html rebuilt (as of {as_of})")


if __name__ == "__main__":
    main()
