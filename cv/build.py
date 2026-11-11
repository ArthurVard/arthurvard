"""Build the CV from Arthur_Vardanyan_CV.yaml.

Usage (from this folder):
    python build.py                          # full build, see "Outputs"
    python build.py --watch                  # re-render the PDF on every save
    python build.py --design.theme sb2nov    # extra arguments go to `rendercv render`
    python build.py other_cv.yaml [args...]  # a tailored copy: PDF, PNG and Markdown, no web page

Outputs:
    rendercv_output/  PDF, PNG previews, Markdown and Typst source: the files for applications.
                      They include the private values from private.yaml (the phone number).
    site/             The web page (index.html, style.css) and a PDF, built from the YAML as it is:
                      no private values, no extra arguments. GitHub Actions builds the same folder
                      and publishes it to GitHub Pages (../.github/workflows/cv-website.yml).

The first run creates .venv/ with the RenderCV version pinned in requirements.txt. The script then
re-runs itself inside .venv/, because the web page needs the Jinja2, Markdown and YAML libraries
that come with RenderCV.

RenderCV runs up to three times: (1) PDF, PNG and Typst; (2) Markdown, from a temporary copy without
the raw Typst lines of design.templates ("#set ...", "#show ...", "#v(...)"), which would print as
text; (3) the PDF for site/.
"""

import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DEFAULT_CV = ROOT / "Arthur_Vardanyan_CV.yaml"
PRIVATE = ROOT / "private.yaml"  # never committed (see .gitignore)
WEB = ROOT / "web"  # template and stylesheet of the web page
SITE = ROOT / "site"
VENV = ROOT / ".venv"
BIN = VENV / ("Scripts" if os.name == "nt" else "bin")
EXE = ".exe" if os.name == "nt" else ""
TYPST_STYLE_LINE = re.compile(r"^[ \t]+#(?:set|show|v)\b.*\r?\n", re.MULTILINE)
# RenderCV prints Unicode; without UTF-8 mode it crashes on Windows when output is piped.
ENV = {**os.environ, "PYTHONUTF8": "1"}


def run(*cmd) -> int:
    try:
        return subprocess.run(cmd, env=ENV).returncode
    except KeyboardInterrupt:  # Ctrl+C ends --watch
        return 130


def render(cv: Path, *args) -> int:
    return run(BIN / f"rendercv{EXE}", "render", cv, *args)


def main(args: list[str]) -> int:
    cv = Path(args.pop(0)).resolve() if args and args[0].endswith((".yaml", ".yml")) else DEFAULT_CV
    private = private_overrides()
    flags = set(args)

    # 1. PDF, PNG and Typst, with the private values: the files you send with applications.
    rc = render(cv, *args, *private, "-nomd", "-nohtml")
    if rc or flags & {"-w", "--watch"}:
        return rc

    # 2. Markdown, from a copy without the Typst style lines.
    if not flags & {"-nomd", "--dont-generate-markdown"}:
        plain = cv.with_name(f".{cv.stem}.plain.yaml")  # same folder, so outputs land in the same place
        plain.write_text(TYPST_STYLE_LINE.sub("", cv.read_text(encoding="utf-8")), encoding="utf-8")
        try:
            rc = render(plain, *args, *private, "-notyp", "-nopdf", "-nopng", "-nohtml")
        finally:
            plain.unlink(missing_ok=True)

    # 3. The web page, from the YAML exactly as committed: what GitHub Pages will show.
    if rc == 0 and cv == DEFAULT_CV:
        rc = build_site(cv)
    return rc


def private_overrides() -> list[str]:
    """private.yaml as RenderCV command-line overrides: {cv: {phone: X}} -> --cv.phone X."""
    if not PRIVATE.exists():
        return []
    from ruamel.yaml import YAML

    def flatten(node, key=""):
        if isinstance(node, dict):
            for name, value in node.items():
                yield from flatten(value, f"{key}.{name}" if key else str(name))
        elif isinstance(node, list):
            sys.exit(f"{PRIVATE.name}: {key} is a list; only single values are supported.")
        elif node is not None:
            yield f"--{key}"
            yield str(node)

    return list(flatten(YAML(typ="safe").load(PRIVATE.read_text(encoding="utf-8"))))


# ---------------------------------------------------------------------------------------------
# Web page: web/index.html.j2 + web/style.css, filled from the cv: and locale: parts of the YAML.
# (The design: part only affects the PDF; the page's look is in style.css.)

# Entry types, recognised by their fields as RenderCV does; the first match wins.
ENTRY_KINDS = [
    ("experience", {"company"}),
    ("education", {"institution"}),
    ("publication", {"title", "authors"}),
    ("one_line", {"label", "details"}),
    ("bullet", {"bullet"}),
    ("normal", {"name"}),
]
SOCIAL_URLS = {
    "LinkedIn": "https://linkedin.com/in/{}",
    "GitHub": "https://github.com/{}",
    "GitLab": "https://gitlab.com/{}",
    "X": "https://x.com/{}",
    "StackOverflow": "https://stackoverflow.com/users/{}",
    "ORCID": "https://orcid.org/{}",
    "YouTube": "https://youtube.com/@{}",
    "Telegram": "https://t.me/{}",
}
# Section keys become titles as in RenderCV: technical_skills -> Technical Skills.
SMALL_WORDS = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with"}


