#!/usr/bin/env node
// visual-plan pack: lint the plan data, inline the runtime, write one self-contained HTML file.
// Usage: node pack.mjs plan.yaml [--out plan.html] [--strict]   (also plan.json, plan.js with `window.PLAN = {...}`, or a page with a <script id="plan"> block)
import { readFileSync, writeFileSync, existsSync } from 'node:fs';
import { dirname, join, basename, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import vm from 'node:vm';
import { createRequire } from 'node:module';

const here = dirname(fileURLToPath(import.meta.url));
const args = process.argv.slice(2);
if (!args[0]) { console.error('usage: node pack.mjs plan.yaml [--out plan.html] [--strict]'); process.exit(2); }
const src = resolve(args[0]);
const outIdx = args.indexOf('--out');
const out = outIdx >= 0 ? resolve(args[outIdx + 1]) : (/\.(ya?ml|json|js|mjs)$/.test(src) ? src.replace(/\.(ya?ml|json|js|mjs)$/, '.html') : src.replace(/\.html$/, '.packed.html'));
const strict = args.includes('--strict');

const raw = readFileSync(src, 'utf8');
const errors = [], warnings = [];
const err = (m) => errors.push(m), warn = (m) => warnings.push(m);

// ---- read the plan data: plan.yaml (the authoring format), plan.json, plan.js (`window.PLAN = {...}`), or a page with a <script id="plan"> block
const isYaml = /\.ya?ml$/.test(src), isJson = /\.json$/.test(src), isJs = /\.(js|mjs)$/.test(src);
const isContent = isYaml || isJson || isJs;
let P;
if (isYaml) {
  const yaml = createRequire(import.meta.url)('./vendor/js-yaml.js');
  try { P = yaml.load(raw); } catch (e) { console.error('error: plan.yaml does not parse: ' + e.message); process.exit(1); }
} else if (isJson) {
  try { P = JSON.parse(raw); } catch (e) { console.error('error: plan.json does not parse: ' + e.message); process.exit(1); }
} else {
  const m = isJs ? [null, raw] : raw.match(/<script id="plan">([\s\S]*?)<\/script>/);
  if (!m) { console.error('error: no <script id="plan"> block'); process.exit(1); }
  const ctx = { window: {} };
  try { vm.runInNewContext(m[1], ctx); } catch (e) { console.error('error: plan data does not evaluate: ' + e.message); process.exit(1); }
  P = ctx.window.PLAN;
}
if (!P || !Array.isArray(P.blocks)) { console.error('error: window.PLAN with a blocks array is required'); process.exit(1); }
// profile: `plan` (a design decision, the default) or `explainer` (an existing system, for explainer and review skills)
const profile = P.profile || 'plan';
if (!['plan', 'explainer'].includes(profile)) { console.error('error: profile must be plan or explainer, not ' + profile); process.exit(1); }
const plan = profile === 'plan';

// ---- helpers
const strip = (h) => String(h == null ? '' : h).replace(/<pre[\s\S]*?<\/pre>/g, ' ').replace(/<code>[\s\S]*?<\/code>/g, ' ').replace(/<[^>]+>/g, ' ').replace(/&[a-z]+;/g, ' ').replace(/\s+/g, ' ').trim();
const walk = (v, path, fn) => {
  if (typeof v === 'string') fn(v, path);
  else if (Array.isArray(v)) v.forEach((x, i) => walk(x, path + '[' + i + ']', fn));
  else if (v && typeof v === 'object') Object.keys(v).forEach((k) => walk(v[k], path + '.' + k, fn));
};

// ---- structure
const CORE = plan ? ['problem', 'map', 'decisions', 'goal', 'scope'] : ['map', 'terms'];
const kinds = P.blocks.map((b) => b.kind);
let last = -1;
for (const k of CORE) {
  const i = kinds.indexOf(k);
  if (i < 0) err('core block missing: ' + k);
  else if (i < last) err('core block out of order: ' + k);
  else last = i;
}
if (!P.title || P.title.split(/\s+/).length > 8) warn('title: 3 to 7 words');
// A design block names the locked mockup file; the pack inlines it after the lint, so the mockup's own
// markup and script never meet the plan's word and code rules.
for (const b of P.blocks.filter((x) => x.kind === 'design')) {
  if (!b.file) err('design: needs a file, the locked mockup beside the plan');
  else if (!existsSync(resolve(dirname(src), b.file))) err('design: file not found: ' + b.file);
}
if (!P.opening) err('opening is missing');

const mapBlock = P.blocks.find((b) => b.kind === 'map');
if (mapBlock) {
  const N = mapBlock.nodes || {};
  if (!N[mapBlock.root]) err('map: root node "' + mapBlock.root + '" is missing');
  const depth = {}; depth[mapBlock.root] = 1;
  const edges = [];
  for (const id of Object.keys(N)) {
    const n = N[id];
    for (const k of Object.keys(n.children || {})) edges.push([id, n.children[k], k]);
    if (n.view && n.view.type === 'diagram') for (const g of (n.view.svg || '').match(/data-go="([^"]+)"/g) || []) edges.push([id, g.slice(9, -1), 'shape']);
    if (n.view && n.view.type === 'diagram') for (const g of (n.view.svg || '').match(/data-n="([^"]+)"/g) || []) { const nm = g.slice(8, -1); if (!(n.notes || {})[nm]) warn('map: node "' + id + '" shape "' + nm + '" has no note'); }
    if (n.view && n.view.type === 'diagram') for (const b of n.view.boxes || []) {
      if (b.node) { edges.push([id, b.node, 'box']); if (!N[b.node]) err('map: node "' + id + '" has a box for "' + b.node + '", which does not exist'); }
      else if (b.part) { if (!(n.notes || {})[b.part]) warn('map: node "' + id + '" box "' + b.part + '" has no note'); }
      else err('map: node "' + id + '" has a box with neither node nor part');
      if (b.x == null || b.y == null) err('map: node "' + id + '" box "' + (b.node || b.part) + '" has no x, y');
    }
    if (n.view && n.view.type === 'diagram' && !n.view.boxes && !/<svg/.test(n.view.svg || '')) err('map: node "' + id + '" diagram has no boxes and its svg is not a full <svg> element');
    if (n.view && n.view.type === 'parts') for (const p of n.view.parts) if (!(n.notes || {})[p[1]]) warn('map: node "' + id + '" part "' + p[1] + '" has no note');
  }
  let changed = true;
  while (changed) { changed = false; for (const [a, b] of edges) { if (depth[a] && !depth[b]) { depth[b] = depth[a] + 1; changed = true; } } }
  for (const [a, b] of edges) if (!N[b]) err('map: node "' + a + '" opens "' + b + '", which does not exist');
  for (const id of Object.keys(N)) { if (!depth[id]) warn('map: node "' + id + '" is not reachable from the root'); else if (depth[id] > 3) err('map: node "' + id + '" is at depth ' + depth[id] + '; the cap is 3'); }
}

const dec = P.blocks.find((b) => b.kind === 'decisions');
if (dec) {
  for (const d of dec.open || []) {
    if (!d.id) err('decision without id: ' + strip(d.title));
    if (!d.context || !/Problem/.test(d.context)) err('decision "' + d.id + '": context must open with the problem');
    for (const w of ['Why now', 'Known', 'Affected']) if (!new RegExp(w).test(d.context || '')) warn('decision "' + d.id + '": context has no "' + w + '"');
    if (!d.options || d.options.length < 2) err('decision "' + d.id + '": needs 2 or more options');
    for (const o of d.options || []) for (const f of ['label', 'how', 'gains', 'costs', 'effort', 'reversible']) if (!o[f]) err('decision "' + d.id + '": option "' + strip(o.label) + '" lacks ' + f);
  }
  if ((dec.open || []).length === 0 && !(P.status && /lock/i.test(P.status.text || ''))) warn('no open decision: the status should say locked');
}

// ---- no code in the plan
const ALLOWED_CODE = /^blocks\[\d+\]\.(today|cards\[\d+\]\.html|open\[\d+\]\.context)/; // current state, data cards, decision context
const ALLOWED_REF = /^blocks\[\d+\]\.(today|open\[\d+\]\.context|settled)/;
walk(P.blocks, 'blocks', (s, path) => {
  if (/<pre|```|\bdef |\bclass \w+\(|=>\s*\{|function\s*\(/.test(s) && !ALLOWED_CODE.test(path) && !/\.svg$/.test(path) && !/\.calls$|view\.text$|\.example$/.test(path)) err('code in the plan at ' + path);
  if (plan && /\b[\w\/-]+\.(py|ts|js|go|java|rs|rb|sql|md|yaml|yml|toml)(:\d+)?\b/.test(strip(s)) && !ALLOWED_REF.test(path) && !/\.svg$|\.calls$|view\.text$|\.example$|retired/.test(path)) warn('file reference outside current state or a decision at ' + path);
});

// ---- retired terms
for (const t of P.retired || []) {
  const re = new RegExp('\\b' + t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'i');
  walk(P.blocks, 'blocks', (s, path) => { if (!/\.svg$|retired|\.extra\[\d+\]/.test(path) && re.test(strip(s))) err('retired term "' + t + '" at ' + path); }); // the older-words card names them on purpose
}

// ---- badges: a bold word with a colon is a tag that is not a badge
walk(P.blocks, 'blocks', (s, path) => { const mm = s.match(/<b>(Keep|Flag|Recommended|New|Exists|Open|Settled|Note|Risk)[^<]{0,3}<\/b>/i); if (mm) warn('tag written as bold, use a badge: "' + mm[0] + '" at ' + path); });

// ---- STE (plan only: an explainer follows its own style rules)
const BAD = { utilize: 'use', leverage: 'use', perform: 'do', ensure: 'make sure', verify: 'make sure', demonstrate: 'show', indicate: 'show', commence: 'start', terminate: 'stop', obtain: 'get', provide: 'give', 'prior to': 'before', 'in order to': 'to', however: 'but', additionally: 'also', 'etc.': 'list the items', whatever: 'say the thing', should: 'must or can', may: 'can', might: 'can' };
const seen = new Set();
walk(P.blocks, 'blocks', (s, path) => {
  if (/\.svg$|\.calls$|view\.text$|\.example$|exampleLabel|retired|\.label$/.test(path)) return;
  const text = strip(s); if (!text) return;
  if (plan && /\b\w+n't\b|\b(it|that|there|what|who)'s\b|\b(I|you|we|they)'(re|ve|ll|d)\b/i.test(text)) warn('contraction at ' + path);
  if (plan) for (const w of Object.keys(BAD)) { const re = new RegExp('\\b' + w.replace('.', '\\.') + '\\b', 'i'); if (re.test(text)) { const k = w + '@' + path; if (!seen.has(k)) { seen.add(k); warn('STE: "' + w + '" → ' + BAD[w] + ' at ' + path); } } }
  for (const sent of text.split(/(?<=[.!?;:])\s+/)) { const n = sent.split(/\s+/).length; if (n > 30) warn('long sentence (' + n + ' words) at ' + path + ': "' + sent.slice(0, 60) + '…"'); }
  if (plan && /\b(is|are|was|were|be|been|being)\s+\w+ed\s+by\b/i.test(text)) warn('passive voice at ' + path);
});

// ---- report
for (const w of warnings) console.log('warn  ' + w);
for (const e of errors) console.log('error ' + e);
console.log(errors.length + ' error(s), ' + warnings.length + ' warning(s)');
if (errors.length || (strict && warnings.length)) process.exit(1);

// ---- inline each design reference
for (const b of P.blocks) if (b.kind === 'design' && b.file) b.srcdoc = readFileSync(resolve(dirname(src), b.file), 'utf8');

// ---- compose the page and inline the runtime
const css = readFileSync(join(here, 'visualplan.css'), 'utf8');
const js = readFileSync(join(here, 'visualplan.js'), 'utf8');
const shortTitle = (P.shortTitle || P.title).replace(/[<>&]/g, '');
const html = isContent
  ? '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer">\n<title>' + shortTitle + '</title>\n<link rel="stylesheet" href="visualplan.css">\n</head><body>\n<script id="plan">\nwindow.PLAN = ' + JSON.stringify(P).replace(/</g, '\\u003c') + ';\n</script>\n<script src="visualplan.js"></script>\n</body></html>\n'
  : raw;
let packed = html
  .replace(/<link rel="stylesheet" href="[^"]*visualplan\.css">/, '<style>\n' + css + '\n</style>')
  .replace(/<script src="[^"]*visualplan\.js"( defer)?><\/script>/, '')
  .replace(/<\/body>/, '<script>\n' + js + '\n</script>\n</body>');
if (!/<meta name="referrer"/.test(packed)) packed = packed.replace('<head>', '<head><meta name="referrer" content="no-referrer">');
writeFileSync(out, packed);
console.log('wrote ' + basename(out) + ' (' + Math.round(packed.length / 1024) + ' KB)');
