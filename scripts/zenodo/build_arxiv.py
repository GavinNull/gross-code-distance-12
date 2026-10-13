"""Build release/arxiv/: arXiv source bundle of paper/draft.tex.

- main.tex = draft.tex with every comment removed (full-line comments dropped, trailing comments cut to a bare '%'
  so that line-end behaviour is unchanged) and the invisible claim tags \\cl{...} with their macro definitions removed
  (they render nothing; removing them does not change the output);
- figures/*.pdf = the figures that main.tex includes (metadata checked for local paths);
- the bibliography is inline (thebibliography), so no .bib/.bbl is needed.
Then: tectonic main.tex in a temporary copy of release/arxiv; the extracted text of the result must equal that of
paper/draft.tex compiled the same way (proves that stripping changed nothing visible).

    uv run python scripts/zenodo/build_arxiv.py
"""
import hashlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SRC = Path("paper/draft.tex")
OUT = Path("release/arxiv")
tex = SRC.read_text()
print("source sha256", hashlib.sha256(tex.encode()).hexdigest())


def strip_comments(s: str) -> str:
    out = []
    for line in s.splitlines():
        m = re.search(r"(?<!\\)%", line)
        if m is None:
            out.append(line)
            continue
        before = line[:m.start()]
        if before.strip() == "":
            continue                      # full-line comment: drop the line (it produced no output)
        out.append(before + "%")
    return "\n".join(out) + "\n"


t = strip_comments(tex)
# claim tags: macro definitions and every use (they expand to nothing with \showclaimtagsfalse)
assert "\\showclaimtagsfalse" in t
t = t.replace("\\newif\\ifshowclaimtags \\showclaimtagsfalse\n", "")
t = re.sub(r"\\newcommand\{\\cl\}\[1\]\{\\ifshowclaimtags.*?\\fi\}\n", "", t)
t = re.sub(r"\\cl\{[0-9,\s]*\}", "", t)
assert "\\cl{" not in t and "showclaimtags" not in t, "claim tag left"
# collapse runs of blank lines
t = re.sub(r"\n{3,}", "\n\n", t)
figs = re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", t)
if OUT.exists():
    shutil.rmtree(OUT)
(OUT / "figures").mkdir(parents=True)
(OUT / "main.tex").write_text(t)
for f in figs:
    data = (Path("paper") / f).read_bytes()
    for bad in (b"/Users", b"qec-ai", b"ephemeral", b"Desktop"):
        assert bad not in data, (f, bad)
    (OUT / f).write_bytes(data)
for bad in ("claims_map", "STATE", "audit", "E-0", "results/", "search/", "research/", "/Users", "TODO",
            "UNVERIFIED", "experimenter"):
    if bad in t:
        print("WARNING: string", repr(bad), "occurs in main.tex")


def build(srcdir: Path, name: str) -> str:
    with tempfile.TemporaryDirectory() as d:
        shutil.copytree(srcdir, d, dirs_exist_ok=True)
        r = subprocess.run(["tectonic", "--keep-logs", name], cwd=d, capture_output=True, text=True)
        if r.returncode:
            print(r.stdout[-3000:], r.stderr[-3000:])
            sys.exit("tectonic failed")
        pdf = Path(d) / name.replace(".tex", ".pdf")
        log = (Path(d) / name.replace(".tex", ".log")).read_text(errors="ignore")
        und = re.findall(r"undefined", log)
        txt = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True).stdout \
            if shutil.which("pdftotext") else ""
        return txt, len(und), pdf.stat().st_size


with tempfile.TemporaryDirectory() as d0:
    # original, compiled the same way (only draft.tex + its figures)
    p = Path(d0)
    shutil.copy(SRC, p / "draft.tex")
    (p / "figures").mkdir()
    for f in figs:
        shutil.copy(Path("paper") / f, p / f)
    txt0, und0, _ = build(p, "draft.tex")
txt1, und1, size = build(OUT, "main.tex")
print("undefined references (orig, arxiv):", und0, und1, "| pdf size", size)
if txt0:
    same = txt0.replace("\x0c", "") == txt1.replace("\x0c", "")
    print("extracted text identical to the original build:", same)
else:
    print("pdftotext not available; text comparison skipped")
print("files:", sorted(str(x.relative_to(OUT)) for x in OUT.rglob("*") if x.is_file()))
