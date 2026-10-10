"""The stylesheet and script embedded in the HTML full assessment.

Kept apart from the renderer so the renderer stays readable, and kept as module
constants rather than files on disk so the report has no build step and no
runtime dependency on where the skill is installed.

Two rules govern everything here:

* **Nothing leaves the document.** No font import, no CDN, no fetch. A report
  that phoned home would leak which issue someone is reading to whoever hosts
  the asset, and it would stop working on a laptop on a plane.
* **Colour is never the only signal.** Every outcome pill carries its label as
  text. The palette is there to let a reader skim; it is not what the report
  says. That also means the thing survives a greyscale print.

The script is deliberately small: it filters rows that are already in the DOM
and toggles `open` on native `<details>`. There is no client-side templating
and no embedded JSON payload, so no source text ever reaches a JavaScript
parser - the escaping problem is solved by not having the problem.
"""

from __future__ import annotations

CSS = """
:root {
  color-scheme: light dark;
  --bg: #ffffff;
  --bg-sunk: #f7f7f8;
  --bg-card: #ffffff;
  --fg: #16181d;
  --fg-muted: #5c6370;
  --fg-faint: #858b96;
  --line: #e3e5e9;
  --line-strong: #cdd1d8;
  --link: #1f5fbf;
  --accent-warn-bg: #fdf4e3;
  --accent-warn-line: #e8c98a;
  --accent-warn-fg: #6b4e11;
  --met-bg: #e4f2e8; --met-fg: #1d5733; --met-line: #bcdcc8;
  --partial-bg: #fcf0d6; --partial-fg: #6d4f12; --partial-line: #ecd4a2;
  --unmet-bg: #fbe4e6; --unmet-fg: #7a2430; --unmet-line: #efc2c8;
  --unverified-bg: #eceef1; --unverified-fg: #4a515c; --unverified-line: #d7dae0;
  --radius: 10px;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #15171b;
    --bg-sunk: #1b1e23;
    --bg-card: #1b1e23;
    --fg: #e8eaed;
    --fg-muted: #a3aab6;
    --fg-faint: #7d848f;
    --line: #2b2f36;
    --line-strong: #3b414a;
    --link: #79aaf0;
    --accent-warn-bg: #2e2716;
    --accent-warn-line: #5d4c23;
    --accent-warn-fg: #e8cd8e;
    --met-bg: #1b3326; --met-fg: #9ad7b2; --met-line: #2d5640;
    --partial-bg: #352c16; --partial-fg: #e3c483; --partial-line: #574728;
    --unmet-bg: #382125; --unmet-fg: #eda7b0; --unmet-line: #5a333a;
    --unverified-bg: #24272d; --unverified-fg: #b3bac5; --unverified-line: #3a3f47;
  }
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue",
    Arial, "Noto Sans", sans-serif;
  font-size: 15px;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

/* Issue text carries file paths and refs with no break opportunities in them.
   Without this one declaration a single `filter/src/builtins/http/ai/...` sets
   the page's minimum width and every other section inherits a sideways
   scrollbar from it. */
.wrap { max-width: 1080px; margin: 0 auto; padding: 40px 28px 72px; overflow-wrap: break-word; }

/* The outcome table has five columns and a fixed minimum. On a phone it is the
   one element that cannot shrink, so it scrolls inside its own box rather than
   widening the document. */
.scroll-x { overflow-x: auto; }

a { color: var(--link); }
a:focus-visible, summary:focus-visible, button:focus-visible,
input:focus-visible, select:focus-visible {
  outline: 2px solid var(--link);
  outline-offset: 2px;
  border-radius: 4px;
}

code, .mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  font-size: 0.92em;
}

/* --- header ----------------------------------------------------------- */

.head { display: flex; gap: 24px; align-items: flex-start; justify-content: space-between; }
.eyebrow {
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-size: 11px;
  font-weight: 600;
  color: var(--fg-faint);
  margin: 0 0 10px;
}
h1 { font-size: 30px; line-height: 1.2; margin: 0 0 8px; font-weight: 650; letter-spacing: -0.01em; }
.meta { color: var(--fg-muted); font-size: 14px; margin: 0; }
.meta .sep { color: var(--fg-faint); padding: 0 6px; }
.epics { margin: 8px 0 0; padding: 0; list-style: none; font-size: 14px; }
.epics li { margin: 2px 0; }

button.toggle {
  font: inherit;
  font-size: 13px;
  padding: 8px 14px;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: var(--bg-card);
  color: var(--fg);
  cursor: pointer;
  white-space: nowrap;
}
button.toggle:hover { background: var(--bg-sunk); }

/* --- banner ----------------------------------------------------------- */

.banner {
  margin: 26px 0 0;
  padding: 12px 16px;
  border: 1px solid var(--accent-warn-line);
  background: var(--accent-warn-bg);
  color: var(--accent-warn-fg);
  border-radius: var(--radius);
  font-size: 14px;
}
.banner p { margin: 0 0 6px; font-weight: 600; }
.banner ul { margin: 0; padding-left: 20px; font-weight: 400; }
.banner li { margin: 3px 0; }

/* --- sections --------------------------------------------------------- */

section { margin-top: 38px; padding-top: 30px; border-top: 1px solid var(--line); }
section.first { border-top: 0; padding-top: 0; }
h2 { font-size: 21px; margin: 0 0 16px; font-weight: 620; letter-spacing: -0.01em; }
h3 { font-size: 15px; margin: 0 0 10px; font-weight: 620; }

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; align-items: start; }

.card {
  border: 1px solid var(--line);
  border-radius: var(--radius);
  background: var(--bg-card);
  padding: 18px 20px;
}
.card h3 { margin-bottom: 12px; }
.note { color: var(--fg-muted); font-size: 12.5px; margin: 10px 0 0; }

table { border-collapse: collapse; width: 100%; font-size: 14px; }
th, td { text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--line); }
th { font-weight: 600; color: var(--fg-muted); font-size: 12.5px; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
tbody tr:last-child td { border-bottom: 0; }

dl.facts { margin: 0; display: grid; grid-template-columns: auto 1fr; gap: 0; }
dl.facts dt, dl.facts dd {
  margin: 0;
  padding: 9px 0;
  border-bottom: 1px solid var(--line);
  font-size: 14px;
}
dl.facts dt { color: var(--fg-muted); padding-right: 18px; }
dl.facts dd { text-align: right; }
dl.facts > :nth-last-child(1), dl.facts > :nth-last-child(2) { border-bottom: 0; }

/* --- decisions -------------------------------------------------------- */

.decision {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 18px;
  padding: 14px 0;
  border-bottom: 1px solid var(--line);
  align-items: start;
}
.decision:last-child { border-bottom: 0; }
.decision .kind {
  text-transform: uppercase;
  letter-spacing: 0.07em;
  font-size: 10.5px;
  font-weight: 650;
  color: var(--fg-faint);
}
.decision .title { font-weight: 600; margin: 3px 0 2px; }
.decision .body { color: var(--fg-muted); font-size: 14px; }
.decision .refs { font-size: 13px; color: var(--fg-muted); margin-top: 4px; }
.decision .links { font-size: 13px; text-align: right; white-space: nowrap; }
.decision .links a { display: inline-block; margin-left: 10px; }

/* --- controls --------------------------------------------------------- */

.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  align-items: center;
  margin-bottom: 8px;
}
.controls input[type=search], .controls select {
  font: inherit;
  font-size: 14px;
  padding: 7px 10px;
  border: 1px solid var(--line-strong);
  border-radius: 8px;
  background: var(--bg-card);
  color: var(--fg);
}
.controls input[type=search] { flex: 1 1 260px; min-width: 180px; }
.controls label.check { display: flex; align-items: center; gap: 7px; font-size: 14px; cursor: pointer; }
.count { color: var(--fg-muted); font-size: 13px; margin: 0 0 14px; }

/* --- requirement rows ------------------------------------------------- */

.group { margin-bottom: 26px; }
.group > h3 { display: flex; gap: 10px; align-items: baseline; }
.group > h3 .n { color: var(--fg-faint); font-weight: 500; font-size: 13px; }

.rows { border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; }
.rowhead, .rowline {
  display: grid;
  grid-template-columns: 22px 150px 1fr 120px 190px;
  gap: 12px;
  align-items: center;
  padding: 10px 14px;
}
.rowhead {
  background: var(--bg-sunk);
  font-size: 12.5px;
  font-weight: 600;
  color: var(--fg-muted);
  border-bottom: 1px solid var(--line);
}
details.row { border-bottom: 1px solid var(--line); }
details.row:last-child { border-bottom: 0; }
details.row > summary { list-style: none; cursor: pointer; }
details.row > summary::-webkit-details-marker { display: none; }
details.row > summary:hover { background: var(--bg-sunk); }
.chev { color: var(--fg-faint); transition: transform 0.12s ease; font-size: 11px; }
details.row[open] .chev { transform: rotate(90deg); }
.cid { font-weight: 600; font-size: 13.5px; }
.cq { color: var(--fg-muted); font-size: 13px; }

/* The finding is the model's coverage sentence and is often a paragraph. It is
   clamped rather than truncated in the renderer: the whole string stays in the
   DOM, so the search box still matches on text the collapsed row is not
   showing, and expanding reveals it in full. */
.cfind {
  color: var(--fg-muted);
  font-size: 14px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12.5px;
  font-weight: 600;
  border: 1px solid transparent;
  white-space: nowrap;
}
.badge-met { background: var(--met-bg); color: var(--met-fg); border-color: var(--met-line); }
.badge-partial { background: var(--partial-bg); color: var(--partial-fg); border-color: var(--partial-line); }
.badge-unmet { background: var(--unmet-bg); color: var(--unmet-fg); border-color: var(--unmet-line); }
.badge-unverified { background: var(--unverified-bg); color: var(--unverified-fg); border-color: var(--unverified-line); }

.detail {
  background: var(--bg-sunk);
  border-top: 1px solid var(--line);
  padding: 16px 18px 18px 48px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 18px 28px;
}
.detail h4 {
  margin: 0 0 5px;
  font-size: 12.5px;
  font-weight: 650;
  color: var(--fg-muted);
}
.detail .block { font-size: 14px; }
.detail .block + .block { margin-top: 14px; }
.detail blockquote {
  margin: 0;
  padding-left: 12px;
  border-left: 2px solid var(--line-strong);
  color: var(--fg);
}
.detail ul { margin: 0; padding-left: 18px; }
.detail li { margin: 2px 0; }
.detail .when { color: var(--fg-faint); font-size: 12.5px; }

.empty { color: var(--fg-muted); font-style: italic; padding: 18px 14px; }

/* --- footer ----------------------------------------------------------- */

.foot { color: var(--fg-muted); font-size: 13px; }
.foot ul { margin: 0; padding-left: 18px; }
.foot li { margin: 4px 0; }
.colophon { margin-top: 36px; padding-top: 18px; border-top: 1px solid var(--line);
  color: var(--fg-faint); font-size: 12.5px; }

/* --- narrow ----------------------------------------------------------- */

@media (max-width: 820px) {
  .wrap { padding: 26px 16px 56px; }
  h1 { font-size: 24px; }
  .grid-2, .detail { grid-template-columns: 1fr; }
  th, td { padding: 8px 7px; }
  /* Label above value, both left-aligned. A right-aligned value in a 1fr
     column puts the long ones hard against the card edge. */
  dl.facts { grid-template-columns: 1fr; }
  dl.facts dt { padding: 9px 0 0; border-bottom: 0; }
  dl.facts dd { padding: 0 0 9px; text-align: left; }
  .head { flex-direction: column; gap: 14px; }
  .rowhead { display: none; }
  .rowline { grid-template-columns: 18px 1fr; gap: 4px 10px; }
  .rowline .cfind, .rowline .cout, .rowline .cq { grid-column: 2; }
  .decision { grid-template-columns: 1fr; }
  .decision .links { text-align: left; white-space: normal; }
  .decision .links a { margin: 0 12px 0 0; }
  .detail { padding-left: 18px; }
}

/* --- print ------------------------------------------------------------ */

@media print {
  :root { --bg: #fff; --bg-card: #fff; --bg-sunk: #fff; --fg: #000; --fg-muted: #333;
    --fg-faint: #555; --line: #bbb; --line-strong: #999; --link: #00c; }
  body { font-size: 10.5pt; }
  .wrap { max-width: none; padding: 0; }
  .no-print { display: none !important; }
  /* Every row opens: a printed report that hid its evidence behind a
     disclosure triangle would be a worse document than the Markdown one.
     Both declarations are needed. A closed <details> puts size containment on
     its content, so forcing the panel to display paints it but leaves the row
     sized as if it were empty - forty-nine evidence panels printed on top of
     the rows beneath them. `::details-content` lifts the containment; the
     `beforeprint` handler below does the same job in a browser that does not
     support it yet. */
  details.row::details-content { content-visibility: visible; block-size: auto; }
  details.row > .detail { display: grid !important; }
  /* Unclamped on paper: there is no disclosure triangle to click. */
  .cfind { display: block; overflow: visible; -webkit-line-clamp: none; line-clamp: none; }
  .chev { display: none; }
  .rows, .card, details.row { break-inside: avoid; }
  section { break-before: auto; page-break-inside: auto; }
  a { text-decoration: none; }
  a[href^="http"]::after { content: " (" attr(href) ")"; font-size: 8.5pt; color: #555; }
  .detail { background: #fff; }
}
"""


