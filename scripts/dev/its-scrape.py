#!/usr/bin/env python3
"""
ITS (its.1c.ru) scraper via Chrome DevTools Protocol (CDP).

Reads rendered content from the currently open ITS page (after manual login)
and exports it to JSON for further parsing/indexing.

Requirements:
  pip install websockets

Run Chromium in WSL with CDP enabled:
  chromium --remote-debugging-port=9222 --no-first-run "https://its.1c.ru/..." &

Notes:
  - CDP supports only a single WebSocket connection per page. Close any other
    CDP clients (e.g. scripts/dev/chrome-debug.py) before running this script.
  - Authentication must be done manually in the open browser profile.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass
from collections import deque
from pathlib import Path
from typing import Any, Optional
from urllib.request import urlopen


CDP_URL = "http://127.0.0.1:9222"


def _get_pages() -> list[dict[str, Any]]:
    try:
        with urlopen(f"{CDP_URL}/json", timeout=2) as resp:
            return json.loads(resp.read())
    except Exception as e:
        raise RuntimeError(
            f"Cannot connect to Chrome at {CDP_URL}. "
            f"Start Chromium with: chromium --remote-debugging-port=9222 --no-first-run <url> &"
        ) from e


def _find_page(url_pattern: str) -> dict[str, Any]:
    pages = _get_pages()
    for page in pages:
        if page.get("type") == "page" and url_pattern in (page.get("url") or ""):
            return page
    raise RuntimeError(f"No page found matching url pattern: {url_pattern!r}")


@dataclass
class CDPClient:
    ws_url: str
    _next_id: int = 1

    async def command(self, ws, method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        msg_id = self._next_id
        self._next_id += 1
        payload: dict[str, Any] = {"id": msg_id, "method": method}
        if params:
            payload["params"] = params
        await ws.send(json.dumps(payload))
        while True:
            raw = await ws.recv()
            data = json.loads(raw)
            if data.get("id") != msg_id:
                continue
            if "error" in data:
                raise RuntimeError(f"CDP command error ({method}): {data['error']}")
            return data.get("result") or {}

    async def eval(self, ws, expression: str, *, return_by_value: bool = True) -> Any:
        msg_id = self._next_id
        self._next_id += 1
        await ws.send(
            json.dumps(
                {
                    "id": msg_id,
                    "method": "Runtime.evaluate",
                    "params": {"expression": expression, "returnByValue": return_by_value},
                }
            )
        )
        while True:
            raw = await ws.recv()
            data = json.loads(raw)
            if data.get("id") != msg_id:
                continue
            if "error" in data:
                raise RuntimeError(f"CDP evaluate error: {data['error']}")
            result = (data.get("result") or {}).get("result") or {}
            if return_by_value and "value" in result:
                return result["value"]
            return result


def _sha1_12(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def _split_sections(text: str) -> list[dict[str, Any]]:
    """
    Best-effort section splitter for ITS docs.

    Splits by headings like:
      "7.1. ...", "7.10. ...", "1. ...", "Приложение 7. ..."
    """
    lines = [ln.rstrip() for ln in text.splitlines()]
    heading_re = re.compile(r"^(?:Приложение\s+\d+\.|(?:\d+\.){1,6}\s).+")

    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal current, buf
        if current is None:
            return
        current["text"] = "\n".join(buf).strip()
        sections.append(current)
        current = None
        buf = []

    for ln in lines:
        if not ln.strip():
            if buf and buf[-1] != "":
                buf.append("")
            continue
        if heading_re.match(ln) and len(ln) < 160:
            flush()
            current = {"title": ln.strip(), "text": ""}
            continue
        if current is None:
            current = {"title": "preamble", "text": ""}
        buf.append(ln)

    flush()
    return sections


def _extract_ti_id(value: str) -> str | None:
    m = re.search(r"(TI\d{6,})", value)
    return m.group(1) if m else None


def _slugify(value: str, max_len: int = 120) -> str:
    value = unicodedata.normalize("NFKC", value).strip()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^\w\u0400-\u04FF\s.-]+", "_", value, flags=re.UNICODE)
    value = value.replace(" ", "_")
    value = re.sub(r"_+", "_", value).strip("._-")
    return value[:max_len] or "its_doc"


def _format_version_for_filename(version: str) -> str:
    v = version.strip()
    return v if re.fullmatch(r"\d+\.\d+\.\d+", v) else "unknown"


_ZERO_WIDTH = (
    "\u200b"  # ZERO WIDTH SPACE
    "\u200c"  # ZERO WIDTH NON-JOINER
    "\u200d"  # ZERO WIDTH JOINER
    "\ufeff"  # ZERO WIDTH NO-BREAK SPACE / BOM
)


def _sanitize_text(value: str) -> str:
    """
    Reduce Unicode confusables/ambiguity in exported text for editors (VS Code).

    - NFKC normalization
    - NBSP-like spaces -> normal space
    - remove zero-width chars
    """
    s = unicodedata.normalize("NFKC", value)
    s = (
        s.replace("\u00a0", " ")  # NO-BREAK SPACE
        .replace("\u202f", " ")  # NARROW NO-BREAK SPACE
        .replace("\u2007", " ")  # FIGURE SPACE
    )
    for ch in _ZERO_WIDTH:
        s = s.replace(ch, "")
    return s


def _breadcrumbs_to_path(breadcrumbs: list[dict[str, Any]] | list[str]) -> list[str]:
    out: list[str] = []
    if not breadcrumbs:
        return out
    if isinstance(breadcrumbs[0], str):
        return [str(x).strip() for x in breadcrumbs if str(x).strip()]
    for b in breadcrumbs:
        if isinstance(b, dict):
            t = str(b.get("text") or "").strip()
            if t:
                out.append(t)
    return out


def _build_toc_hierarchy(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stack: list[dict[str, Any]] = []
    out: list[dict[str, Any]] = []

    for item in items:
        level = int(item.get("level") or 0)
        while stack and int(stack[-1].get("level") or 0) >= level:
            stack.pop()
        parent_id = stack[-1].get("id") if stack else None
        enriched = {**item, "parent_id": parent_id}
        out.append(enriched)
        stack.append(enriched)

    return out


async def _wait_for_change(
    *,
    cdp: CDPClient,
    ws,
    expr: str,
    prev_value: Any,
    timeout_s: float = 8.0,
    poll_s: float = 0.2,
) -> Any:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        cur = await cdp.eval(ws, expr)
        if cur != prev_value and cur is not None:
            return cur
        await asyncio.sleep(poll_s)
    return await cdp.eval(ws, expr)


async def _click_link(
    *,
    cdp: CDPClient,
    ws,
    href: str,
    text: str,
    timeout_s: float = 8.0,
) -> bool:
    href_js = json.dumps(href)
    text_js = json.dumps(text)
    clicked = await cdp.eval(
        ws,
        rf"""
