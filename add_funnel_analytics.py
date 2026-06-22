#!/usr/bin/env python3
"""Inject a tiny, cookieless page-view beacon onto every standalone content page so
organic booklet reach is measured in the same funnel the live widget already feeds.

Why: the retrieval funnel runs on ?ref/?from attribution, but the STATIC booklet
pages recorded nothing — only the 43 pages that embed the live practice widget
(/embed/practice) fired `booklet_viewed`. This closes the gap for the remaining
content pages so we can see which booklets actually pull readers, and (with the
retrieval-app Landing's `signup_clicked` event) how that converts to sign-ups.

Design — mirrors add_retrieval_cta.py / add_resize.py:
  - Idempotent + marker-based: a marked block is replaced if present, else inserted
    before </body>. Re-run any time.
  - SKIPS pages that already embed the widget (they fire booklet_viewed from the
    iframe — beaconing here too would double-count).
  - SKIPS index.html (hub, not a booklet).
  - Posts a single `booklet_viewed` to the public emit-funnel-event edge function
    (best-effort, keepalive, never blocks the page). No cookies; a random session id
    in localStorage stitches a visit. NO PII.

The Supabase URL + anon key below are the PUBLIC values already shipped in the
retrieval-app client bundle and the embedded widget — safe to inline. RLS + revoked
grants protect anon_funnel_events; the anon key is only the apikey to reach the fn.

Usage:  python3 add_funnel_analytics.py
"""
import os
import re
import glob

HERE = os.path.dirname(os.path.abspath(__file__))

START = "<!--ISCI-FUNNEL-ANALYTICS:START"
END = "<!--ISCI-FUNNEL-ANALYTICS:END-->"

EMIT_URL = "https://uvzukwoxqhcxaxtzrziy.supabase.co/functions/v1/emit-funnel-event"
ANON_KEY = ("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InV2enVrd294cWhjeGF4dHpyeml5Iiwicm9sZSI6ImFub24i"
            "LCJpYXQiOjE3NzQzNDUyNTIsImV4cCI6MjA4OTkyMTI1Mn0."
            "PtT24EfMfTckYaq9jXBPRuCsG6utWMLcHs9H8buM70c")


def beacon_block(slug):
    return (
        f"{START} (auto-injected by add_funnel_analytics.py; do not edit)-->\n"
        "<script>\n"
        "(function(){\n"
        "  try{\n"
        f'    var EP="{EMIT_URL}",KEY="{ANON_KEY}",FROM="{slug}";\n'
        '    var sid=null;\n'
        '    try{sid=localStorage.getItem("isci_sid");if(!sid){sid=(window.crypto&&crypto.randomUUID)?crypto.randomUUID():String(Date.now())+Math.random().toString(16).slice(2);localStorage.setItem("isci_sid",sid);}}catch(e){}\n'
        '    fetch(EP,{method:"POST",headers:{"Content-Type":"application/json","apikey":KEY},'
        'body:JSON.stringify({event:"booklet_viewed",session_id:sid,ref:"interactive-science",from_source:FROM}),'
        'keepalive:true}).catch(function(){});\n'
        "  }catch(e){}\n"
        "})();\n"
        "</script>\n"
        f"{END}"
    )


def inject(path, block):
    html = open(path, encoding="utf-8").read()
    marker_re = re.compile(re.escape(START) + ".*?" + re.escape(END), re.S)
    if marker_re.search(html):
        new = marker_re.sub(lambda m: block, html, count=1)
        action = "updated"
    elif "</body>" in html:
        idx = html.rfind("</body>")
        new = html[:idx] + block + "\n" + html[idx:]
        action = "inserted"
    else:
        return "skip-other"
    if new != html:
        open(path, "w", encoding="utf-8").write(new)
    return action


def main():
    counts = {"inserted": 0, "updated": 0, "skip-widget": 0, "skip-index": 0, "skip-other": 0}
    for path in sorted(glob.glob(os.path.join(HERE, "*.html"))):
        name = os.path.basename(path)
        if name == "index.html":
            counts["skip-index"] += 1
            continue
        html = open(path, encoding="utf-8").read()
        # Pages embedding the live widget already fire booklet_viewed from the iframe.
        if "embed/practice" in html:
            counts["skip-widget"] += 1
            print("skip ", name, "(widget page — already measured)")
            continue
        slug = name[:-5] if name.endswith(".html") else name
        action = inject(path, beacon_block(slug))
        counts[action] = counts.get(action, 0) + 1
        print("beacon", name, "->", action)

    print("\n" + ", ".join(f"{k}: {v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
