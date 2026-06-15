#!/usr/bin/env python3
"""Regenerate index.html from resources.json.

Replaces everything between <!--GRID:START--> and <!--GRID:END--> with freshly
generated <section class="group"> blocks, and rebuilds the JSON-LD ItemList.
Everything else in index.html is left byte-for-byte unchanged. Idempotent:
running it twice yields the same file.

Usage:  python3 build.py
"""
import json
import re
import os

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX = os.path.join(HERE, "index.html")
MANIFEST = os.path.join(HERE, "resources.json")

manifest = json.load(open(MANIFEST, encoding="utf-8"))
origin = manifest["site"]["origin"].rstrip("/")
sections = manifest["sections"]

html = open(INDEX, encoding="utf-8").read()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
_TAG_RE = re.compile(r"<[^>]+>")


def strip_tags(s):
    """Plain text from a name that may contain <em>…</em>."""
    return _TAG_RE.sub("", s)


def data_text(item):
    """lowercase: name + tag + desc + folder + spec + tokens."""
    parts = [
        strip_tags(item.get("name", "")),
        item.get("tag", ""),
        item.get("desc", ""),
        item.get("folder", ""),
        item.get("spec", ""),
        item.get("tokens", ""),
    ]
    return " ".join(p for p in parts if p).lower()


def render_card(item):
    accent = item["accent"]
    cat = item["cat"]
    tokens = item.get("tokens", "")
    dt = data_text(item)
    spec = item.get("spec", "")
    name = item.get("name", "")
    tag = item.get("tag", "")
    desc = item.get("desc", "")
    tags = item.get("tags", [])
    tags_html = "".join('<span class="tag">%s</span>' % t for t in tags)

    if item.get("coming"):
        top = (
            '<div class="card-top"><span class="card-spec">%s</span>'
            '<span class="soon">Coming soon</span></div>' % spec
        )
        return (
            '<div class="card coming" style="--accent:%s" data-cat="%s" '
            'data-tokens="%s" data-text="%s">'
            '%s'
            '<h3 class="card-name">%s</h3>'
            '<p class="card-tag">%s</p>'
            '<p class="card-desc">%s</p>'
            '<div class="card-tags">%s</div>'
            '</div>'
            % (accent, cat, tokens, dt, top, name, tag, desc, tags_html)
        )

    external = item.get("external", False)
    href = item["href"]
    target = ' target="_blank" rel="noopener noreferrer"' if external else ""
    top = (
        '<div class="card-top"><span class="card-spec">%s</span>'
        '<i class="ti ti-arrow-up-right card-arrow" aria-hidden="true"></i></div>'
        % spec
    )
    folder_html = ""
    if "folder" in item:
        folder_html = '<span class="card-folder">%s</span>' % item["folder"]
    return (
        '<a class="card" href="%s"%s style="--accent:%s" data-cat="%s" '
        'data-tokens="%s" data-text="%s">'
        '%s%s'
        '<h3 class="card-name">%s</h3>'
        '<p class="card-tag">%s</p>'
        '<p class="card-desc">%s</p>'
        '<div class="card-tags">%s</div>'
        '</a>'
        % (href, target, accent, cat, tokens, dt, top, folder_html, name, tag,
           desc, tags_html)
    )


def render_section(sec):
    count = len(sec["items"])
    cards = "".join(render_card(it) for it in sec["items"])
    return (
        '<section class="group" id="%s" data-group="%s">'
        '<div class="group-head"><h2>%s</h2>'
        '<span class="group-blurb">%s</span>'
        '<span class="group-count">%d</span></div>'
        '<div class="grid">%s</div></section>'
        % (sec["id"], sec["id"], sec["title"], sec["blurb"], count, cards)
    )


# ---------------------------------------------------------------------------
# 1. Replace the grid region between the markers
# ---------------------------------------------------------------------------
grid_html = "\n".join(render_section(s) for s in sections)
new_region = "<!--GRID:START-->\n%s\n  <!--GRID:END-->" % grid_html

grid_re = re.compile(r"<!--GRID:START-->.*?<!--GRID:END-->", re.S)
if not grid_re.search(html):
    raise SystemExit("GRID markers not found in index.html")
html = grid_re.sub(lambda m: new_region, html, count=1)


# ---------------------------------------------------------------------------
# 2. Rebuild the JSON-LD ItemList (non-coming items only, sequential position)
# ---------------------------------------------------------------------------
def card_url(item):
    if item.get("external"):
        return item["href"]
    return origin + "/" + item["href"]


ld_re = re.compile(
    r'(<script type="application/ld\+json">)(.*?)(</script>)', re.S
)
m = ld_re.search(html)
if not m:
    raise SystemExit("JSON-LD script block not found")
ld = json.loads(m.group(2))

elements = []
pos = 0
for sec in sections:
    for it in sec["items"]:
        if it.get("coming"):
            continue
        pos += 1
        about = it.get("about")
        resource = {
            "@type": "LearningResource",
            "name": strip_tags(it.get("name", "")),
            "url": card_url(it),
            "description": it.get("desc", ""),
            "educationalLevel": it.get("level"),
            "learningResourceType": it.get("type"),
            "inLanguage": "en-GB",
            "isAccessibleForFree": True,
        }
        if about:
            resource["about"] = {"@type": "Thing", "name": about}
        elements.append(
            {"@type": "ListItem", "position": pos, "item": resource}
        )

for node in ld["@graph"]:
    if node.get("@type") == "ItemList":
        node["numberOfItems"] = pos
        node["itemListElement"] = elements

# Serialise with the same conventions as the original block:
# ", " and ": " separators, ensure_ascii=False to keep unicode chars intact.
new_ld = json.dumps(ld, ensure_ascii=False, separators=(", ", ": "))
html = ld_re.sub(
    lambda mm: mm.group(1) + new_ld + mm.group(3), html, count=1
)

with open(INDEX, "w", encoding="utf-8") as f:
    f.write(html)

n_internal_ext = pos
print("Rebuilt index.html")
print("  sections:", [(s["id"], len(s["items"])) for s in sections])
print("  JSON-LD numberOfItems:", n_internal_ext)