(() => {{
  const href = {href_js};
  const text = {text_js};
  const links = Array.from(document.querySelectorAll('a'));
  let a = links.find(x => (x.getAttribute('href') || '') === href) || null;
  if (!a && href) {{
    a = links.find(x => (x.getAttribute('href') || '').includes(href)) || null;
  }}
  if (!a && text) {{
    a = links.find(x => (x.innerText || '').trim().replace(/\\s+/g,' ') === text) || null;
  }}
  if (!a) return false;
  a.click();
  return true;
}})()
""",
    )
    if not clicked:
        return False

    prev_state = await cdp.eval(
        ws,
        "JSON.stringify({outer: String(location.href||''), frame: String(document.querySelector('#w_metadata_doc_frame')?.contentWindow?.location?.href||'')})",
    )
    await _wait_for_change(
        cdp=cdp,
        ws=ws,
        expr="JSON.stringify({outer: String(location.href||''), frame: String(document.querySelector('#w_metadata_doc_frame')?.contentWindow?.location?.href||'')})",
        prev_value=prev_state,
        timeout_s=timeout_s,
    )
    return True


async def _scrape_current_in_session(
    *,
    cdp: CDPClient,
    ws,
    page_url: str,
    include_raw_text: bool,
    sanitize_text: bool,
) -> dict[str, Any]:
    outer = await cdp.eval(
        ws,
        r"""
