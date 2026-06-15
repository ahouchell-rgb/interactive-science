#!/usr/bin/env python3
"""One-off extractor: parse index.html into resources.json.

Run once to bootstrap the manifest from the existing hand-written homepage.
After this, edit resources.json and run build.py to regenerate index.html.
"""
import json
import re
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "index.html")
OUT = os.path.join(HERE, "resources.json")
ORIGIN = "https://interactive-science.com"

html = open(SRC, encoding="utf-8").read()

# ---- 1. Parse the JSON-LD ItemList into a url -> metadata map ----------------
ldm = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
ld = json.loads(ldm.group(1))
meta_by_url = {}
for node in ld["@graph"]:
    if node.get("@type") == "ItemList":
        for li in node["itemListElement"]:
            it = li["item"]
            meta_by_url[it["url"]] = {
                "level": it.get("educationalLevel"),
                "type": it.get("learningResourceType"),
                "about": it.get("about", {}).get("name"),
            }


def basename(url):
    return url.rstrip("/").rsplit("/", 1)[-1]


# map by basename for internal lookups, plus full-url for externals
meta_by_basename = {basename(u): m for u, m in meta_by_url.items()}


def lookup_meta(href, external):
    if external:
        # match full url (allow trailing-slash differences)
        for u, m in meta_by_url.items():
            if u.rstrip("/") == href.rstrip("/"):
                return m
        return {}
    return meta_by_basename.get(basename(href), {})


# ---- 2. Isolate the section run --------------------------------------------
# The featured-wrap "Start here" block is BEFORE the first <section class="group">
# and must be ignored. Take from first group section to its end.
start = html.index('<section class="group"')
# end: just after the final </section> belonging to the group run, i.e. the
# </section> immediately preceding the empty/signup region.
end_marker = html.index('<div class="empty"', start)
run = html[start:end_marker]

section_re = re.compile(
    r'<section class="group" id="(?P<id>[^"]+)" data-group="[^"]+">'
    r'<div class="group-head"><h2>(?P<title>.*?)</h2>'
    r'<span class="group-blurb">(?P<blurb>.*?)</span>'
    r'<span class="group-count">\d+</span></div>'
    r'<div class="grid">(?P<body>.*?)</div></section>',
    re.S,
)

# Card regexes (anchor = internal/external, div = coming soon)
anchor_re = re.compile(
    r'<a class="card" href="(?P<href>[^"]*)"(?P<attrs>[^>]*?)>'
    r'(?P<inner>.*?)</a>',
    re.S,
)
coming_re = re.compile(
    r'<div class="card coming"(?P<attrs>[^>]*?)>(?P<inner>.*?</div>)</div>',
    re.S,
)


def grab(pat, text, default=None):
    m = re.search(pat, text, re.S)
    return m.group(1) if m else default


def parse_card_inner(inner):
    d = {}
    d["spec"] = grab(r'<span class="card-spec">(.*?)</span>', inner)
    folder = grab(r'<span class="card-folder">(.*?)</span>', inner)
    if folder is not None:
        d["folder"] = folder
    d["name"] = grab(r'<h3 class="card-name">(.*?)</h3>', inner)
    d["tag"] = grab(r'<p class="card-tag">(.*?)</p>', inner)
    d["desc"] = grab(r'<p class="card-desc">(.*?)</p>', inner)
    tags_blob = grab(r'<div class="card-tags">(.*?)</div>', inner) or ""
    d["tags"] = re.findall(r'<span class="tag">(.*?)</span>', tags_blob)
    return d


def attr(attrs, name):
    m = re.search(r'%s="([^"]*)"' % re.escape(name), attrs)
    return m.group(1) if m else None


sections = []
for sm in section_re.finditer(run):
    sec = {
        "id": sm.group("id"),
        "title": sm.group("title"),
        "blurb": sm.group("blurb"),
        "items": [],
    }
    body = sm.group("body")
    # Walk body in order, matching either coming-soon div or anchor.
    pos = 0
    # Build an ordered list of (start, kind, match)
    events = []
    for m in coming_re.finditer(body):
        events.append((m.start(), "coming", m))
    for m in anchor_re.finditer(body):
        events.append((m.start(), "anchor", m))
    events.sort(key=lambda e: e[0])
    for _, kind, m in events:
        if kind == "coming":
            attrs = m.group("attrs")
            inner = m.group("inner")
            card = {
                "accent": attr(attrs, "--accent")
                or re.search(r'--accent:([^";]+)', attrs).group(1),
                "cat": attr(attrs, "data-cat"),
                "tokens": attr(attrs, "data-tokens"),
                "coming": True,
            }
            card.update(parse_card_inner(inner))
            sec["items"].append(card)
        else:
            href = m.group("href")
            attrs = m.group("attrs")
            inner = m.group("inner")
            external = href.startswith("http://") or href.startswith("https://")
            card = {"href": href}
            card["accent"] = re.search(r'--accent:([^";]+)', attrs).group(1)
            card["cat"] = attr(attrs, "data-cat")
            card["tokens"] = attr(attrs, "data-tokens")
            if external:
                card["external"] = True
            card.update(parse_card_inner(inner))
            meta = lookup_meta(href, external)
            if meta.get("level"):
                card["level"] = meta["level"]
            if meta.get("type"):
                card["type"] = meta["type"]
            if meta.get("about"):
                card["about"] = meta["about"]
            sec["items"].append(card)
    sections.append(sec)

manifest = {"site": {"origin": ORIGIN}, "sections": sections}

# ---- 3. Asserts ------------------------------------------------------------
all_hrefs = [it["href"] for s in sections for it in s["items"] if "href" in it]
total_cards = sum(len(s["items"]) for s in sections)
print("Total cards parsed:", total_cards)
print("Sections:", [(s["id"], len(s["items"])) for s in sections])

# count cards in the section run of the source (anchors + coming, within run)
src_anchor_hrefs = re.findall(r'<a class="card" href="([^"]*)"', run)
src_coming = run.count('class="card coming"')
print("Source run anchors:", len(src_anchor_hrefs), "coming:", src_coming)
assert total_cards == len(src_anchor_hrefs) + src_coming, "card count mismatch"
assert set(all_hrefs) == set(src_anchor_hrefs), "href set mismatch"

with open(OUT, "w", encoding="utf-8") as f:
    json.dump(manifest, f, ensure_ascii=False, indent=2)
    f.write("\n")
print("Wrote", OUT)
