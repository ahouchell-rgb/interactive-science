#!/usr/bin/env python3
"""Inject a LIVE, answerable retrieval-practice widget into the revision booklets
that are mapped to a retrieval-app topic, turning a passive read into an active
retrieval session — the booklet stops being static.

The widget is an <iframe> to retrieval-app's /embed/practice route. Questions are
pulled LIVE from the shared question bank for the mapped topic, so a question
authored (and shared) in feynman-education shows up here automatically — one
content pipeline, two surfaces. It's fully anonymous (no login to practise) and
ends on a "carry this into a free account" bridge inside the iframe.

Idempotent + marker-based, exactly like add_retrieval_cta.py: a marked block is
replaced if present, otherwise inserted just ABOVE the retrieval CTA (so the order
reads revise -> practise -> sign up), else before </body>. Re-run any time — safe.

  - Only touches booklets listed in resources.json -> site.retrieval_topics
    (slug -> topic UUID). Everything else is left untouched.
  - The block is fully inline-styled and ships its own tiny resize listener, so it
    renders correctly whether or not the booklet's own CSS / resize host is present.
  - Embed base comes from site.retrieval_url, overridable with the env var
    RETRIEVAL_EMBED_BASE (e.g. http://localhost:3000 for local verification).

Usage:
  python3 add_retrieval_widget.py
  RETRIEVAL_EMBED_BASE=http://localhost:3000 python3 add_retrieval_widget.py
"""
import os
import re
import json
import glob

HERE = os.path.dirname(os.path.abspath(__file__))

START = "<!--ISCI-RETRIEVAL-WIDGET:START"
END = "<!--ISCI-RETRIEVAL-WIDGET:END-->"
CTA_START = "<!--ISCI-RETRIEVAL-CTA:START"

SUBJECT = {
    "biology": "biology",
    "physics": "physics",
    "chemistry": "chemistry",
    "environmental": "environmental science",
}


def widget_block(slug, phrase, topic_id, embed_base):
    src = f"{embed_base}/embed/practice?topic={topic_id}&amp;ref=interactive-science&amp;from={slug}"
    return (
        f"{START} (auto-injected by add_retrieval_widget.py; do not edit)-->\n"
        '<section style="max-width:680px;margin:48px auto 8px;padding:22px 24px;'
        "border:1px solid #d7ddd4;border-left:4px solid #2E7D4F;border-radius:12px;"
        "background:#f6f9f4;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;"
        'box-sizing:border-box;">\n'
        '  <div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;'
        'color:#2E7D4F;font-weight:700;margin-bottom:6px;">Practice &middot; retrieval</div>\n'
        '  <div style="font-size:19px;font-weight:600;line-height:1.35;margin-bottom:6px;color:#1d2a20;">'
        "Check you&rsquo;ve actually got it.</div>\n"
        '  <div style="font-size:14px;color:#48564a;margin-bottom:16px;">'
        f"Answer {phrase} and get instant, marked feedback &mdash; no login needed.</div>\n"
        f'  <iframe id="isci-rp-frame" src="{src}" title="Retrieval practice" loading="lazy" '
        'style="width:100%;height:520px;border:0;display:block;border-radius:8px;background:#fff;"></iframe>\n'
        "</section>\n"
        "<script>\n"
        "(function(){var f=document.getElementById('isci-rp-frame');if(!f)return;"
        "window.addEventListener('message',function(e){var d=e.data;"
        "if(d&&d.type==='iscience:resize'&&f.contentWindow===e.source&&d.height>0&&d.height<20000){"
        "f.style.height=Math.ceil(d.height)+'px';}});})();\n"
        "</script>\n"
        f"{END}"
    )


def inject(path, block):
    html = open(path, encoding="utf-8").read()
    marker_re = re.compile(re.escape(START) + ".*?" + re.escape(END), re.S)
    if marker_re.search(html):
        new = marker_re.sub(lambda m: block, html, count=1)
        action = "updated"
    elif CTA_START in html:
        idx = html.find(CTA_START)
        new = html[:idx] + block + "\n" + html[idx:]
        action = "inserted-above-cta"
    elif "</body>" in html:
        idx = html.rfind("</body>")
        new = html[:idx] + block + "\n" + html[idx:]
        action = "inserted"
    else:
        return "SKIP (no </body>)"
    if new != html:
        open(path, "w", encoding="utf-8").write(new)
    return action


def main():
    manifest = json.load(open(os.path.join(HERE, "resources.json"), encoding="utf-8"))
    site = manifest.get("site", {})
    embed_base = os.environ.get("RETRIEVAL_EMBED_BASE") or site.get("retrieval_url", "https://retrieval-app.com")
    embed_base = embed_base.rstrip("/")
    topics = site.get("retrieval_topics", {})

    by_href = {}
    for section in manifest.get("sections", []):
        for item in section.get("items", []):
            if item.get("href"):
                by_href[item["href"]] = item

    if not topics:
        print("No site.retrieval_topics in resources.json — nothing to do.")
        return

    print(f"embed base: {embed_base}\n")
    counts = {"inserted": 0, "inserted-above-cta": 0, "updated": 0, "missing": 0}
    for slug, topic_id in topics.items():
        name = slug + ".html"
        path = os.path.join(HERE, name)
        if not os.path.exists(path):
            counts["missing"] += 1
            print("widget", name, "-> MISSING (no such booklet)")
            continue
        item = by_href.get(name, {})
        subj = SUBJECT.get(item.get("cat"))
        phrase = f"a few {subj} questions" if subj else "a few questions"
        action = inject(path, widget_block(slug, phrase, topic_id, embed_base))
        counts[action] = counts.get(action, 0) + 1
        print("widget", name, "->", action, f"(topic {topic_id[:8]}…)")

    print("\n" + ", ".join(f"{k}: {v}" for k, v in counts.items()))


if __name__ == "__main__":
    main()