(() => {
  function extractBreadcrumbs() {
    const homeLink = Array.from(document.querySelectorAll('a')).find(a => (a.innerText || '').trim() === 'Главная');
    if (homeLink) {
      const container = homeLink.closest('nav, ol, ul, .breadcrumb, .breadcrumbs, .path') || homeLink.parentElement;
      if (container) {
        const items = Array.from(container.querySelectorAll('li'));
        if (items.length >= 2) {
          const out = [];
          for (const li of items) {
            const a = li.querySelector('a');
            if (a) out.push({ text: (a.innerText || '').trim(), href: a.getAttribute('href') || '' });
            else out.push({ text: (li.innerText || '').trim(), href: '' });
          }
          if (out.filter(x => x.text).length >= 2) return out.filter(x => x.text);
        }
        const links = Array.from(container.querySelectorAll('a'))
          .map(a => ({ text: (a.innerText || '').trim(), href: a.getAttribute('href') || '' }))
          .filter(x => x.text);
        if (links.length >= 2) return links;
      }
    }

    const selectors = [
      '.breadcrumb a',
      'nav[aria-label*="breadcrumb"] a',
      '.breadcrumbs a',
      '.bread-crumbs a',
      '.path a',
    ];
    for (const sel of selectors) {
      const nodes = Array.from(document.querySelectorAll(sel));
      if (nodes.length >= 2) {
        return nodes.map(a => ({ text: (a.innerText || '').trim(), href: a.getAttribute('href') || '' })).filter(x => x.text);
      }
    }

    const hay = (document.body && document.body.innerText) ? document.body.innerText : '';
    const line = hay.split('\n').map(l => l.trim()).find(l => l.startsWith('Главная') && (l.includes('>') || l.includes('›') || l.includes('→'))) || '';
    if (line) {
      const parts = line
        .split(/(?:\s+>\s+|\s+›\s+|\s+→\s+)/g)
        .map(s => s.trim())
        .filter(Boolean);
      return parts.map(p => ({ text: p, href: '' }));
    }

    return [];
  }

  function extractVersion() {
    const direct = Array.from(document.querySelectorAll('button, a, span, div'))
      .map(el => (el.innerText || '').trim())
      .find(t => /^\d+\.\d+\.\d+$/.test(t));
    return direct || '';
  }

  function findTocContainer() {
    const frame = document.querySelector('#w_metadata_doc_frame');
    const candidates = [];
    if (frame) {
      const near = frame.closest('main, .main, .content, .l, body') || document.body;
      candidates.push(...Array.from((near || document).querySelectorAll('aside, nav, .sidebar, .sidebar-fixed, .sidebar-spacer, .left, .l')));
    } else {
      candidates.push(...Array.from(document.querySelectorAll('aside, nav, .sidebar, .sidebar-fixed, .sidebar-spacer, .left, .l')));
    }

    let best = null;
    let bestScore = 0;
    for (const el of candidates) {
      const links = el.querySelectorAll('a[href]');
      if (!links || links.length < 5) continue;
      const t = el.innerText || '';
      const score = links.length
        + (t.match(/\nПриложение\s+\d+\./g) || []).length * 10
        + (t.match(/\n\d+\.\d+\./g) || []).length * 10
        + (t.match(/TI\d{6,}/g) || []).length * 3;
      if (score > bestScore) { bestScore = score; best = el; }
    }
    return best;
  }

  function extractToc() {
    const container = findTocContainer();
    if (!container) return { items: [], selectedText: '' };

    const items = [];
    const seen = new Set();
    const links = Array.from(container.querySelectorAll('a'));
    for (const a of links) {
      const text = (a.innerText || '').trim().replace(/\s+/g,' ');
      const href = (a.getAttribute('href') || '').trim();
      if (!text) continue;
      if (!href || href === '#' || href === 'javascript:void(0)' || href === 'javascript:;') continue;

      let level = 1;
      let p = a.parentElement;
      while (p && p !== container) {
        if (p.tagName === 'UL' || p.tagName === 'OL') level += 1;
        p = p.parentElement;
      }
      const ml = parseInt((getComputedStyle(a).marginLeft || '0').replace('px',''), 10);
      if (!isNaN(ml) && ml >= 12) level += Math.min(5, Math.floor(ml / 24));

      const active = a.classList.contains('active') || a.getAttribute('aria-current') === 'page' || a.closest('.active') != null;
      const key = href + '|' + text;
      if (seen.has(key)) continue;
      seen.add(key);
      items.push({ text, href, level: Math.max(1, level), active });
    }

    const selectedNode = items.find(i => i.active) || null;
    const selectedText = selectedNode ? selectedNode.text : '';
    return { items, selectedText };
  }

  const toc = extractToc();
  const f = document.querySelector('#w_metadata_doc_frame');
  if (!f || !f.contentDocument) return { error: 'no_frame' };
  const d = f.contentDocument;
  const url = (f.contentWindow && f.contentWindow.location) ? String(f.contentWindow.location.href) : '';
  const title = String(d.title || document.title || '');
  const h1 = String((d.querySelector('h1') && d.querySelector('h1').innerText) ? d.querySelector('h1').innerText.trim() : '');
  const len = (d.body && d.body.innerText) ? d.body.innerText.length : 0;
  return {
    title,
    h1,
    url,
    len,
    outer_url: String(location.href || ''),
    outer_title: String(document.title || ''),
    version: extractVersion(),
    breadcrumbs: extractBreadcrumbs(),
    toc: toc.items,
    toc_selected: toc.selectedText,
  };
})()
""",
    )

    if isinstance(outer, dict) and outer.get("error"):
        raise RuntimeError(f"Cannot access ITS frame content: {outer.get('error')}")

    frame_title = str(outer.get("title") or "")
    frame_h1 = str(outer.get("h1") or "")
    frame_url = str(outer.get("url") or "")
    total_len = int(outer.get("len") or 0)
    if total_len <= 0:
        raise RuntimeError("Frame text length is zero; are you logged in and content loaded?")

    async def read_frame_text_slice(start: int, end: int) -> str:
        return str(
            await cdp.eval(
                ws,
                rf"""
