/* Screen my roster — client-side CSV parsing, batches to api.rosterproof.com/v1/screen, downloadable report.
   Nothing is stored server-side except the API key's monthly usage count (free plan: 500 lookups per calendar month, 100 per request). */
(function () {
  var API = 'https://api.rosterproof.com';
  var keyIn = document.getElementById('skey'), ks = document.getElementById('keystate');
  try { var saved = localStorage.getItem('rp_api_key'); if (saved) { keyIn.value = saved; ks.textContent = '(saved in this browser)'; } } catch (_) {}

  document.getElementById('mkkey').addEventListener('click', function () {
    var em = document.getElementById('semail').value; if (!em) { ks.textContent = 'enter an email first'; return; }
    ks.textContent = 'creating…';
    fetch(API + '/v1/keys', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: em, org: '' }) })
      .then(function (r) { return r.json(); }).then(function (d) {
        if (d.api_key) { keyIn.value = d.api_key; try { localStorage.setItem('rp_api_key', d.api_key); } catch (_) {} ks.textContent = 'created — copy it from the box, it is not shown again (free plan: ' + d.monthly_lookups + ' lookups per month)'; }
        else ks.textContent = d.error || 'failed';
      }).catch(function () { ks.textContent = 'API not reachable'; });
  });

  document.getElementById('file').addEventListener('change', function (e) {
    var f = e.target.files[0]; if (!f) return;
    var rd = new FileReader(); rd.onload = function () { document.getElementById('roster').value = rd.result; }; rd.readAsText(f);
  });

  function cell(s) { return s.trim().replace(/^"|"$/g, '').replace(/""/g, '"'); }
  // quote-aware CSV line splitter: "Marketing Service, Inc" stays one cell; "" is an escaped quote
  function splitCsv(line) {
    var out = [], cur = '', inq = false;
    for (var i = 0; i < line.length; i++) {
      var ch = line[i];
      if (inq) { if (ch === '"') { if (line[i + 1] === '"') { cur += '"'; i++; } else inq = false; } else cur += ch; }
      else if (ch === '"') inq = true;
      else if (ch === ',') { out.push(cur); cur = ''; }
      else cur += ch;
    }
    out.push(cur); return out.map(function (x) { return x.trim(); });
  }
  function parseRoster(text) {
    var lines = text.split(/\r?\n/).map(function (l) { return l.trim(); }).filter(Boolean);
    if (!lines.length) return { npis: [], names: [], orgs: [], invalid: [] };
    var hdr = splitCsv(lines[0].toLowerCase()).map(cell);
    var iN = hdr.findIndex(function (h) { return /^npi/.test(h); });
    var iL = hdr.indexOf('last_name') >= 0 ? hdr.indexOf('last_name') : hdr.indexOf('last');
    var iF = hdr.indexOf('first_name') >= 0 ? hdr.indexOf('first_name') : hdr.indexOf('first');
    var iS = hdr.indexOf('state');
    var iO = ['organization', 'org', 'business_name', 'business'].map(function (h) { return hdr.indexOf(h); }).filter(function (i) { return i >= 0; })[0];
    if (iO === undefined) iO = -1;
    var hasHeader = (iN >= 0 || iL >= 0 || iO >= 0), npis = [], names = [], orgs = [], invalid = [], seen = {};
    lines.slice(hasHeader ? 1 : 0).forEach(function (l) {
      var c = splitCsv(l);
      var npi = ((hasHeader && iN >= 0) ? c[iN] : c[0] || '').replace(/\D/g, '');
      if (/^\d{10}$/.test(npi) && !seen[npi]) { seen[npi] = 1; npis.push(npi); }
      else if (hasHeader && iL >= 0 && c[iL]) { names.push({ last: c[iL], first: iF >= 0 ? c[iF] : '', state: iS >= 0 ? c[iS] : '' }); }
      else if (hasHeader && iO >= 0 && c[iO]) { orgs.push({ name: c[iO], state: iS >= 0 ? c[iS] : '' }); }
      else if (npi && !/^\d{10}$/.test(npi)) { invalid.push(((hasHeader && iN >= 0) ? c[iN] : c[0]) || npi); }
    });
    return { npis: npis, names: names, orgs: orgs, invalid: invalid };
  }

  var lastRows = [];
  function td(html, extra) { return '<td style="padding:7px 6px;border-bottom:1px solid #232e4a' + (extra || '') + '">' + html + '</td>'; }
  function esc(v) { return String(v == null ? '' : v).replace(/&/g, '&amp;').replace(/</g, '&lt;'); }

  document.getElementById('run').addEventListener('click', function () {
    var key = keyIn.value.trim(), st = document.getElementById('status');
    if (!key) { st.textContent = 'Create or paste an API key first.'; return; }
    var r = parseRoster(document.getElementById('roster').value), total = r.npis.length + r.names.length + r.orgs.length;
    if (!total) { st.textContent = r.invalid.length ? 'Not screened: ' + r.invalid.join(', ') + ' — an NPI is exactly 10 digits.' : 'No NPIs or names found.'; return; }
    try { localStorage.setItem('rp_api_key', key); } catch (_) {}
    st.textContent = 'Screening ' + total + ' entries…';
    var tb = document.querySelector('#results tbody'); tb.innerHTML = ''; lastRows = [];
    var hits = 0, done = 0, asof = '', batches = [], remaining = null, limit = null;
    r.invalid.forEach(function (v) { lastRows.push([v, 'INVALID', '', '', 'not a 10-digit NPI — not screened', '', '', '']); var t = document.createElement('tr'); t.innerHTML = td(esc(v)) + td('<span style="color:#f0c674">invalid</span>') + '<td colspan="6" style="padding:7px 6px;border-bottom:1px solid #232e4a;color:#f0c674">not a 10-digit NPI — not screened</td>'; tb.appendChild(t); });
    // batches stay within the free plan's 100 queries per request
    for (var i = 0; i < r.npis.length; i += 100) batches.push({ npis: r.npis.slice(i, i + 100) });
    for (var j = 0; j < r.names.length; j += 100) batches.push({ names: r.names.slice(j, j + 100) });
    for (var o = 0; o < r.orgs.length; o += 100) batches.push({ organizations: r.orgs.slice(o, o + 100) });
    (function next(k) {
      if (k >= batches.length) {
        st.textContent = 'Done: ' + total + ' screened, ' + hits + ' with a hit (snapshot as of ' + asof + ').' + (remaining !== null ? ' ' + remaining + ' of ' + limit + ' lookups left this month.' : '');
        document.getElementById('summary').textContent = total + ' entries · ' + hits + ' hits · as of ' + asof;
        document.getElementById('rescard').style.display = 'block'; document.getElementById('dl').disabled = false; return;
      }
      fetch(API + '/v1/screen', { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + key }, body: JSON.stringify(batches[k]) })
        .then(function (resp) { var rem = resp.headers.get('X-RateLimit-Remaining'); if (rem !== null) { remaining = Number(rem); limit = Number(resp.headers.get('X-RateLimit-Limit')); } return resp.json(); }).then(function (d) {
          if (d.error) { st.textContent = 'Error: ' + (d.message || d.error); return; }
          asof = d.as_of;
          d.results.forEach(function (res) {
            var q = res.query.npi || (res.query.name ? res.query.name + (res.query.state ? ' (' + res.query.state + ')' : '') : (res.query.last + ', ' + res.query.first + (res.query.state ? ' (' + res.query.state + ')' : '')));
            if (!res.matches.length) {
              lastRows.push([q, 'no', '', '', '', '', '', '']);
              var tr0 = document.createElement('tr'); tr0.innerHTML = td(esc(q)) + td('<span style="color:#8fa3c7">clear</span>') + '<td colspan="6" style="border-bottom:1px solid #232e4a"></td>'; tb.appendChild(tr0); return;
            }
            hits++;
            res.matches.forEach(function (m) {
              var nm = m.business_name || ((m.last_name || '') + ', ' + (m.first_name || ''));
              var tier = m.npi ? ((m.tier ? m.tier.confidence : '') + ' · ' + (m.npi_origin || '')) : 'name match only';
              lastRows.push([q, 'YES', m.source_id, nm, (m.is_active ? 'ACTIVE' : 'ended') + ' · ' + (m.exclusion_reason || ''), m.exclusion_start || '', m.npi ? m.npi + ' (' + tier + ')' : '', m.needs_human_review ? 'needs human review' : '']);
              var tr = document.createElement('tr');
              tr.innerHTML = td(esc(q)) + td('<span style="color:#7fd4c8;font-weight:600">HIT</span>') + td(esc(m.source_id)) + td(esc(nm))
                + td((m.is_active ? '<span style="color:#7fd4c8">active</span>' : 'ended') + ' · ' + esc(m.exclusion_reason || '')) + td(esc(m.exclusion_start || ''))
                + td(m.npi ? esc(m.npi) + '<br><span style="color:#8fa3c7">' + esc(tier) + '</span>' : '<span style="color:#8fa3c7">name match only</span>')
                + td(m.needs_human_review ? '<span style="color:#f0c674">review</span>' : '');
              tb.appendChild(tr);
            });
          });
          done += d.lookups; st.textContent = 'Screened ' + done + ' of ' + total + '…'; next(k + 1);
        }).catch(function () { st.textContent = 'The API is not reachable right now.'; });
    })(0);
  });

  document.getElementById('dl').addEventListener('click', function () {
    var hdr = ['query', 'hit', 'list', 'name_or_organization', 'status', 'since', 'npi_match', 'review'];
    var q = function (v) { v = String(v == null ? '' : v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
    var lines = ['# RosterProof screening report — ' + new Date().toISOString().slice(0, 10) + ' — VERIFY BEFORE ADVERSE ACTION: confirm any hit against the source agency (and OIG SSN-based search for LEIE). Attribution: https://rosterproof.com/attribution', hdr.join(',')]
      .concat(lastRows.map(function (r) { return r.map(q).join(','); }));
    var blob = new Blob([lines.join('\n')], { type: 'text/csv' });
    var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'rosterproof_screening_report.csv'; a.click();
  });
})();
