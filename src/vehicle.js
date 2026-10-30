/* Optional mode switch, modification connectors and detail-panel positioning.
 * No innerHTML or remote data. div-based controls support BWiki's HTML allowlist.
 * Never writes to the Wiki. */
(function () {
  'use strict';
  var MODES = ['ab', 'rb'];

  function initModifications(root) {
    var tree = root.querySelector('.wtv-mod-tree');
    if (!tree) return;
    var nodes = Array.prototype.slice.call(tree.querySelectorAll('.wtv-mod-node'));
    var canvas = document.createElement('canvas');
    canvas.className = 'wtv-mod-lines';
    canvas.setAttribute('aria-hidden', 'true');
    tree.insertBefore(canvas, tree.firstChild);
    function draw() {
      var box = tree.getBoundingClientRect();
      if (!box.width || !box.height) return;
      var ratio = window.devicePixelRatio || 1;
      canvas.width = Math.ceil(tree.offsetWidth * ratio);
      canvas.height = Math.ceil(tree.offsetHeight * ratio);
      canvas.style.width = tree.offsetWidth + 'px';
      canvas.style.height = tree.offsetHeight + 'px';
      var ctx = canvas.getContext('2d');
      ctx.scale(ratio, ratio);
      ctx.strokeStyle = '#7e919b';
      ctx.fillStyle = '#7e919b';
      ctx.lineWidth = 2.5;
      nodes.forEach(function (node) {
        var required = (node.dataset.requires || '').split(',').filter(Boolean);
        var ids = required;
        ids.forEach(function (id) {
          var parent = nodes.find(function (n) { return n.dataset.mod === id; });
          if (!parent) return;
          var a = parent.querySelector('.wtv-mod-card').getBoundingClientRect();
          var b = node.querySelector('.wtv-mod-card').getBoundingClientRect();
          if (Math.abs(a.top - b.top) < 1) {
            // Same-tier prerequisites connect at the facing card edges.
            var direction = b.left > a.left ? 1 : -1;
            var start = (direction > 0 ? a.right : a.left) - box.left;
            var end = (direction > 0 ? b.left : b.right) - box.left;
            var y = b.top + b.height / 2 - box.top;
            ctx.beginPath(); ctx.moveTo(start, y);
            ctx.lineTo(end - direction * 6, y); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(end - direction * 7, y - 4);
            ctx.lineTo(end, y); ctx.lineTo(end - direction * 7, y + 4); ctx.fill();
            return;
          }
          var x1 = a.left + a.width / 2 - box.left;
          var y1 = a.bottom - box.top;
          var x2 = b.left + b.width / 2 - box.left;
          var y2 = b.top - box.top;
          var mid = y1 + (y2 - y1) / 2;
          ctx.setLineDash([]);
          ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x1, mid);
          ctx.lineTo(x2, mid); ctx.lineTo(x2, y2 - 5); ctx.stroke();
          ctx.setLineDash([]);
          ctx.beginPath(); ctx.moveTo(x2 - 4, y2 - 7); ctx.lineTo(x2, y2);
          ctx.lineTo(x2 + 4, y2 - 7); ctx.fill();
        });
      });
    }
    function collapsible(node, trigger, defaultOpen) {
      var opened = !!defaultOpen;
      Object.defineProperty(node, 'open', {get:function(){return opened;},set:function(value){
        value=!!value; if(value===opened)return; opened=value;
        node.dataset.open=value?'1':'0'; trigger.setAttribute('aria-expanded',value?'true':'false');
        node.dispatchEvent(new Event('toggle'));
      }});
      node.dataset.open=opened?'1':'0';
      trigger.addEventListener('click',function(){node.open=!node.open;});
      trigger.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();node.open=!node.open;}});
    }
    nodes.forEach(function (node) {
      collapsible(node,node.querySelector('.wtv-mod-card'),false);
      var panel = node.querySelector('.wtv-mod-info');
      panel.classList.add('wtv-mod-portal');
      node.addEventListener('toggle', function () {
        if (!node.open) { node.appendChild(panel); return; }
        nodes.forEach(function (other) { if (other !== node) other.open = false; });
        document.body.appendChild(panel);
        var rect = node.querySelector('.wtv-mod-card').getBoundingClientRect();
        panel.style.left = Math.max(8, Math.min(rect.left, window.innerWidth - 288)) + 'px';
        var height = panel.getBoundingClientRect().height;
        panel.style.top = Math.max(8, Math.min(rect.bottom + 6, window.innerHeight - height - 8)) + 'px';
      });
    });
    function close() { nodes.forEach(function (node) { node.open = false; }); }
    document.addEventListener('click', function (e) { if (!e.target.closest('.wtv-mod-node, .wtv-mod-portal')) close(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') close(); });
    tree.parentElement.addEventListener('scroll', close);
    window.addEventListener('scroll', close);
    window.addEventListener('resize', function () { close(); draw(); });
    if (window.ResizeObserver) new ResizeObserver(draw).observe(tree);
    requestAnimationFrame(draw);
  }

  function init(scope) {
    if (!scope || typeof scope.querySelectorAll !== 'function') return;
    var roots = scope.querySelectorAll('.wtv');
    for (var i = 0; i < roots.length; i++) initRoot(roots[i]);
  }

  function initLoadouts(root) {
    var editor = root.querySelector('.wtv-loadout-editor');
    if (!editor) return;
    var slots = Array.prototype.slice.call(editor.querySelectorAll('.wtv-slot-choice'));
    var result = editor.querySelector('.wtv-loadout-result');
    result.setAttribute('aria-live','polite');
    root.querySelectorAll('.wtv-loadout-toggle').forEach(function(toggle) {
      function change() { var on=toggle.parentElement.dataset.open!=='1';toggle.parentElement.dataset.open=on?'1':'0';toggle.setAttribute('aria-expanded',on?'true':'false'); }
      toggle.setAttribute('aria-expanded','false');toggle.addEventListener('click',change);
      toggle.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();change();}});
    });
    function refresh() {
      var selected = {}, total = 0, left = 0, right = 0, unknown = false, errors = [], counts = {};
      slots.forEach(function (slot) {
        var choice = slot.querySelector('[data-selected="1"]');
        selected[slot.dataset.slot] = choice;
        var mass = choice.dataset.mass === '' ? NaN : Number(choice.dataset.mass);
        if (!Number.isFinite(mass)) { unknown = true; return; }
        total += mass;
        if (slot.dataset.side === 'left') left += mass;
        if (slot.dataset.side === 'right') right += mass;
        (choice.dataset.items || '').split(',').filter(Boolean).forEach(function (part) {
          var pair = part.split(':'); counts[pair[0]] = (counts[pair[0]] || 0) + Number(pair[1]);
        });
      });
      slots.forEach(function (slot) {
        var choice = selected[slot.dataset.slot];
        ['dependencies','blocking'].forEach(function (kind) {
          (choice.dataset[kind] || '').split(',').filter(Boolean).forEach(function (part) {
            var pair = part.split(':'), other = selected[pair[0]];
            var present = other && other.dataset.option === pair[1];
            if (kind === 'dependencies' ? !present : present) errors.push('挂点 ' + slot.querySelector('strong').textContent.replace('挂点 ', '') + (kind === 'dependencies' ? ' 缺少依赖：' : ' 与装备互斥：') + pair[1]);
          });
        });
      });
      [[total,editor.dataset.maxTotal,'总重量'],[left,editor.dataset.maxLeft,'左翼重量'],[right,editor.dataset.maxRight,'右翼重量'],[Math.abs(left-right),editor.dataset.maxImbalance,'左右失衡']].forEach(function (check) {
        if (check[1] !== '' && Number.isFinite(Number(check[1])) && Number(check[1])>=0 && check[0] > Number(check[1]) + 0.001) errors.push(check[2] + '超过上限');
      });
      result.replaceChildren();
      var summary = document.createElement('p');
      summary.textContent = '总挂载 ' + total.toFixed(1) + ' kg · 左翼 ' + left.toFixed(1) + ' kg · 右翼 ' + right.toFixed(1) + ' kg · 失衡 ' + Math.abs(left-right).toFixed(1) + ' kg';
      result.appendChild(summary);
      var status = document.createElement('strong');
      status.textContent = errors.length ? '未通过：' + errors.join('；') : unknown ? '存在未知重量，无法完成检查' : '已解析的静态规则检查通过';
      result.appendChild(status);
      result.dataset.validity = errors.length ? 'invalid' : unknown ? 'unknown' : 'passed';
      var names = {};
      root.querySelectorAll('.game-unit_slot-list [data-store]').forEach(function (row) { names[row.dataset.store] = row.querySelector('th').textContent.replace(/^\d+ × /, ''); });
      Object.keys(counts).forEach(function (key) { var p = document.createElement('div'); p.textContent = (names[key] || key) + ' × ' + counts[key]; result.appendChild(p); });
    }
    slots.forEach(function (slot) {
      var trigger=slot.querySelector('.wtv-slot-trigger');
      var options=slot.querySelector('.wtv-slot-options');
      if(trigger && options) {
        trigger.setAttribute('aria-haspopup','listbox');
        trigger.setAttribute('aria-expanded','false');
        function expand(){root.wtvOpenPanel(options,trigger,true);}
        trigger.addEventListener('click',expand);
        trigger.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '||e.key==='ArrowDown'){e.preventDefault();expand();}});
      }
      slot.querySelectorAll('.wtv-store-choice').forEach(function (choice) {
        choice.setAttribute('role','option');
        function choose() {
          root.wtvClosePanel();
          slot.querySelectorAll('.wtv-store-choice').forEach(function (other) { other.dataset.selected=other===choice?'1':'0';other.setAttribute('aria-selected', other === choice ? 'true' : 'false'); });
          if(trigger){
            trigger.replaceChildren();
            var selectedLabel=choice.cloneNode(true);
            Array.prototype.slice.call(selectedLabel.attributes).forEach(function(a){selectedLabel.removeAttribute(a.name);});selectedLabel.className='wtv-slot-selected';
            trigger.appendChild(selectedLabel);
            var arrow=document.createElement('span');arrow.className='wtv-dropdown-arrow';arrow.textContent='▾';trigger.appendChild(arrow);
            trigger.focus({preventScroll:true});
          }
          refresh();
        }
        choice.addEventListener('click', choose);
        choice.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(); } });
      });
    });
    refresh();
  }

  function initPopovers(root) {
    var active=null;
    function close(focus) {
      if(!active)return;
      var old=active;active=null;
      if(old.placeholder){old.placeholder.replaceWith(old.panel);old.panel.classList.remove('wtv-ui-portal','wtv-dropdown-portal');old.panel.removeAttribute('style');}
      else old.panel.remove();
      old.anchor.setAttribute('aria-expanded','false');
      if(focus)old.anchor.focus({preventScroll:true});
    }
    root.wtvClosePanel=close;
    root.wtvOpenPanel=function(source,anchor,dropdown) {
      if(active && active.anchor===anchor){close();return;}
      close();
      var panel,placeholder;
      if(dropdown){panel=source;placeholder=document.createComment('loadout-options');source.replaceWith(placeholder);}
      else {panel=source.cloneNode(true);panel.classList.remove('wtv-popup-source');panel.removeAttribute('data-popup-id');}
      panel.classList.add('wtv-ui-portal');
      if(dropdown){panel.classList.add('wtv-dropdown-portal');panel.setAttribute('role','listbox');}
      else {panel.setAttribute('role','dialog');panel.setAttribute('aria-label',anchor.textContent.trim());var dismiss=document.createElement('div');dismiss.className='wtv-popup-close';dismiss.setAttribute('role','button');dismiss.tabIndex=0;dismiss.textContent='×';dismiss.setAttribute('aria-label','关闭');dismiss.addEventListener('click',function(){close(true);});dismiss.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();close(true);}});panel.prepend(dismiss);}
      document.body.appendChild(panel);
      var box=anchor.getBoundingClientRect();
      panel.style.maxHeight=Math.max(120,Math.min(dropdown?420:680,window.innerHeight-24))+'px';
      panel.style.left=Math.max(8,Math.min(box.left,window.innerWidth-panel.offsetWidth-8))+'px';
      panel.style.top=Math.max(8,Math.min(box.bottom+5,window.innerHeight-panel.offsetHeight-8))+'px';
      active={panel:panel,anchor:anchor,placeholder:placeholder};anchor.setAttribute('aria-expanded','true');
      if(dropdown){var selected=panel.querySelector('[data-selected="1"]');if(selected)selected.focus({preventScroll:true});}
    };
    root.querySelectorAll('.wtv-popover-trigger').forEach(function(anchor){
      anchor.setAttribute('aria-haspopup','dialog');anchor.setAttribute('aria-expanded','false');
      function open(){var source=Array.prototype.find.call(root.querySelectorAll('[data-popup-id]'),function(n){return n.dataset.popupId===anchor.dataset.popup;});if(source)root.wtvOpenPanel(source,anchor,false);}
      anchor.addEventListener('click',open);
      anchor.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}});
    });
    document.addEventListener('click',function(e){if(active&&!active.panel.contains(e.target)&&!active.anchor.contains(e.target))close();});
    document.addEventListener('keydown',function(e){if(!active)return;if(e.key==='Escape'){e.preventDefault();close(true);}else if(active.placeholder && (e.key==='ArrowDown'||e.key==='ArrowUp')){e.preventDefault();var items=Array.prototype.slice.call(active.panel.querySelectorAll('[role="option"]'));var index=items.indexOf(document.activeElement);items[(index+(e.key==='ArrowDown'?1:-1)+items.length)%items.length].focus();}});
    document.addEventListener('scroll',function(e){if(active&&!active.panel.contains(e.target))close();},true);
    window.addEventListener('resize',function(){close();});
  }

  function initRoot(root) {
    if (!root || !root.dataset || root.dataset.wtvReady === '1') return;
    var buttons = Array.prototype.slice.call(root.querySelectorAll('[data-wtv-mode]'));
    root.dataset.wtvReady = '1';
    var sidebar = root.querySelector('.wtv-side');
    if (sidebar) {
      function positionSidebar() {
        if (window.innerWidth <= 820) { sidebar.style.top = ''; return; }
        var edge = sidebar.getBoundingClientRect(), top = 12;
        document.querySelectorAll('.wiki-nav,.wiki-header,#biliGameHeader,#mw-head').forEach(function(header) {
          var rect = header.getBoundingClientRect(), style = getComputedStyle(header);
          if ((style.position === 'fixed' || style.position === 'sticky') && style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 0 && rect.height > 0 && rect.top <= Math.max(0, parseFloat(style.top) || 0) + 1 && rect.bottom > 0 && rect.left < edge.right && rect.right > edge.left) top = Math.max(top, rect.bottom + 12);
        });
        sidebar.style.top = Math.ceil(top) + 'px';
        sidebar.style.maxHeight = Math.max(160, window.innerHeight - top - 12) + 'px';
      }
      window.addEventListener('scroll', positionSidebar, {passive:true});
      window.addEventListener('resize', positionSidebar);
      positionSidebar();
    }
    initModifications(root);
    initPopovers(root);
    initLoadouts(root);
    if (!buttons.length) return;

    function current() {
      var m = root.getAttribute('data-mode');
      return MODES.indexOf(m) >= 0 ? m : 'rb';
    }
    function sync() {
      var m = current();
      for (var i = 0; i < buttons.length; i++) {
        var on = buttons[i].getAttribute('data-wtv-mode') === m;
        buttons[i].setAttribute('aria-pressed', on ? 'true' : 'false');
      }
    }
    function apply(mode) {
      if (MODES.indexOf(mode) < 0) return;
      root.dataset.mode = mode; /* attribute only; descendants are never replaced */
      sync();
    }
    function onKey(e) {
      var key = e.key;
      if (key !== 'ArrowRight' && key !== 'ArrowLeft' && key !== 'Home' && key !== 'End' && key !== 'Enter' && key !== ' ' && key !== 'Spacebar') return;
      e.preventDefault();
      var idx = buttons.indexOf(document.activeElement);
      if (idx < 0) return;
      if (key === 'Enter' || key === ' ' || key === 'Spacebar') {
        apply(buttons[idx].getAttribute('data-wtv-mode'));
        return;
      }
      var next;
      if (key === 'ArrowRight') next = (idx + 1) % buttons.length;
      else if (key === 'ArrowLeft') next = (idx + buttons.length - 1) % buttons.length;
      else if (key === 'Home') next = 0;
      else next = buttons.length - 1;
      buttons[next].focus();
      apply(buttons[next].getAttribute('data-wtv-mode'));
    }

    for (var i = 0; i < buttons.length; i++) {
      (function (btn) {
        btn.addEventListener('click', function () { apply(btn.getAttribute('data-wtv-mode')); });
        btn.addEventListener('keydown', onKey);
      })(buttons[i]);
    }
    sync();
  }

  if (window.mw && typeof mw.hook === 'function') {
    mw.hook('wikipage.content').add(function (content) {
      init((content && content[0]) || document);
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { init(document); });
  } else {
    init(document);
  }
})();