# Filtering only ever toggles `hidden` on elements that are already in the
# document, and expanding only ever sets `open`. Nothing here builds markup
# from a string, so there is no path from issue text to the HTML parser.
JS = """
(function () {
  'use strict';
  var rows = Array.prototype.slice.call(document.querySelectorAll('details.row'));
  var groups = Array.prototype.slice.call(document.querySelectorAll('.group'));
  var search = document.getElementById('q');
  var outcome = document.getElementById('f-outcome');
  var type = document.getElementById('f-type');
  var attention = document.getElementById('f-attention');
  var count = document.getElementById('visible-count');
  var toggle = document.getElementById('toggle-all');
  if (!rows.length) { return; }

  function matches(row, term) {
    if (term && row.getAttribute('data-search').indexOf(term) === -1) { return false; }
    if (outcome.value && row.getAttribute('data-outcome') !== outcome.value) { return false; }
    if (type.value && row.getAttribute('data-type') !== type.value) { return false; }
    if (attention.checked && row.getAttribute('data-attention') !== '1') { return false; }
    return true;
  }

  function apply() {
    var term = search.value.trim().toLowerCase();
    var shown = 0;
    rows.forEach(function (row) {
      var ok = matches(row, term);
      row.hidden = !ok;
      if (ok) { shown += 1; }
    });
    groups.forEach(function (group) {
      var here = group.querySelectorAll('details.row:not([hidden])').length;
      group.hidden = here === 0;
      // The group heading has to agree with the filter too. Leaving it at the
      // group total under an active filter is how a reader concludes a source
      // has nine criteria needing attention when it has two.
      var tally = group.querySelector('.n');
      if (tally) {
        var all = tally.getAttribute('data-total');
        tally.textContent = here === Number(all)
          ? tally.getAttribute('data-label')
          : here + ' of ' + all + ' shown';
      }
    });
    var total = rows.length;
    count.textContent = shown === total
      ? 'Showing all ' + total + ' criteria'
      : 'Showing ' + shown + ' of ' + total + ' criteria';
  }

  function visible() {
    return rows.filter(function (row) { return !row.hidden; });
  }

  function setToggleLabel() {
    var open = visible().some(function (row) { return row.open; });
    toggle.textContent = open ? 'Collapse evidence' : 'Expand evidence';
    toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
  }

  // Acts on the visible rows only. Expanding rows a filter has hidden would
  // leave the button lying about what the next click does.
  toggle.addEventListener('click', function () {
    var target = !visible().some(function (row) { return row.open; });
    visible().forEach(function (row) { row.open = target; });
    setToggleLabel();
  });
  rows.forEach(function (row) { row.addEventListener('toggle', setToggleLabel); });

  [search, outcome, type, attention].forEach(function (control) {
    control.addEventListener('input', function () { apply(); setToggleLabel(); });
  });

  // Paper has no disclosure triangle, so every visible row opens for the
  // print and goes back to how the reader left it afterwards. The print
  // stylesheet does this on its own in a browser that supports
  // `::details-content`; this is the fallback, and it is also what makes the
  // restore correct rather than leaving everything expanded.
  var restore = [];
  window.addEventListener('beforeprint', function () {
    restore = visible().filter(function (row) { return !row.open; });
    restore.forEach(function (row) { row.open = true; });
  });
  window.addEventListener('afterprint', function () {
    restore.forEach(function (row) { row.open = false; });
    restore = [];
    setToggleLabel();
  });

  apply();
  setToggleLabel();
})();
"""