(() => {{
  const f = document.querySelector('#w_metadata_doc_frame');
  const d = f && f.contentDocument;
  const t = (d && d.body && d.body.innerText) ? d.body.innerText : '';
  return t.slice({start}, {end});
}})()
""",
            )
        )

    chunk_size = 20_000
    chunks: list[str] = []
    for start in range(0, total_len, chunk_size):
        end = min(total_len, start + chunk_size)
        chunks.append(await read_frame_text_slice(start, end))
    full_text = "".join(chunks)
    if sanitize_text:
        full_text = _sanitize_text(full_text)

    frame_anchor_ids = await cdp.eval(
        ws,
        r"""
(() => {
  const f = document.querySelector('#w_metadata_doc_frame');
  const d = f && f.contentDocument;
  if (!d) return [];
  const els = Array.from(d.querySelectorAll('[id]'));
  const ids = els.map(e => String(e.id)).filter(id => /^TI\d{6,}$/.test(id));
  const seen = new Set();
  const out = [];
  for (const id of ids) { if (!seen.has(id)) { seen.add(id); out.push(id); } }
  return out;
})()
""",
    )

    toc_raw = outer.get("toc") if isinstance(outer, dict) else []
    toc_items: list[dict[str, Any]] = []
    if isinstance(toc_raw, list):
        for it in toc_raw:
            if not isinstance(it, dict):
                continue
            text = str(it.get("text") or "").strip()
            href = str(it.get("href") or "").strip()
            level = int(it.get("level") or 1)
            active = bool(it.get("active") or False)
            toc_items.append({"text": text, "href": href, "level": level, "active": active})

    outer_url = str(outer.get("outer_url") or "") if isinstance(outer, dict) else ""
    outer_pointer_ti = _extract_ti_id(outer_url)
    current_ti = _extract_ti_id(frame_url) or None

    anchor_ids = [str(x) for x in frame_anchor_ids] if isinstance(frame_anchor_ids, list) else []
    anchor_set = set(anchor_ids)

    enriched_toc: list[dict[str, Any]] = []
    for it in toc_items:
        ti = _extract_ti_id(it.get("href") or "") or _extract_ti_id(it.get("text") or "")
        enriched_toc.append({**it, "id": ti})
    enriched_toc = _build_toc_hierarchy(enriched_toc)

    async def read_section_by_anchor(start_id: str, next_id: str | None) -> str:
        next_part = f"'{next_id}'" if next_id else "null"
        return str(
            await cdp.eval(
                ws,
                rf"""
