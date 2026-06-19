/*
 * dc-runtime.js — a minimal, self-contained renderer for the design-component
 * template dialect used by the Route Planner handoff (claude.ai/design "support.js"
 * equivalent). It interprets the exact subset of the dialect this project uses:
 *
 *   {{ expr }}                 interpolation in text nodes and attribute values
 *   <sc-if value="{{ x }}">    conditional block (renders children when truthy)
 *   <sc-for list="{{ a }}"     list block (repeats children per item)
 *            as="item">
 *   onClick / onInput /        event bindings -> addEventListener(handler)
 *   onKeyDown
 *   value="{{ x }}"            controlled input value
 *   style-hover="..."          inline hover styles
 *
 * Expressions are simple dotted paths (e.g. `nav.dashboard.go`, `s.color`) or the
 * literals true/false/null/number. All computed values come from the component's
 * renderVals(); the template never does arithmetic.
 *
 * Rendering is a full re-render of the active screen on every setState(). Because
 * only one screen's <sc-if> is truthy at a time, each render builds just that
 * screen. Text-input focus and caret are preserved across re-renders.
 */
(function (global) {
  'use strict';

  var SVG_NS = 'http://www.w3.org/2000/svg';

  // ---- expression evaluation -------------------------------------------------

  // Resolve a single {{ ... }} expression to its raw value (function, array,
  // boolean, ...). Used where the binding must keep its native type.
  function evalExpr(expr, scope) {
    var e = String(expr).trim();
    if (e === 'true') return true;
    if (e === 'false') return false;
    if (e === 'null') return null;
    if (/^-?\d+(\.\d+)?$/.test(e)) return Number(e);
    var parts = e.split('.');
    var cur = scope;
    for (var i = 0; i < parts.length; i++) {
      if (cur == null) return undefined;
      cur = cur[parts[i].trim()];
    }
    return cur;
  }

  // If an attribute value is exactly one binding ("{{ x }}"), return the inner
  // expression so callers can read its raw (non-stringified) value.
  function singleExpr(value) {
    var m = String(value).trim().match(/^\{\{([^}]*)\}\}$/);
    return m ? m[1].trim() : null;
  }

  // Stringifying interpolation for mixed text / attribute content.
  function interp(str, scope) {
    if (str == null) return '';
    return String(str).replace(/\{\{([^}]*)\}\}/g, function (_, ex) {
      var v = evalExpr(ex, scope);
      return v == null ? '' : String(v);
    });
  }

  // ---- DOM rendering ---------------------------------------------------------

  function isEventAttr(name) {
    // Attribute names are lower-cased by the HTML parser, so onClick -> onclick.
    return /^on[a-z]+$/.test(name);
  }

  function applyAttr(el, name, rawValue, scope, hoverBox) {
    if (name.indexOf('hint-') === 0 || name === 'data-screen-label') return;

    if (isEventAttr(name)) {
      var ex = singleExpr(rawValue);
      var fn = ex ? evalExpr(ex, scope) : null;
      if (typeof fn === 'function') {
        el.addEventListener(name.slice(2), fn);
      }
      return;
    }

    if (name === 'style-hover') {
      hoverBox.css = interp(rawValue, scope);
      return;
    }

    if (name === 'value') {
      var vex = singleExpr(rawValue);
      var v = vex ? evalExpr(vex, scope) : interp(rawValue, scope);
      el.value = v == null ? '' : v;
      return;
    }

    el.setAttribute(name, interp(rawValue, scope));
  }

  function wireHover(el, hoverCss) {
    if (!hoverCss) return;
    var base = el.getAttribute('style') || '';
    el.addEventListener('mouseenter', function () {
      el.setAttribute('style', base + ';' + hoverCss);
    });
    el.addEventListener('mouseleave', function () {
      el.setAttribute('style', base);
    });
  }

  // Render one source node against a scope, returning an array of live nodes.
  function renderNode(node, scope, out) {
    if (node.nodeType === 3) { // text
      out.push(document.createTextNode(interp(node.nodeValue, scope)));
      return;
    }
    if (node.nodeType !== 1) { // comment / other
      out.push(node.cloneNode(true));
      return;
    }

    var tag = node.localName.toLowerCase();

    if (tag === 'sc-for') {
      var listExpr = singleExpr(node.getAttribute('list') || '');
      var as = node.getAttribute('as') || 'item';
      var list = listExpr ? evalExpr(listExpr, scope) : [];
      if (!list) return;
      for (var i = 0; i < list.length; i++) {
        var childScope = Object.create(scope);
        childScope[as] = list[i];
        childScope[as + '_index'] = i;
        var kids = node.childNodes;
        for (var j = 0; j < kids.length; j++) renderNode(kids[j], childScope, out);
      }
      return;
    }

    if (tag === 'sc-if') {
      var condExpr = singleExpr(node.getAttribute('value') || '');
      var cond = condExpr ? evalExpr(condExpr, scope) : false;
      if (!cond) return;
      var ck = node.childNodes;
      for (var k = 0; k < ck.length; k++) renderNode(ck[k], scope, out);
      return;
    }

    // Normal element: recreate in the source node's namespace so SVG subtrees
    // (path, circle, g, ...) stay in the SVG namespace and actually render.
    var ns = node.namespaceURI || 'http://www.w3.org/1999/xhtml';
    var el = document.createElementNS(ns, node.localName);
    var hoverBox = { css: '' };
    var attrs = node.attributes;
    for (var a = 0; a < attrs.length; a++) {
      applyAttr(el, attrs[a].name, attrs[a].value, scope, hoverBox);
    }
    wireHover(el, hoverBox.css);

    var children = node.childNodes;
    var childOut = [];
    for (var c = 0; c < children.length; c++) renderNode(children[c], scope, childOut);
    for (var n = 0; n < childOut.length; n++) el.appendChild(childOut[n]);

    out.push(el);
  }

  // ---- focus preservation ----------------------------------------------------

  function focusKey(el) {
    return el.tagName + '|' + (el.getAttribute('type') || '') + '|' + (el.getAttribute('placeholder') || '');
  }

  function captureFocus(root) {
    var a = document.activeElement;
    if (!a || !root.contains(a)) return null;
    if (a.tagName !== 'INPUT' && a.tagName !== 'TEXTAREA') return null;
    return { key: focusKey(a), start: a.selectionStart, end: a.selectionEnd };
  }

  function restoreFocus(root, f) {
    if (!f) return;
    var nodes = root.querySelectorAll('input, textarea');
    for (var i = 0; i < nodes.length; i++) {
      if (focusKey(nodes[i]) === f.key) {
        nodes[i].focus();
        if (f.start != null && typeof nodes[i].setSelectionRange === 'function') {
          try { nodes[i].setSelectionRange(f.start, f.end); } catch (e) { /* type without text selection */ }
        }
        return;
      }
    }
  }

  // ---- DCLogic base class ----------------------------------------------------

  function DCLogic(props) {
    this.props = props || {};
    this._template = null;
    this._mountEl = null;
  }

  DCLogic.prototype.mount = function (templateEl, mountEl) {
    this._template = templateEl;
    this._mountEl = mountEl;
    this._render();
  };

  DCLogic.prototype.setState = function (updater, cb) {
    var patch = typeof updater === 'function' ? updater(this.state) : updater;
    var next = {};
    var k;
    for (k in this.state) next[k] = this.state[k];
    for (k in patch) next[k] = patch[k];
    this.state = next;
    this._render();
    if (typeof cb === 'function') cb();
  };

  DCLogic.prototype._render = function () {
    if (!this._mountEl || !this._template) return;
    var vals;
    try {
      vals = this.renderVals();
    } catch (err) {
      console.error('renderVals failed', err);
      return;
    }
    var focus = captureFocus(this._mountEl);
    var out = [];
    var src = this._template.content.childNodes;
    for (var i = 0; i < src.length; i++) renderNode(src[i], vals, out);
    var frag = document.createDocumentFragment();
    for (var j = 0; j < out.length; j++) frag.appendChild(out[j]);
    this._mountEl.replaceChildren(frag);
    restoreFocus(this._mountEl, focus);
  };

  global.DCLogic = DCLogic;
})(window);
