# Interactive Science

This folder is the deployed site at **https://interactive-science.com** — a set of
free, teacher-built AQA GCSE & KS3 science tools, revision booklets and retrieval
practice. Each `*.html` at the top level is a standalone page served directly.

## Adding or editing a resource

The homepage card grid and its SEO JSON-LD are **generated from a manifest**, so you
never hand-edit `index.html` to add a resource. Instead:

1. Edit **`resources.json`** — add/change one entry under the relevant section.
2. Run the build:

   ```sh
   python3 build.py
   ```

3. Commit `resources.json` and the regenerated `index.html`.

`build.py` rewrites only the card grid (between the `<!--GRID:START-->` /
`<!--GRID:END-->` markers) and the JSON-LD block. Everything else in `index.html`
(head, CSS, hero, filter bar, "Start here" featured cards, signup, footer, JS) is
left untouched. It is idempotent — running it twice produces the same file.

### Manifest entry shape

```json
{ "href": "my-tool.html", "accent": "#C84A6D", "cat": "biology",
  "tokens": "ks3 gcse tool", "spec": "AQA 4.1.1", "folder": "Cells & Microscopy",
  "name": "Zoom into <em>the Cell</em>", "tag": "short subtitle",
  "desc": "One-paragraph description.", "tags": ["KS3","GCSE"],
  "level": "GCSE", "type": "interactive tool", "about": "Biology" }
```

- `name` may contain `<em>…</em>` markup — it is kept verbatim on the card and
  stripped to plain text for the JSON-LD.
- `folder` is optional (tool cards have it; revision cards don't).
- `level` / `type` / `about` feed the JSON-LD `LearningResource`.
- **External link**: add `"external": true` and put the full `https://…` URL in
  `href`. The card gets `target="_blank" rel="noopener noreferrer"` and the JSON-LD
  uses the URL as-is.
- **Coming soon**: add `"coming": true` and omit `href` / `level` / `type` / `about`.
  Coming-soon cards render as a non-clickable card and are **excluded** from the
  JSON-LD.
- `data-text` (the search blob) is regenerated automatically — don't hand-write it.

The original one-off `extract.py` was used to bootstrap `resources.json` from the
old hand-written homepage. You won't normally need it again.

## Filename rules

- Use **lowercase-kebab-case** for new pages: `gas-exchange-revision.html`.
- **Case matters on the server** — `Cell-Zoom.html` and `cell-zoom.html` are
  different files. Always link with the exact filename.

## Folders

- **`interactives/`** — small embeddable widgets (e.g. `ph-slider.html`,
  `alveolus-diffusion.html`) that revision pages embed in `<iframe>`s.
- **`pdf/`** — print-ready booklet PDFs that the revision pages link to.