(() => {{
  const f = document.querySelector('#w_metadata_doc_frame');
  const d = f && f.contentDocument;
  if (!d) return '';
  const start = d.getElementById('{start_id}');
  if (!start) return '';
  const end = {next_part} ? d.getElementById({next_part}) : null;
  const range = d.createRange();
  range.setStartBefore(start);
  if (end) range.setEndBefore(end);
  else range.setEndAfter(d.body.lastChild || d.body);
  const txt = range.cloneContents().textContent || '';
  return txt;
}})()
""",
            )
        ).strip()

    sections: list[dict[str, Any]] = []
    toc_with_anchors = [t for t in enriched_toc if t.get("id") and t.get("id") in anchor_set]
    if toc_with_anchors:
        for idx, t in enumerate(toc_with_anchors):
            sid = str(t["id"])
            next_id = str(toc_with_anchors[idx + 1]["id"]) if idx + 1 < len(toc_with_anchors) else None
            section_text = await read_section_by_anchor(sid, next_id)
            if sanitize_text:
                section_text = _sanitize_text(section_text)
            sections.append(
                {
                    "id": sid,
                    "title": t.get("text") or "",
                    "level": t.get("level") or 1,
                    "parent_id": t.get("parent_id"),
                    "text": section_text,
                }
            )
    else:
        for s in _split_sections(full_text):
            sections.append(
                {
                    "id": None,
                    "title": s.get("title") or "",
                    "level": None,
                    "parent_id": None,
                    "text": s.get("text") or "",
                }
            )

    breadcrumbs_raw = outer.get("breadcrumbs") if isinstance(outer, dict) else []
    breadcrumb_path = _breadcrumbs_to_path(breadcrumbs_raw) if isinstance(breadcrumbs_raw, list) else []
    display_name = breadcrumb_path[-1] if breadcrumb_path else (frame_h1 or frame_title.split("::", 1)[0].strip())
    if sanitize_text:
        display_name = _sanitize_text(display_name).strip()
        breadcrumb_path = [_sanitize_text(x).strip() for x in breadcrumb_path]
    version = str(outer.get("version") or "") if isinstance(outer, dict) else ""

    doc_url = frame_url.split("#", 1)[0] if frame_url else ""
    doc_id = doc_url or page_url or ""
    pointer_ti = outer_pointer_ti or current_ti

    payload: dict[str, Any] = {
        "source": "its.1c.ru",
        "doc_id": doc_id,
        "doc_id_sha1_12": _sha1_12(doc_id) if doc_id else "",
        "pointer_ti": pointer_ti,
        "outer_pointer_ti": outer_pointer_ti,
        "current_ti": current_ti,
        "display_name": display_name,
        "breadcrumb_path": breadcrumb_path,
        "breadcrumb_str": " > ".join(breadcrumb_path) if breadcrumb_path else "",
        "frame_title": frame_title,
        "frame_h1": frame_h1,
        "outer_title": str(outer.get("outer_title") or "") if isinstance(outer, dict) else "",
        "version": version,
        "breadcrumbs": breadcrumbs_raw,
        "toc_selected": str(outer.get("toc_selected") or "") if isinstance(outer, dict) else "",
        "toc": enriched_toc,
        "page_url": page_url,
        "frame_url": frame_url,
        "doc_url": doc_url,
        "text_len": len(full_text),
        "sections_count": len(sections),
        "sections": sections,
        "frame_anchor_ids": anchor_ids,
    }
    if include_raw_text:
        payload["raw_text"] = full_text

    return payload


def _filename_from_payload(payload: dict[str, Any], *, name_style: str) -> str:
    if name_style == "full" and payload.get("breadcrumb_str"):
        name = str(payload.get("breadcrumb_str") or "")
    else:
        name = str(payload.get("display_name") or "")
    if not name:
        name = str(payload.get("frame_h1") or payload.get("frame_title") or "its_doc")

    version = str(payload.get("version") or "")
    pointer = str(payload.get("pointer_ti") or payload.get("current_ti") or payload.get("doc_id_sha1_12") or "no_pointer")
    return f"{_slugify(name)}__v{_format_version_for_filename(version)}__{pointer}.json"


async def scrape(
    url_pattern: str,
    out_path: Path,
    *,
    include_raw_text: bool,
    name_style: str,
    sanitize_text: bool,
) -> tuple[dict[str, Any], Path]:
    import websockets

    page = _find_page(url_pattern)
    ws_url = page["webSocketDebuggerUrl"]
    cdp = CDPClient(ws_url)

    async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
        await cdp.command(ws, "Runtime.enable")
        await cdp.command(ws, "Page.enable")
        payload = await _scrape_current_in_session(
            cdp=cdp,
            ws=ws,
            page_url=str(page.get("url") or ""),
            include_raw_text=include_raw_text,
            sanitize_text=sanitize_text,
        )

    if not out_path.name or out_path.name == "last.json":
        out_path = Path("generated/its") / _filename_from_payload(payload, name_style=name_style)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload, out_path


async def crawl_toc(
    url_pattern: str,
    out_dir: Path,
    *,
    max_items: int = 0,
    delay_s: float = 0.3,
    include_raw_text: bool,
    name_style: str,
    only_unique_docs: bool,
    sanitize_text: bool,
) -> Path:
    """
    Iterate outer TOC items and scrape each visited state.
    Saves an index.json with the list of visited items + per-item output paths.
    """
    import websockets

    page = _find_page(url_pattern)
    ws_url = page["webSocketDebuggerUrl"]
    cdp = CDPClient(ws_url)

    out_dir.mkdir(parents=True, exist_ok=True)

    async with websockets.connect(ws_url, max_size=64 * 1024 * 1024) as ws:
        await cdp.command(ws, "Runtime.enable")
        await cdp.command(ws, "Page.enable")

        async def extract_toc_links() -> list[dict[str, str]]:
            toc = await cdp.eval(
                ws,
                r"""
