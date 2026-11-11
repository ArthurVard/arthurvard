# CV as code

My CV lives in one YAML file, [`Arthur_Vardanyan_CV.yaml`](Arthur_Vardanyan_CV.yaml).
[RenderCV](https://github.com/rendercv/rendercv) turns it into Typst (a modern LaTeX alternative)
and compiles that to PDF, so no LaTeX install is needed. `build.py` renders a web page from the same file.

Web version: **https://arthurvard.github.io/arthurvard/**

## Build

```sh
python build.py                          # everything, see the table
python build.py --watch                  # re-render the PDF on every save
python build.py --design.theme sb2nov    # try another theme without editing the YAML
```

The first run creates `.venv/` and installs the RenderCV version pinned in `requirements.txt`
(Python 3.12+). To upgrade, change the version there and delete `.venv/`.

| Output | Use |
|---|---|
| `rendercv_output/Arthur_Vardanyan_CV.pdf` | Applications and ATS uploads. Includes the private values (phone). |
| `rendercv_output/Arthur_Vardanyan_CV.md` | Plain text for application forms; `pandoc Arthur_Vardanyan_CV.md -o cv.docx` for Word. |
| `rendercv_output/Arthur_Vardanyan_CV_*.png` | Page previews. |
| `rendercv_output/Arthur_Vardanyan_CV.typ` | Generated Typst source. Read-only: every build overwrites it. |
| `site/` | The web page and a PDF without the private values. A local preview, not committed: GitHub builds the same page itself (see Publishing). Open `site/index.html` to preview. |

## Private values

The repository is public, so the phone number is not in the CV's YAML. It lives in `private.yaml`
in this folder, which git ignores:

```yaml
cv:
  phone: "+374..."   # keep the quotes, or YAML drops the "+"
```

`build.py` passes these values to RenderCV (as `--cv.phone ...`) for the files in `rendercv_output/`
only; without the file, the CV renders without them. The CV's YAML keeps `phone:` as an empty key
because the header lists contacts in key order, and a value that isn't there would be added at the end.
The web page and its PDF never get these values, and GitHub never sees the file. The same works for any
other single value (e.g. `email:`); lists aren't supported. Private notes can go in the same file as comments.

## Publishing

Git uploads only the sources: the YAML, `build.py`, `requirements.txt` and `web/`. The built `site/`
folder is git-ignored; GitHub builds its own copy. It's like committing the `.tex` file, not the PDF:

```text
your PC                                  GitHub
YAML + build.py + web/  ── git push ──►  repository (sources only)
                                           │ the workflow runs: python cv/build.py
site/  (local preview only)                ▼
                                         its own site/ ──► GitHub Pages
```

Every push to `main` that changes `cv/` runs [`cv-website.yml`](../.github/workflows/cv-website.yml).
It builds the CV and publishes `site/` to **https://arthurvard.github.io/arthurvard/**. A run takes
1–2 minutes and has two jobs, *build* and *deploy*. Progress and errors appear in the repository's
**Actions** tab.

One-time setup, before the first push. GitHub Pages needs no separate repository and no `gh-pages`
branch:

1. Open the repository's **Settings → Pages**.
2. Under **Build and deployment → Source**, choose **GitHub Actions** (not "Deploy from a branch").
3. Ignore the workflows GitHub suggests ("Static HTML", "Jekyll"): this one is already in the repository.

Pages is free because the repository is public; private repositories need a paid plan for it.

## How the YAML works

- `cv:` is the content, `design:` the PDF layout, `locale:` the date words.
- Markdown works in every text field: `**bold**`, `*italic*`, `[link](https://…)`.
- Quote a value that starts with `*` or contains `: `. Otherwise YAML reads it as a mapping, and
  RenderCV's error doesn't mention the colon.
- `>-` joins the lines of a block into one paragraph; `|-` keeps each line as its own line.
- **`stack:`** is a custom field: every job and project has one, e.g. `stack: "*Stack: C#, PostgreSQL*"`.
  The templates in `design.templates` print it as the entry's last line; leave it out and nothing prints.
- **Text sizes.** RenderCV's options set one body size, not "descriptions smaller than job titles".
  So each template in `design.templates` starts with raw Typst lines:
  - `#set text(1.0752688em)` scales the entry back up to 10pt. The body is 9.3pt, so the summary
    and skills stay smaller.
  - `#show block: set text(0.93em)` shrinks the description and the bullets.
  - `#show emph: set text(0.88em)` shrinks the italic stack line.
  - `#v(3pt)` adds the gap above the stack line.

  These lines must come first in a template, because RenderCV damages raw Typst that follows an empty field.
- **Two-pass build.** Those Typst lines would print as text in the Markdown, so `build.py` renders
  the Markdown from a temporary copy without them. The web page has its own template and style
  (`web/index.html.j2`, `web/style.css`), modelled on the PDF.
- A `;` right after bold or italic text disappears from the PDF (Typst syntax): use a full stop.
- Years are unquoted numbers (`date: 2003`); a quoted year prints as "Jan 2003".
- Every design option is documented at [docs.rendercv.com](https://docs.rendercv.com).
  `.venv/Scripts/rendercv new "Name"` writes a sample file that lists them all.
- In VS Code, the Red Hat YAML extension gives autocomplete and validation from the schema line at
  the top of the file.

## Tailored versions

Copy the YAML (e.g. `cv_haskell.yaml`), trim and reorder it, and give it its own output folder,
because output file names come from `cv.name`:

```sh
python build.py cv_haskell.yaml -o rendercv_output/haskell
```

It gets the private values too, but no web page. A committed copy is public like everything else
here, so keep tailored copies out of git if they shouldn't be.

## Content guidelines

- Bullets: action verb + what you built + the result. Add numbers wherever they are true.
- Last ~10 years in detail; older roles in one or two lines.
- A single column of real text, as here: ATS parsers read it reliably, while photos, skill bars
  and multi-column layouts often break them.
- Update the CV when something ships, not only when job hunting.
