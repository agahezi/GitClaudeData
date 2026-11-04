/* visual-plan runtime. Renders window.PLAN: opening, examples, blocks (core and extras), the map as a node
   tree of depth 3 with zoom, decisions with option panels, comments, and the Respond sheet. No dependencies. */
(function () {
  'use strict';
  var P = null;

  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function tag(cls, text) { return '<span class="tag ' + esc(cls) + '">' + esc(text || cls) + '</span>'; }
  function el(html) { var t = document.createElement('template'); t.innerHTML = html.trim(); return t.content.firstChild; }
  var store = { picks: {}, comments: {}, struck: {} };
  function save() { try { localStorage.setItem('visual-plan:' + P.title, JSON.stringify(store)); } catch (e) {} }

  /* ---------- blocks ---------- */
  var KIND_TITLES = { problem: 'Problem, and how it works today', design: 'Design reference', map: 'Map', terms: 'Terms', traces: 'Traces', constraints: 'Constraints', data: 'Data models', decisions: 'Decisions', risks: 'Risks, and what changes for a reader', goal: 'Goal', scope: 'Scope', reused: 'Reused', section: '' };
  var TOC_TITLES = { problem: 'Problem', design: 'Design', map: 'Map', terms: 'Terms', traces: 'Traces', constraints: 'Constraints', data: 'Data models', decisions: 'Decisions', risks: 'Risks', goal: 'Goal', scope: 'Scope', reused: 'Reused' };

  function commentBtn(key, label) {
    var has = store.comments[key] ? ' has' : '';
    return '<button type="button" class="cbtn' + has + '" data-c="' + esc(key) + '" data-label="' + esc(label || key) + '" title="Comment on this part">' + (has ? 'comment ✓' : 'comment') + '</button>';
  }
  function card(key, inner, label) { return '<div class="card">' + commentBtn(key, label || strip(inner).slice(0, 60)) + inner + '</div>'; }
  function strip(h) { var t = document.createElement('div'); t.innerHTML = h; return (t.textContent || '').replace(/\s+/g, ' ').trim(); }
  function list(items) { return '<ul>' + items.map(function (i) { return '<li>' + i + '</li>'; }).join('') + '</ul>'; }

  function renderBlock(b, i) {
    var id = b.id || b.kind + (b.kind === 'section' ? i : '');
    var title = b.title || KIND_TITLES[b.kind] || '';
    var h = '<section class="block" id="' + esc(id) + '">' + (title ? '<h2 class="sec">' + title + '</h2>' : '') + (b.sub ? '<p class="sub">' + b.sub + '</p>' : '');
    switch (b.kind) {
      case 'problem':
        h += '<div class="grid2">' + card(id + '/problem', '<h3>Problem</h3><p>' + b.problem + '</p>') +
             card(id + '/today', '<h3>' + esc(b.today.label || 'How it works today') + '</h3>' + list(b.today.items)) + '</div>';
        break;
      case 'map':
        h += '<div class="crumbs" id="crumbs"></div><div class="stage"><div id="overview"><div class="ov" data-scroll="scroll sideways →"></div><div class="hint">' +
             (b.legend || []).map(function (k) { return '<span class="key"><i class="' + esc(k[0]) + '"></i>' + esc(k[1]) + '</span>'; }).join('') +
             (b.note ? '<span>' + b.note + '</span>' : '') + '</div></div><div class="detail" id="detail" hidden></div></div>' +
             (b.walkthrough ? '<p class="sub" style="margin-top:10px"><b>In two lines:</b> ' + b.walkthrough + '</p>' : '');
        break;
      case 'terms':
        h += '<div class="termflow">' + (b.cards || []).map(function (c, j) {
          return (j ? '<span class="sep" aria-hidden="true">→</span>' : '') + '<div class="tcard">' + commentBtn(id + '/term/' + j, c.term) + '<span class="term ' + esc(c.cls || 'car') + '">' + esc(c.term) + '</span><b class="tt">' + c.title + '</b><p>' + c.text + '</p>' + (c.example ? '<p class="ex">' + c.example + '</p>' : '') + '</div>';
        }).join('') + '</div>';
        if (b.extra && b.extra.length) h += '<div class="grid2" style="margin-top:14px">' + b.extra.map(function (x, j) { return card(id + '/' + j, '<h3>' + x.title + '</h3><p>' + x.html + '</p>', strip(x.title)); }).join('') + '</div>';
        break;
      case 'traces':
        h += renderCalls(b.calls, id + '/calls');
        if (b.cards && b.cards.length) h += '<div class="grid2" style="margin-top:14px">' + b.cards.map(function (c, j) { return card(id + '/' + j, '<h3>' + (c.badge ? tag(c.badge) : '') + c.title + '</h3><p>' + c.html + '</p>', strip(c.title)); }).join('') + '</div>';
        break;
      case 'constraints':
        h += '<div class="tblwrap"><table class="deftable"><tr><th style="width:34%">Constraint</th><th style="width:20%">Applied by</th><th>Keep, or flag</th><th class="ccol"></th></tr>' +
             b.rows.map(function (r, k) { return '<tr><td>' + r.value + '</td><td>' + r.by + '</td><td>' + (r.badge ? tag(r.badge) : '') + r.text + '</td><td class="ccol">' + commentBtn(id + '/row/' + k, strip(r.value)) + '</td></tr>'; }).join('') + '</table></div>';
        break;
      case 'data':
        h += '<div class="grid2">' + b.cards.map(function (c, j) { return card(id + '/' + j, '<h3>' + (c.badge ? tag(c.badge) : '') + c.title + '</h3>' + c.html, strip(c.title)); }).join('') + '</div>';
        break;
      case 'decisions':
        h += renderDecisions(b, id);
        break;
      case 'risks':
        h += '<div class="grid2">' + card(id + '/risks', '<h3>Risks</h3>' + list(b.risks), 'Risks') + card(id + '/changes', '<h3>Behaviour changes</h3>' + list(b.changes), 'Behaviour changes') + '</div>';
        break;
      case 'goal':
        h += card(id, list(b.items), 'Goal'); break;
      case 'scope':
        h += (b.inside && b.inside.length ? '<div class="grid2">' + card(id + '/in', '<h3>Also in this plan</h3>' + list(b.inside), 'Also in this plan') + card(id + '/out', '<h3>Not in this plan</h3>' + list(b.outside), 'Not in this plan') + '</div>' : card(id + '/out', '<h3>Not in this plan</h3>' + list(b.outside), 'Not in this plan'));
        break;
      case 'design':
        h += card(id, '<h3>' + esc(b.file || '') + '</h3><iframe class="design" title="' + esc(b.title || 'Design reference') + '" srcdoc="' + esc(b.srcdoc || '') + '"></iframe>', 'Design reference'); break;
      case 'reused':
        h += card(id, list(b.items), 'Reused'); break;
      default:
        h += '<div class="grid2' + (b.wide ? ' wide' : '') + '">' + (b.cards || []).map(function (c, j) { return card(id + '/' + j, (c.title ? '<h3>' + c.title + '</h3>' : '') + c.html, strip(c.title || '')); }).join('') + '</div>';
    }
    return h + '</section>';
  }

  /* ---------- calls ---------- */
  function renderCalls(text, key) {
    var lines = String(text || '').split('\n').filter(function (l) { return l.trim(); });
    var marked = lines.some(function (l) { return /^[+~*] /.test(l); });
    var h = '<div class="calls" data-key="' + esc(key) + '">';
    if (marked) h += '<div class="cl-head"><span class="k"><i style="background:var(--code-soft);color:var(--code)">+</i>new</span><span class="k"><i style="background:var(--warn-soft);color:var(--warn)">~</i>changed</span><span class="k"><i style="background:var(--ai-soft);color:var(--ai)">*</i>an agent</span><span>click the rail to strike a row</span></div>';
    else h += '<div class="cl-head"><span>one call per line · click the rail to strike a row</span></div>';
    h += '<div class="cl-rows' + (marked ? '' : ' norail') + '">';
    lines.forEach(function (line, i) {
      var mark = marked ? line.charAt(0) : ' ', rest = marked ? line.slice(2) : line;
      var depth = (rest.match(/^ */) || [''])[0].length / 2; rest = rest.trim();
      var loc = '', note = '', at = rest.indexOf(' @ '); if (at >= 0) { loc = rest.slice(at + 3); rest = rest.slice(0, at); }
      var dd = rest.indexOf(' -- '); if (dd >= 0) { note = rest.slice(dd + 4); rest = rest.slice(0, dd); }
      var cls = mark === '+' ? 'm-add' : mark === '~' ? 'm-mod' : mark === '*' ? 'm-ai' : 'm-ctx';
      var rk = key + '#' + i, struck = store.struck[rk] ? ' struck' : '';
      var guides = ''; for (var d = 0; d < depth; d++) guides += '│  ';
      h += '<div class="cl-row ' + cls + struck + '" data-row="' + esc(rk) + '" data-name="' + esc(rest) + '"><span class="cl-rail" title="Strike this row">' + (mark.trim() || '') + '</span><span class="cl-tg">' + guides + '</span><span class="cl-nm">' + esc(rest) + '</span>' + (note ? '<span class="cl-note">' + esc(note) + '</span>' : '') + (loc ? '<span class="cl-loc">' + esc(loc) + '</span>' : '') + '</div>';
    });
    return h + '</div></div>';
  }

  /* ---------- decisions ---------- */
  function renderDecisions(b, id) {
    var h = '';
    if (b.settled && b.settled.length) {
      h += '<h3 class="openhead">' + tag('settled') + 'Decisions taken, and what each follows from</h3><div class="tblwrap"><table class="deftable"><tr><th style="width:38%">Decision</th><th style="width:26%">Follows from</th><th>Considered</th><th class="ccol"></th></tr>' +
           b.settled.map(function (r, k) { return '<tr><td>' + r.decision + '</td><td>' + r.from + '</td><td>' + (r.considered || '—') + '</td><td class="ccol">' + commentBtn(id + '/settled/' + k, strip(r.decision).slice(0, 60)) + '</td></tr>'; }).join('') + '</table></div>';
    }
    if (b.open && b.open.length) {
      h += '<h3 class="openhead">Open decisions · ' + b.open.length + '</h3><p class="sub">Open an option to read how it works and what it costs. Press <b>Choose</b> to answer. The first option is the author\'s recommendation. When every decision has an answer, copy the response from the bar below; the author moves the answers into the settled table and offers the lock.</p>';
      b.open.forEach(function (d, n) {
        var pick = store.picks[d.id];
        h += '<div class="dec" id="d-' + esc(d.id) + '" data-dec="' + esc(d.id) + '">' + commentBtn('decision/' + d.id, 'Decision ' + (n + 1) + ' · ' + strip(d.title)) + '<h3>' + tag(pick != null ? 'answered' : 'open') + (n + 1) + ' · ' + d.title + '</h3><p class="ctx">' + d.context + '</p><div class="opts">';
        d.options.forEach(function (o, i) {
          var chosen = pick === i;
          h += '<button type="button" class="opt" data-i="' + i + '" aria-expanded="' + (i === 0 && pick == null) + '">' + (i === 0 ? tag('recommended') : '') + o.label + (chosen ? '<span class="pick">✓ your answer</span>' : '') + '</button>' +
               '<div class="optd' + ((i === 0 && pick == null) || chosen ? ' show' : '') + '"><dl><dt>How</dt><dd>' + o.how + '</dd><dt>Gains</dt><dd>' + o.gains + '</dd><dt>Costs</dt><dd>' + o.costs + '</dd><dt>Effort / risk</dt><dd>' + o.effort + '</dd><dt>Reversible?</dt><dd>' + o.reversible + '</dd></dl><button type="button" class="btn choose" data-i="' + i + '">' + (chosen ? 'Chosen' : 'Choose this option') + '</button></div>';
        });
        h += '</div></div>';
      });
    } else if (!b.settled || !b.settled.length) {
      h += '<p class="sub">No decisions.</p>';
    }
    return h;
  }

  /* ---------- map and nodes ---------- */
  var mapBlock = null, N = {}, parentOf = {}, current = null, decBlock = null, openDecs = [];
  function init() {
    try { var saved = localStorage.getItem('visual-plan:' + P.title); if (saved) store = JSON.parse(saved); } catch (e) {}
    mapBlock = P.blocks.filter(function (b) { return b.kind === 'map'; })[0];
    N = mapBlock ? mapBlock.nodes : {};
    if (mapBlock) Object.keys(N).forEach(function (id) {
      var n = N[id];
      Object.keys(n.children || {}).forEach(function (k) { parentOf[n.children[k]] = id; });
      if (n.view && n.view.type === 'diagram') {
        ((n.view.svg || '').match(/data-go="([^"]+)"/g) || []).forEach(function (m) { parentOf[m.slice(9, -1)] = id; });
        (n.view.boxes || []).forEach(function (b) { if (b.node) parentOf[b.node] = id; });
      }
    });
    decBlock = P.blocks.filter(function (b) { return b.kind === 'decisions'; })[0];
    openDecs = decBlock && decBlock.open ? decBlock.open : [];
  }

  function partsHtml(view) {
    var h = '<div class="flow">';
    view.parts.forEach(function (p, i) {
      if (i) h += '<span class="sep" aria-hidden="true">→</span>';
      h += '<button type="button" class="node ' + esc(p[0]) + '" data-n="' + esc(p[1]) + '" aria-pressed="false"><b>' + esc(p[1]) + '</b><small>' + esc(p[2] || '') + '</small></button>';
    });
    return h + '</div>';
  }
  function machineHtml(view) {
    var h = '<div class="machine">';
    (view.grid || [view.states.map(function (s) { return s[0]; })]).forEach(function (row) {
      h += '<div class="mgrid" style="grid-template-columns:repeat(' + row.length + ',minmax(0,1fr))">';
      row.forEach(function (sid) { var st = view.states.filter(function (s) { return s[0] === sid; })[0]; h += st ? '<button type="button" class="mstate" data-n="' + esc(sid) + '"><b>' + esc(sid) + '</b>' + esc(st[1]) + '</button>' : '<span></span>'; });
      h += '</div>';
    });
    h += '<ul class="marrows">' + (view.arrows || []).map(function (a) { return '<li data-from="' + esc(a[0]) + '">' + esc(a[0]) + ' → ' + esc(a[1]) + (a[2] ? ' : ' + esc(a[2]) : '') + '</li>'; }).join('') + '</ul></div>';
    return h;
  }
  function tableHtml(view) {
    return '<div class="tblwrap"><table class="deftable"><tr>' + view.columns.map(function (c) { return '<th>' + c + '</th>'; }).join('') + '</tr>' + view.rows.map(function (r) { return '<tr>' + r.map(function (c) { return '<td>' + c + '</td>'; }).join('') + '</tr>'; }).join('') + '</table></div>';
  }
  function boxSvg(b, node) {
    var cls = b.cls || (node && node.cls) || 'code', title = b.title || (node ? node.title : b.part) || '', sub = b.sub != null ? b.sub : (node && node.sub) || '';
    var subs = String(sub).split('\n').filter(Boolean), w = b.w || 150, h = b.h || (subs.length > 1 ? 96 : 72);
    var titleY = subs.length ? b.y + Math.max(24, (h - 15 * subs.length - 4) / 2 + 8) : b.y + h / 2 + 5;
    var attr = b.node ? ' data-go="' + esc(b.node) + '"' : ' data-n="' + esc(b.part) + '"';
    var g = '<g class="nd"' + attr + ' tabindex="0" role="button" aria-label="' + esc(b.node ? 'Open: ' + title : title) + '">';
    g += '<rect class="' + esc(cls) + '" x="' + b.x + '" y="' + b.y + '" width="' + w + '" height="' + h + '" rx="12"' + (b.dashed ? ' stroke-dasharray="6 4"' : '') + '/>';
    g += '<text x="' + (b.x + w / 2) + '" y="' + titleY + '" text-anchor="middle" class="t" font-weight="700" font-size="15">' + esc(title) + '</text>';
    subs.forEach(function (line, i) { g += '<text x="' + (b.x + w / 2) + '" y="' + (titleY + 19 + i * 15) + '" text-anchor="middle" class="m" font-size="12">' + esc(line) + '</text>'; });
    if (b.node) g += '<text x="' + (b.x + w - 8) + '" y="' + (b.y + 14) + '" text-anchor="end" class="zoom">+</text>';
    return g + '</g>';
  }
  var markerSeq = 0;
  function diagramSvg(view) {
    var mid = 'ah-' + (++markerSeq);
    if (!view.boxes) return String(view.svg).replace(/id="ah"/g, 'id="' + mid + '"').replace(/url\(#ah\)/g, 'url(#' + mid + ')');
    var inner = String(view.svg || '').replace(/url\(#ah\)/g, 'url(#' + mid + ')') + view.boxes.map(function (b) { return boxSvg(b, b.node ? N[b.node] : null); }).join('');
    return '<svg viewBox="' + esc(view.viewBox || '0 0 1000 400') + '" role="img" aria-label="' + esc(view.label || 'diagram') + '"><defs><marker id="' + mid + '" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 z" class="arrowhead"/></marker></defs>' + inner + '</svg>';
  }
  function viewHtml(view, key) {
    if (!view) return '';
    if (view.type === 'diagram') return '<div class="diag" data-scroll="scroll sideways →">' + diagramSvg(view) + '</div>';
    if (view.type === 'parts') return partsHtml(view);
    if (view.type === 'calls') return renderCalls(view.text, key);
    if (view.type === 'machine') return machineHtml(view);
    if (view.type === 'table') return tableHtml(view);
    return '';
  }
  function portHtml(label, p, dirWord) {
    return '<div class="port"><h4>' + label + '</h4><ul>' + p.items.map(function (i) { return '<li>' + i + '</li>'; }).join('') + '</ul><div class="meta"><b>' + dirWord + '</b> ' + (p.from || p.to) + '</div>' + (p.how ? '<div class="meta"><b>How</b> ' + p.how + '</div>' : '') + '</div>';
  }
  function siblings(id) { var p = parentOf[id]; return Object.keys(N).filter(function (k) { return parentOf[k] === p && k !== mapBlock.root; }); }

  function renderDetail(id) {
    current = id;
    var c = N[id], detail = document.getElementById('detail'), h = '';
    h += '<div class="dt-head"><div><div class="badges">' + (c.badges || []).map(function (b) { return '<span class="bdg ' + esc(b[0]) + '">' + (b[1] ? '<b>' + esc(b[1]) + '</b>' : '') + esc(b[2]) + '</span>'; }).join('') + '</div>';
    h += '<h2>' + esc(c.title) + '</h2></div><div class="dt-actions">' + commentBtn('node/' + id, strip(c.title)) + '<button class="btn" type="button" data-back>← Back</button></div></div>';
    if (c.one) h += '<p class="one">' + c.one + '</p>';
    var hasPorts = c['in'] || c.out;
    h += '<div class="io' + (hasPorts ? '' : ' noports') + '">' + (c['in'] ? portHtml('Input', c['in'], 'From') : '') +
         '<div class="inside"><div class="cap">Inside · click a part to read about it</div>' + viewHtml(c.view, 'node/' + id) + '<div class="note" id="note" hidden></div></div>' +
         (c.out ? portHtml('Output', c.out, 'To') : '') + '</div>';
    if (c.example) h += '<div class="cols"><div><div class="lbl">' + esc(c.exampleLabel || 'Example') + '</div><div class="box"><pre>' + esc(c.example) + '</pre></div></div></div>';
    var sib = siblings(id), i = sib.indexOf(id);
    if (sib.length > 1) { var prev = sib[(i - 1 + sib.length) % sib.length], next = sib[(i + 1) % sib.length]; h += '<div class="nav"><button type="button" class="btn" data-go="' + esc(prev) + '">← ' + esc(N[prev].title) + '</button><button type="button" class="btn" data-go="' + esc(next) + '">' + esc(N[next].title) + ' →</button></div>'; }
    detail.innerHTML = h;
    var note = detail.querySelector('#note');
    function show(name) {
      detail.querySelectorAll('[data-n]').forEach(function (b) { var on = b.getAttribute('data-n') === name; b.setAttribute('aria-pressed', on ? 'true' : 'false'); b.classList.toggle('on', on); });
      detail.querySelectorAll('.marrows li').forEach(function (li) { li.classList.toggle('on', li.getAttribute('data-from') === name); });
      var text = (c.notes || {})[name];
      if (text == null) { note.hidden = true; return; }
      var child = (c.children || {})[name];
      note.hidden = false;
      note.innerHTML = '<b>' + esc(name) + '.</b> ' + text + (child && N[child] ? '<div><button type="button" class="btn go" data-go="' + esc(child) + '">Open: ' + esc(N[child].title) + ' →</button></div>' : '');
      bindGo(note);
    }
    var first = detail.querySelector('[data-n]');
    if (first) show(first.getAttribute('data-n'));
    detail.querySelectorAll('[data-n]').forEach(function (b) { b.onclick = function () { show(b.getAttribute('data-n')); }; });
    detail.querySelector('[data-back]').onclick = function () { var p = parentOf[id]; if (p && p !== mapBlock.root) openDirect(p); else goHome(); };
    bindGo(detail); bindComments(detail); bindCalls(detail);
  }
  function bindGo(root) { root.querySelectorAll('[data-go]').forEach(function (b) { b.onclick = function (e) { e.stopPropagation(); openDirect(b.getAttribute('data-go')); }; }); }
  function crumbs(id) {
    var c = document.getElementById('crumbs'); if (!c) return;
    var chain = []; var cur = id; while (cur && cur !== mapBlock.root) { chain.unshift(cur); cur = parentOf[cur]; }
    var h = '<button type="button" data-home>' + esc(N[mapBlock.root].title || 'Overview') + '</button>';
    chain.forEach(function (k, i) { h += '<span>›</span>' + (i === chain.length - 1 ? '<span>' + esc(N[k].title) + '</span>' : '<button type="button" data-go="' + esc(k) + '">' + esc(N[k].title) + '</button>'); });
    c.innerHTML = h; c.querySelector('[data-home]').onclick = goHome; bindGo(c);
  }
  function openDirect(id) {
    if (!N[id]) return;
    var ov = document.getElementById('overview'), dt = document.getElementById('detail');
    ov.hidden = true; dt.hidden = false; renderDetail(id); dt.classList.remove('fade'); void dt.offsetWidth; dt.classList.add('fade');
    crumbs(id); if (location.hash !== '#' + id) history.replaceState(null, '', '#' + id);
    var c = document.getElementById('crumbs'); if (c) c.scrollIntoView({ block: 'start' });
  }
  function goHome() {
    var ov = document.getElementById('overview'), dt = document.getElementById('detail');
    dt.hidden = true; ov.hidden = false; current = null; crumbs(null); history.replaceState(null, '', location.pathname + location.search);
  }
  function renderMap() {
    if (!mapBlock) return;
    var root = N[mapBlock.root];
    var ov = document.querySelector('#overview .ov'); ov.innerHTML = root.view && root.view.type === 'diagram' ? diagramSvg(root.view) : '';
    ov.querySelectorAll('[data-go]').forEach(function (g) { g.setAttribute('tabindex', '0'); g.setAttribute('role', 'button'); g.onclick = function () { openDirect(g.getAttribute('data-go')); }; g.onkeydown = function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openDirect(g.getAttribute('data-go')); } }; });
    crumbs(null);
  }

  /* ---------- comments, strikes, picks ---------- */
  function bindComments(root) {
    root.querySelectorAll('.cbtn').forEach(function (b) {
      b.onclick = function () {
        var key = b.getAttribute('data-c'), host = b.closest('.dt-actions') ? b.closest('.detail') : b.parentElement, box = host.querySelector('.cbox');
        if (box) { box.remove(); return; }
        box = el('<div class="cbox"><label>Comment on ' + esc(b.getAttribute('data-label')) + '<textarea placeholder="What should change, or what is unclear">' + esc(store.comments[key] || '') + '</textarea></label></div>');
        if (b.closest('.dt-actions')) host.querySelector('.dt-head').insertAdjacentElement('afterend', box); else host.appendChild(box);
        var ta = box.querySelector('textarea'); ta.focus();
        ta.oninput = function () { store.comments[key] = ta.value.trim(); b.classList.toggle('has', !!store.comments[key]); b.textContent = store.comments[key] ? 'comment ✓' : 'comment'; save(); updateBar(); };
      };
    });
  }
  function bindCalls(root) {
    root.querySelectorAll('.cl-rail').forEach(function (r) {
      r.onclick = function () { var row = r.parentElement, k = row.getAttribute('data-row'); store.struck[k] = store.struck[k] ? '' : row.getAttribute('data-name'); row.classList.toggle('struck', !!store.struck[k]); save(); updateBar(); };
    });
  }
  function bindDecisions(root) {
    root.querySelectorAll('.dec').forEach(function (dec) {
      var id = dec.getAttribute('data-dec');
      dec.querySelectorAll('.opt').forEach(function (b) {
        b.onclick = function () {
          var open = b.getAttribute('aria-expanded') === 'true';
          dec.querySelectorAll('.opt').forEach(function (o) { o.setAttribute('aria-expanded', 'false'); o.nextElementSibling.classList.remove('show'); });
          if (!open) { b.setAttribute('aria-expanded', 'true'); b.nextElementSibling.classList.add('show'); }
        };
      });
      dec.querySelectorAll('.choose').forEach(function (c) {
        c.onclick = function () {
          var i = +c.getAttribute('data-i');
          store.picks[id] = i; save();
          dec.querySelectorAll('.opt').forEach(function (o, k) { var p = o.querySelector('.pick'); if (p) p.remove(); if (k === i) o.insertAdjacentHTML('beforeend', '<span class="pick">✓ your answer</span>'); });
          dec.querySelectorAll('.choose').forEach(function (x, k) { x.textContent = k === i ? 'Chosen' : 'Choose this option'; });
          var t = dec.querySelector('h3 .tag'); if (t) { t.className = 'tag answered'; t.textContent = 'answered'; }
          updateBar();
        };
      });
    });
  }

  /* ---------- respond ---------- */
  function countComments() { return Object.keys(store.comments).filter(function (k) { return store.comments[k]; }).length; }
  function updateBar() {
    var bar = document.getElementById('bar'); if (!bar) return;
    var left = openDecs.filter(function (d) { return store.picks[d.id] == null; }).length, c = countComments(), s = Object.keys(store.struck).filter(function (k) { return store.struck[k]; }).length;
    bar.querySelector('.state').textContent = (openDecs.length ? (left ? left + ' of ' + openDecs.length + ' decision' + (openDecs.length > 1 ? 's' : '') + ' to answer' : 'all decisions answered · copy your response') : (decBlock ? 'no open decision' : 'comments only')) + (c ? ' · ' + c + ' comment' + (c > 1 ? 's' : '') : '') + (s ? ' · ' + s + ' struck' : '');
  }
  function responseMarkdown(lock) {
    var out = ['# Re: ' + P.title, ''];
    if (openDecs.length) {
      out.push('## Decisions');
      openDecs.forEach(function (d, n) {
        var i = store.picks[d.id];
        if (i == null) { out.push((n + 1) + '. [' + d.id + '] ' + strip(d.title) + ' → _not answered_'); return; }
        var o = d.options[i];
        out.push((n + 1) + '. [' + d.id + '] ' + strip(d.title) + ' → **' + strip(o.label) + '**' + (i === 0 ? '  _(the recommendation)_' : '  _(recommended was ' + strip(d.options[0].label) + ')_'));
      });
      out.push('');
    }
    var struck = Object.keys(store.struck).filter(function (k) { return store.struck[k]; });
    if (struck.length) {
      out.push('## Struck');
      struck.forEach(function (k) { out.push('- ' + store.struck[k]); });
      out.push('');
    }
    var cs = Object.keys(store.comments).filter(function (k) { return store.comments[k]; });
    if (cs.length) {
      out.push('## Comments');
      cs.forEach(function (k) { var b = document.querySelector('[data-c="' + k.replace(/"/g, '\\"') + '"]'); out.push('- **' + (b ? b.getAttribute('data-label') : k) + '**'); store.comments[k].split('\n').forEach(function (l) { out.push('  > ' + l); }); });
      out.push('');
    }
    var left = openDecs.filter(function (d) { return store.picks[d.id] == null; }).length;
    if (!decBlock) return out.join('\n').replace(/\n+$/, '');
    out.push('## Lock'); out.push(lock ? 'locked' : (openDecs.length ? (left ? 'not yet: ' + left + ' decision(s) not answered' : 'ready: all decisions answered; move them to the settled table and offer the lock') : 'not locked'));
    return out.join('\n');
  }
  function openSheet(lock) {
    var sheet = document.getElementById('sheet'); sheet.classList.add('show');
    var ta = sheet.querySelector('textarea'); ta.value = responseMarkdown(lock); document.getElementById('copied').textContent = '';
  }

  /* ---------- page ---------- */
  function render() {
    // A host that wraps the page in its own document (the claude.ai Artifact tool) leaves the page's <style>,
    // <title> and <meta> in its <body>; move them to <head> before the body is replaced, or the page loses its CSS.
    document.body.querySelectorAll('style, title, meta').forEach(function (el) { document.head.appendChild(el); });
    P = window.PLAN;
    if (!P) { document.body.innerHTML = '<p style="padding:24px">No plan data: window.PLAN is missing.</p>'; return; }
    init();
    var h = '<div class="wrap"><h1>' + esc(P.title) + (P.status ? (openDecs.length ? '<a class="tag ' + esc(P.status.badge) + '" href="#decisions">' + esc(P.status.text) + '</a>' : tag(P.status.badge, P.status.text)) : '') + '</h1>';
    if (P.opening) h += '<p class="opening">' + P.opening + '</p>';
    if (P.examples && P.examples.length) h += '<div class="exstrip" role="note"><b>Examples on this page.</b> ' + (P.examplesNote || '') + P.examples.map(function (e) { return '<span class="exb"><b>' + esc(e.name) + '</b>' + e.text + '</span>'; }).join('') + '</div>';
    h += '<nav class="toc" aria-label="Sections">' + P.blocks.map(function (b, i) { var id = b.id || b.kind + (b.kind === 'section' ? i : ''); var label = b.title && b.kind === 'section' ? b.title : (TOC_TITLES[b.kind] || b.title || b.kind); if (b.kind === 'decisions' && openDecs.length) label += ' · ' + openDecs.length + ' open'; return '<a href="#' + esc(id) + '">' + esc(label) + '</a>'; }).join('') + '</nav>';
    h += P.blocks.map(renderBlock).join('');
    h += '</div>';
    h += '<div class="bar" id="bar"><span class="state"></span><button type="button" class="btn" id="respond">Respond</button>' + (openDecs.length || !decBlock ? '' : '<button type="button" class="btn pri" id="lock">Lock this design</button>') + '</div>';
    h += '<div class="sheet" id="sheet"><div class="pane"><h2>Your response</h2><p class="sub">Copy this text and paste it in the chat. Your answers and struck rows are decisions; your comments are feedback.</p><textarea readonly aria-label="Your response, as text to paste in the chat"></textarea><div class="row"><button type="button" class="btn pri" id="copy">Copy response</button><button type="button" class="btn" id="close">Close</button><span class="sub" id="copied"></span></div></div></div>';
    document.body.innerHTML = h;
    renderMap();
    bindComments(document); bindCalls(document); bindDecisions(document); bindGo(document);
    document.getElementById('respond').onclick = function () { openSheet(false); };
    var lockBtn = document.getElementById('lock'); if (lockBtn) lockBtn.onclick = function () { openSheet(true); };
    document.getElementById('close').onclick = function () { document.getElementById('sheet').classList.remove('show'); };
    document.getElementById('copy').onclick = function () {
      var ta = document.querySelector('#sheet textarea'); ta.select();
      var done = function () { document.getElementById('copied').textContent = 'copied'; };
      if (navigator.clipboard) navigator.clipboard.writeText(ta.value).then(done, function () { document.execCommand('copy'); done(); }); else { document.execCommand('copy'); done(); }
    };
    updateBar();
    var start = (location.hash || '').slice(1);
    if (N[start] && start !== (mapBlock && mapBlock.root)) openDirect(start);
    window.addEventListener('hashchange', function () { var id = (location.hash || '').slice(1); if (N[id] && id !== mapBlock.root) openDirect(id); else if (!id && current) goHome(); });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', render); else render();
})();