(() => {
  function findTocContainer() {
    const frame = document.querySelector('#w_metadata_doc_frame');
    const candidates = [];
    if (frame) {
      const near = frame.closest('main, .main, .content, .l, body') || document.body;
      candidates.push(...Array.from((near || document).querySelectorAll('aside, nav, .sidebar, .sidebar-fixed, .sidebar-spacer, .left, .l')));
    } else {
      candidates.push(...Array.from(document.querySelectorAll('aside, nav, .sidebar, .sidebar-fixed, .sidebar-spacer, .left, .l')));
    }

    let best = null;
    let bestScore = 0;
    for (const el of candidates) {
      const links = el.querySelectorAll('a[href]');
      if (!links || links.length < 5) continue;
      const t = el.innerText || '';
      const score = links.length
        + (t.match(/\nПриложение\s+\d+\./g) || []).length * 10
        + (t.match(/\n\d+\.\d+\./g) || []).length * 10
        + (t.match(/TI\d{6,}/g) || []).length * 3;
      if (score > bestScore) { bestScore = score; best = el; }
    }
    return best;
  }

  const container = findTocContainer();
  if (!container) return [];

  const out = [];
  const seen = new Set();
  const links = Array.from(container.querySelectorAll('a'));
  for (const a of links) {
    const text = (a.innerText || '').trim().replace(/\s+/g, ' ');
    const href = (a.getAttribute('href') || '').trim();
    if (!text) continue;
    if (!href || href === '#' || href === 'javascript:void(0)' || href === 'javascript:;') continue;
    const key = href + '|' + text;
    if (seen.has(key)) continue;
    seen.add(key);
    out.push({ text, href });
  }
  return out;
})()
""",
            )

            toc_items: list[dict[str, str]] = []
            if isinstance(toc, list):
                for it in toc:
                    if isinstance(it, dict) and it.get("text"):
                        toc_items.append({"text": str(it.get("text") or ""), "href": str(it.get("href") or "")})
            return toc_items

        index: list[dict[str, Any]] = []
        seen_states: set[str] = set()
        seen_doc_ids: set[str] = set()
        seen_links: set[str] = set()

        initial = await extract_toc_links()
        q: deque[dict[str, str]] = deque()
        for it in initial:
            key = f"{it.get('href','')}|{it.get('text','')}"
            if not it.get("href") or not it.get("text") or key in seen_links:
                continue
            seen_links.add(key)
            q.append(it)

        scraped = 0
        while q:
            it = q.popleft()
            await asyncio.sleep(delay_s)

            before_state = await cdp.eval(
                ws,
                "JSON.stringify({outer: String(location.href||''), frame: String(document.querySelector('#w_metadata_doc_frame')?.contentWindow?.location?.href||'')})",
            )
            await _click_link(cdp=cdp, ws=ws, href=it["href"], text=it["text"])
            after_state = await cdp.eval(
                ws,
                "JSON.stringify({outer: String(location.href||''), frame: String(document.querySelector('#w_metadata_doc_frame')?.contentWindow?.location?.href||'')})",
            )

            state_key = str(after_state or before_state)
            if not state_key or state_key in seen_states:
                index.append(
                    {
                        "toc_text": it["text"],
                        "toc_href": it["href"],
                        "skipped": True,
                        "reason": "duplicate_state_or_empty",
                        "state": state_key,
                    }
                )
                # Even if state didn't change, TOC might expand; refresh and enqueue new links.
                for nxt in await extract_toc_links():
                    key = f"{nxt.get('href','')}|{nxt.get('text','')}"
                    if not nxt.get("href") or not nxt.get("text") or key in seen_links:
                        continue
                    seen_links.add(key)
                    q.append(nxt)
                continue
            seen_states.add(state_key)

            payload = await _scrape_current_in_session(
                cdp=cdp,
                ws=ws,
                page_url=str(page.get("url") or ""),
                include_raw_text=include_raw_text,
                sanitize_text=sanitize_text,
            )

            if only_unique_docs and payload.get("doc_id"):
                doc_id = str(payload["doc_id"])
                if doc_id in seen_doc_ids:
                    index.append(
                        {
                            "toc_text": it["text"],
                            "toc_href": it["href"],
                            "skipped": True,
                            "reason": "duplicate_doc_id",
                            "doc_id": doc_id,
                            "frame_url": payload.get("frame_url"),
                        }
                    )
                    continue
                seen_doc_ids.add(doc_id)

            out_path = out_dir / _filename_from_payload(payload, name_style=name_style)
            out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            index.append(
                {
                    "toc_text": it["text"],
                    "toc_href": it["href"],
                    "state": state_key,
                    "frame_url": payload.get("frame_url"),
                    "page_url": payload.get("page_url"),
                    "doc_id": payload.get("doc_id"),
                    "doc_id_sha1_12": payload.get("doc_id_sha1_12"),
                    "doc_url": payload.get("doc_url"),
                    "pointer_ti": payload.get("pointer_ti"),
                    "version": payload.get("version"),
                    "display_name": payload.get("display_name"),
                    "breadcrumb_str": payload.get("breadcrumb_str"),
                    "path": str(out_path),
                }
            )

            scraped += 1
            if max_items > 0 and scraped >= max_items:
                break

            # Refresh TOC after navigation: some nodes expand and reveal new sections.
            for nxt in await extract_toc_links():
                key = f"{nxt.get('href','')}|{nxt.get('text','')}"
                if not nxt.get("href") or not nxt.get("text") or key in seen_links:
                    continue
                seen_links.add(key)
                q.append(nxt)

    index_path = out_dir / "index.json"
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    return index_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--url-pattern",
        default="its.1c.ru/db/v8327doc",
        help="Substring to find the open ITS page in CDP /json list",
    )
    parser.add_argument(
        "--out",
        default="",
        help="Output JSON path. If omitted, auto-generates from title + version + TI",
    )
    parser.add_argument(
        "--name-style",
        choices=["short", "full"],
        default="short",
        help="Filename base: last breadcrumb (short) or full breadcrumb path (full)",
    )
    parser.add_argument(
        "--no-raw-text",
        action="store_true",
        help="Do not include full raw_text in JSON (smaller output, recommended for crawl)",
    )
    parser.add_argument(
        "--sanitize-text",
        action="store_true",
        help="Normalize text (NFKC), replace NBSP with space, remove zero-width chars (cleaner JSON for editors)",
    )
    parser.add_argument(
        "--crawl-toc",
        action="store_true",
        help="Iterate TOC items and scrape each visited page into --out-dir",
    )
    parser.add_argument(
        "--out-dir",
        default="generated/its/crawl",
        help="Output directory for --crawl-toc mode",
    )
    parser.add_argument(
        "--max-items",
        type=int,
        default=0,
        help="Limit TOC items processed in --crawl-toc mode (0 = all)",
    )
    parser.add_argument(
        "--only-unique-docs",
        action="store_true",
        help="In crawl mode, skip items that resolve to an already scraped doc_id",
    )
    args = parser.parse_args()

    include_raw_text = not bool(args.no_raw_text)
    sanitize_text = bool(args.sanitize_text)

    if args.crawl_toc:
        try:
            index_path = asyncio.run(
                crawl_toc(
                    args.url_pattern,
                    Path(args.out_dir),
                    max_items=int(args.max_items or 0),
                    include_raw_text=include_raw_text,
                    name_style=str(args.name_style),
                    only_unique_docs=bool(args.only_unique_docs),
                    sanitize_text=sanitize_text,
                )
            )
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 1
        print(f"Saved: {index_path}")
        return 0

    out_path = Path(args.out) if args.out else Path("generated/its/last.json")
    try:
        payload, saved_path = asyncio.run(
            scrape(
                args.url_pattern,
                out_path,
                include_raw_text=include_raw_text,
                name_style=str(args.name_style),
                sanitize_text=sanitize_text,
            )
        )
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"Saved: {saved_path}")
    print(f"display_name: {payload.get('display_name')}")
    if payload.get("breadcrumb_str"):
        print(f"breadcrumb: {payload.get('breadcrumb_str')}")
    print(f"sections: {payload.get('sections_count')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
