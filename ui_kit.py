"""Visual building blocks for the Streamlit screens (presentation only, no business rules).

The look follows the Milestone 6 wireframes: white top bar with the ZippyWash mark, indigo primary
actions, a five-step progress bar, white cards on a light grey page, and coloured status banners.
"""
from __future__ import annotations

from html import escape

import streamlit as st

INDIGO = "#4F46E5"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stButton button, input, select, textarea, label {
  font-family: 'Inter', system-ui, -apple-system, sans-serif !important; }
.block-container { max-width: 1080px; padding-top: 1.2rem; }
header[data-testid="stHeader"] { background: transparent; }
h1, h2, h3 { letter-spacing: -0.02em; }

/* cards: every bordered container */
[class*="st-key-card_"] { background: #fff; border-radius: 14px !important;
  border: 1px solid #E5E7EB !important; box-shadow: 0 1px 3px rgba(16,24,40,.06); padding: 18px 20px !important; }

/* inputs: light fill with a thin border, as in the wireframes */
div[data-baseweb="input"], div[data-baseweb="select"] > div, div[data-baseweb="textarea"] {
  border: 1px solid #E5E7EB !important; border-radius: 10px !important; }
section[data-testid="stSidebar"] { background: #fff; border-right: 1px solid #E5E7EB; }

/* top bar */
.zw-top { display:flex; align-items:center; gap:10px; }
.zw-logo { width:34px; height:34px; border-radius:9px; background:#4F46E5; display:flex;
  align-items:center; justify-content:center; }
.zw-brand { font-weight:700; font-size:1.15rem; color:#111827; }
.zw-user { display:flex; align-items:center; justify-content:flex-end; gap:8px; font-size:.9rem; color:#374151; }
.zw-avatar { width:32px; height:32px; border-radius:999px; background:#EEF2FF; color:#4338CA;
  font-weight:600; font-size:.8rem; display:flex; align-items:center; justify-content:center; }

/* navigation radio styled as tabs */
[class*="st-key-navbar"] div[role="radiogroup"] { gap: 4px; justify-content:flex-end; flex-wrap:wrap; }
[class*="st-key-navbar"] div[role="radiogroup"] label > div > div:not([data-testid="stMarkdownContainer"]) { display:none; }
[class*="st-key-navbar"] div[role="radiogroup"] label { padding: 6px 12px; border-bottom: 2px solid transparent;
  color:#4B5563; font-weight:500; }
[class*="st-key-navbar"] div[role="radiogroup"] label[data-selected="true"] { border-bottom-color:#4F46E5; color:#111827; }

/* page header */
.zw-title { font-size: 1.9rem; font-weight: 700; color:#111827; margin: .2rem 0 0; }
.zw-sub { color:#6B7280; margin: 2px 0 14px; font-size:.95rem; }
.zw-h { font-weight:600; font-size:1.05rem; color:#111827; margin:0 0 2px; }
.zw-muted { color:#6B7280; font-size:.85rem; }
.zw-small { color:#6B7280; font-size:.78rem; text-transform:uppercase; letter-spacing:.04em; }

/* stepper */
.zw-stepper { display:flex; align-items:flex-start; margin: 10px 0 22px; }
.zw-st { flex:1; display:flex; flex-direction:column; align-items:center; position:relative; }
.zw-st:not(:first-child)::before { content:""; position:absolute; top:13px; right:50%; width:100%;
  height:2px; background:#E5E7EB; z-index:0; }
.zw-st.done:not(:first-child)::before, .zw-st.now:not(:first-child)::before { background:#4F46E5; }
.zw-dot { width:28px; height:28px; border-radius:999px; border:2px solid #D1D5DB; background:#fff;
  display:flex; align-items:center; justify-content:center; font-size:.75rem; color:#6B7280; z-index:1; }
.zw-st.done .zw-dot { background:#4F46E5; border-color:#4F46E5; color:#fff; }
.zw-st.now .zw-dot { background:#4F46E5; border-color:#C7D2FE; color:#fff; box-shadow:0 0 0 4px #E0E7FF; }
.zw-st span { font-size:.75rem; color:#6B7280; margin-top:6px; }
.zw-st.now span { color:#111827; font-weight:600; }

/* banners and pills */
.zw-banner { display:flex; align-items:center; gap:14px; border-radius:14px; padding:14px 18px; margin:0 0 16px;
  border:1px solid; }
.zw-banner .ic { width:38px; height:38px; border-radius:999px; display:flex; align-items:center;
  justify-content:center; color:#fff; font-weight:700; flex:none; }
.zw-banner b { display:block; color:#111827; }
.zw-banner small { color:#4B5563; }
.zw-banner .pill { margin-left:auto; }
.zw-banner.success { background:#ECFDF3; border-color:#A6F4C5; } .zw-banner.success .ic { background:#16A34A; }
.zw-banner.danger { background:#FEF2F2; border-color:#FECACA; } .zw-banner.danger .ic { background:#DC2626; }
.zw-banner.purple { background:#F5F3FF; border-color:#DDD6FE; } .zw-banner.purple .ic { background:#7C3AED; }
.zw-banner.info { background:#EEF2FF; border-color:#C7D2FE; } .zw-banner.info .ic { background:#4F46E5; }
.zw-banner.amber { background:#FFFBEB; border-color:#FDE68A; } .zw-banner.amber .ic { background:#D97706; }
.pill { display:inline-block; padding:3px 10px; border-radius:999px; font-size:.72rem; font-weight:600;
  letter-spacing:.03em; text-transform:uppercase; white-space:nowrap; }
.pill.success { background:#DCFCE7; color:#15803D; } .pill.danger { background:#FEE2E2; color:#B91C1C; }
.pill.purple { background:#EDE9FE; color:#6D28D9; } .pill.amber { background:#FEF3C7; color:#B45309; }
.pill.info { background:#E0E7FF; color:#4338CA; } .pill.grey { background:#F3F4F6; color:#4B5563; }

/* key-value rows and price table */
.zw-kv { display:flex; justify-content:space-between; padding:6px 0; font-size:.92rem; color:#374151; }
.zw-kv b { color:#111827; font-weight:600; }
.zw-kv.total { border-top:1px solid #E5E7EB; margin-top:6px; padding-top:12px; font-weight:600; color:#111827; }
.zw-kv.total b { font-size:1.35rem; }
.zw-note { background:#F9FAFB; border:1px solid #F3F4F6; border-radius:10px; padding:10px 12px;
  font-size:.85rem; color:#4B5563; margin-top:8px; }
.zw-section { font-size:.8rem; font-weight:600; color:#374151; margin:10px 0 2px; }

/* order progress (read-only) */
.zw-prog { display:flex; align-items:flex-start; margin: 8px 0 4px; }
.zw-prog .zw-st span { font-size:.68rem; text-align:center; }
.zw-prog .zw-dot { width:20px; height:20px; font-size:.6rem; }
.zw-prog .zw-st:not(:first-child)::before { top:9px; }

/* buttons */
.stButton button[kind="primary"], .stFormSubmitButton button[kind="primary"] { background:#4F46E5;
  border-color:#4F46E5; border-radius:10px; font-weight:600; padding:.5rem 1.1rem; }
.stButton button[kind="primary"]:hover { background:#4338CA; border-color:#4338CA; }
.stButton button[kind="secondary"], .stFormSubmitButton button[kind="secondary"] { border-radius:10px; }
.zw-step-count { text-align:center; color:#9CA3AF; font-size:.8rem; padding-top:.55rem; }

/* radio options shown as selectable cards (payment methods, rewards, times) */
[class*="st-key-cards"] div[role="radiogroup"] { gap:8px; }
[class*="st-key-cards"] div[role="radiogroup"] label { border:1px solid #E5E7EB; border-radius:12px; padding:10px 14px;
  background:#fff; width:100%; }
[class*="st-key-cards"] div[role="radiogroup"] label[data-selected="true"] { border-color:#4F46E5; background:#EEF2FF; }
[class*="st-key-chips"] div[role="radiogroup"] label { border:1px solid #E5E7EB; border-radius:10px; padding:6px 12px;
  background:#fff; }
[class*="st-key-chips"] div[role="radiogroup"] label[data-selected="true"] { border-color:#4F46E5; background:#EEF2FF; }
</style>
"""

LOGO = ('<svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M13 2L4 14h7l-1 8 9-12h-7l1-8z" '
        'fill="#fff"/></svg>')
CHECK = "&#10003;"


def e(text) -> str:
    """Escape anything that came from data before putting it in HTML."""
    return escape(str(text))


def apply_style() -> None:
    _card_count[0] = 0          # card keys restart on every page run, so they stay stable
    st.markdown(CSS, unsafe_allow_html=True)


def html(markup: str) -> None:
    st.markdown(markup, unsafe_allow_html=True)


def brand() -> None:
    html(f'<div class="zw-top"><div class="zw-logo">{LOGO}</div><div class="zw-brand">ZippyWash</div></div>')


def user_badge(name: str) -> None:
    initials = "".join(p[0] for p in name.split()[:2]).upper()
    html(f'<div class="zw-user"><div class="zw-avatar">{e(initials)}</div>{e(name.split()[0])}</div>')


def page_title(title: str, subtitle: str = "") -> None:
    html(f'<div class="zw-title">{e(title)}</div><div class="zw-sub">{e(subtitle)}</div>')


def stepper(current: int, labels=("Details", "Time Slots", "Review", "Payment", "Confirmation"),
            all_done: bool = False, css: str = "zw-stepper") -> None:
    parts = []
    for i, label in enumerate(labels, start=1):
        state = "done" if (i < current or all_done) else "now" if i == current else ""
        mark = CHECK if state == "done" else str(i)
        parts.append(f'<div class="zw-st {state}"><div class="zw-dot">{mark}</div><span>{e(label)}</span></div>')
    html(f'<div class="{css}">{"".join(parts)}</div>')


def banner(kind: str, icon: str, title: str, text: str = "", pill: str | None = None) -> None:
    p = f'<span class="pill {kind}">{e(pill)}</span>' if pill else ""
    html(f'<div class="zw-banner {kind}"><div class="ic">{icon}</div><div><b>{e(title)}</b>'
         f'<small>{e(text)}</small></div>{p}</div>')


def pill(text: str, kind: str = "grey") -> str:
    return f'<span class="pill {kind}">{e(text)}</span>'


def heading(title: str, sub: str = "", right: str = "") -> None:
    r = f'<span style="float:right">{right}</span>' if right else ""
    html(f'{r}<div class="zw-h">{e(title)}</div>' + (f'<div class="zw-muted">{e(sub)}</div>' if sub else ""))


def kv(rows: list[tuple[str, str]], total: tuple[str, str] | None = None) -> None:
    out = "".join(f'<div class="zw-kv"><span>{e(a)}</span><b>{e(b)}</b></div>' for a, b in rows)
    if total:
        out += f'<div class="zw-kv total"><span>{e(total[0])}</span><b>{e(total[1])}</b></div>'
    html(out)


def note(text: str) -> None:
    html(f'<div class="zw-note">{e(text)}</div>')


def step_count(text: str) -> None:
    html(f'<div class="zw-step-count">{e(text)}</div>')


_card_count = [0]


def card():
    """A white card (bordered container) styled like the Milestone 6 wireframes."""
    _card_count[0] += 1
    return st.container(border=True, key=f"card_{_card_count[0]}")