def build_site(cv: Path) -> int:
    """site/: index.html, style.css and a PDF without the private values."""
    shutil.rmtree(SITE, ignore_errors=True)
    if rc := render(cv, "-o", SITE, "-nomd", "-nohtml", "-nopng"):  # -notyp would skip the PDF too
        return rc
    for typst_source in SITE.glob("*.typ"):
        typst_source.unlink()
    pdfs = list(SITE.glob("*.pdf"))
    if len(pdfs) != 1:
        print(f"Expected one PDF in {SITE}, found {len(pdfs)}.", file=sys.stderr)
        return 1

    from ruamel.yaml import YAML

    data = YAML(typ="safe").load(cv.read_text(encoding="utf-8"))
    (SITE / "index.html").write_text(web_page(data, pdfs[0].name), encoding="utf-8")
    shutil.copy2(WEB / "style.css", SITE / "style.css")
    print(f"Web page: {SITE / 'index.html'}")
    return 0


def web_page(data: dict, pdf_name: str) -> str:
    import jinja2
    import markdown
    from markupsafe import Markup

    cv = data["cv"]
    locale = data.get("locale") or {}
    months = locale.get("month_abbreviations") or "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
    present = locale.get("present") or "present"

    def md(text) -> Markup:
        """Inline Markdown to HTML; a newline is a line break, as in the PDF."""
        html = markdown.markdown(str(text), extensions=["nl2br"])
        if html.startswith("<p>") and html.endswith("</p>") and html.count("<p>") == 1:
            html = html[3:-4]
        return Markup(html)

    def plain(text) -> str:
        return md(text).striptags()

    def month(value) -> str:
        if isinstance(value, datetime.date):
            return f"{months[value.month - 1]} {value.year}"
        if m := re.fullmatch(r"(\d{4})-(\d{1,2})(?:-\d{1,2})?", str(value)):
            return f"{months[int(m[2]) - 1]} {m[1]}"
        return present if str(value) == "present" else str(value)

    def dates(entry) -> str:
        if not isinstance(entry, dict):
            return ""
        if entry.get("start_date") is not None:
            return f"{month(entry['start_date'])} – {month(entry.get('end_date') or 'present')}"
        return month(entry["date"]) if entry.get("date") is not None else ""

    def kind(entry) -> str:
        if isinstance(entry, str):
            return "text"
        return next((name for name, fields in ENTRY_KINDS if fields <= entry.keys()), "normal")

    def title(key: str) -> str:
        if key != key.lower() or " " in key:
            return key  # already written as a title
        words = key.split("_")
        return " ".join(w if i and w in SMALL_WORDS else w[:1].upper() + w[1:] for i, w in enumerate(words))

    def as_list(value) -> list:
        return value if isinstance(value, list) else [value] if value else []

    links = [("location", cv["location"], None)] if cv.get("location") else []
    links += [("email", email, f"mailto:{email}") for email in as_list(cv.get("email"))]
    links += [("phone", phone, f"tel:{phone}") for phone in as_list(cv.get("phone"))]
    links += [("website", re.sub(r"^https?://(www\.)?|/$", "", url), url) for url in as_list(cv.get("website"))]
    for social in cv.get("social_networks") or []:
        url = SOCIAL_URLS.get(social["network"], "").format(social["username"]) or None
        links.append((social["network"].lower(), social["username"], url))

    sections = [
        {
            "id": key.replace("_", "-"),
            "title": title(key),
            "entries": [{"kind": kind(e), "dates": dates(e), "entry": e} for e in entries],
        }
        for key, entries in (cv.get("sections") or {}).items()
    ]

    headline = plain(cv.get("headline") or "")
    person = {  # schema.org data for search engines
        "@context": "https://schema.org",
        "@type": "Person",
        "name": cv.get("name"),
        "jobTitle": headline.split(" · ")[0] or None,
        "address": cv.get("location"),
        "email": next(iter(as_list(cv.get("email"))), None),
        "sameAs": [url for _, _, url in links if url and url.startswith("https://")] or None,
    }
    json_ld = json.dumps({k: v for k, v in person.items() if v}, ensure_ascii=False, indent=1)

    today = datetime.date.today()
    repo = os.environ.get("GITHUB_REPOSITORY")  # set by GitHub Actions
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(WEB), autoescape=True, trim_blocks=True, lstrip_blocks=True
    )
    env.filters["md"] = md
    return env.get_template("index.html.j2").render(
        cv=cv,
        links=links,
        sections=sections,
        pdf=pdf_name,
        updated=f"{months[today.month - 1]} {today.year}",
        description=". ".join(filter(None, [headline, cv.get("location")])),
        initials="".join(word[0] for word in cv["name"].split()[:2]).upper(),
        json_ld=Markup(json_ld.replace("</", "<\\/")),
        source=f"https://github.com/{repo}/tree/{os.environ.get('GITHUB_REF_NAME', 'main')}/cv" if repo else None,
    )


# ---------------------------------------------------------------------------------------------


def in_venv() -> bool:
    return VENV.is_dir() and os.path.samefile(sys.prefix, VENV)


def bootstrap() -> int:
    """Create .venv/ with the pinned RenderCV on the first run, then re-run this script inside it."""
    python = BIN / f"python{EXE}"
    if not (BIN / f"rendercv{EXE}").exists():
        print("First run: installing RenderCV into .venv/ ...", flush=True)
        venv.create(VENV, with_pip=True)
        if rc := run(python, "-m", "pip", "install", "-q", "-r", ROOT / "requirements.txt"):
            return rc
    return run(python, Path(__file__).resolve(), *sys.argv[1:])


if __name__ == "__main__":
    if not in_venv():
        sys.exit(bootstrap())
    rc = main(sys.argv[1:])
    if rc and rc != 130:
        print("\nBuild FAILED: the output folders still hold the last successful build.", file=sys.stderr)
    sys.exit(rc)
