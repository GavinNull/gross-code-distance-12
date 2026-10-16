"""PRL word-equivalent count for paper/draft.tex (APS length guide).

Counts the core (from \\maketitle to the acknowledgments): text including captions and
the Data availability statement, plus floats (single-column figure 150/aspect + 20,
double-column figure 300/(0.5*aspect) + 40, single-column table 13 + 6.5/line,
double-column table 26 + 13/line). Abstract, references, acknowledgments and End
Matter are reported separately (not counted in the core limit).
Usage: uv run python paper/scripts/count_words.py
"""
import re
import struct


def wc(x):
    return len(re.sub(r"\\[a-zA-Z]+\*?|[{}$\\&~]", " ", x).split())


def aspect(png):
    d = open(png, "rb").read(24)
    w, h = struct.unpack(">II", d[16:24])
    return w / h


s = open("paper/draft.tex").read()
t = re.sub(r"(?<!\\)%.*", "", s)
abstract = t[t.index("\\begin{abstract}") + 16:t.index("\\end{abstract}")]
core = t[t.index("\\maketitle"):t.index("\\begin{acknowledgments}")]
endm = t[t.index("\\section*{End Matter}"):t.index("\\clearpage")]
floats = list(re.finditer(r"\\begin\{(table\*?|figure\*?)\}.*?\\end\{\1\}", core, re.S))
body = re.sub(r"\\begin\{(table\*?|figure\*?)\}.*?\\end\{\1\}", "", core, flags=re.S)
paras = re.split(r"\\paragraph\{([^}]*)\}", body)
print(f"abstract: {wc(abstract)} words (not counted)")
total = 0
sections = [("Introduction", paras[0])] + [(paras[i], paras[i + 1]) for i in range(1, len(paras) - 1, 2)]
for name, txt in sections:
    n = wc(txt)
    total += n
    print(f"  text  {name:35s} {n:5d}")
for f in floats:
    kind, blk = f.group(1), f.group(0)
    cap = wc(re.search(r"\\caption\{(.*?)\}\s*\\label", blk, re.S).group(1))
    if kind.startswith("figure"):
        png = re.search(r"\\includegraphics\[[^]]*\]\{([^}]+)\.pdf\}", blk).group(1) + ".png"
        a = aspect("paper/" + png)
        area = 300 / (0.5 * a) + 40 if kind.endswith("*") else 150 / a + 20
    else:
        rows = blk.count("\\\\") 
        area = 26 + 13 * rows if kind.endswith("*") else 13 + 6.5 * rows
    total += cap + area
    print(f"  float {kind:8s} caption {cap:4d} + area {area:6.0f}")
print(f"CORE TOTAL (word-equivalents): {total:.0f}  (limit 3750)")
print(f"End Matter: {wc(endm)} words (separate limit: 2 pages)")
