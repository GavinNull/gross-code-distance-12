"""Known weight-6 BB codes transcribed from research/literature/qldpc-code-catalog.md.

Every entry carries its arXiv source.  `d_kind` is what the paper reports: "exact" or "upper".
Wang–Mueller d values are "reported" (the catalog notes the paper does not mark exact vs. bound).
"""
from __future__ import annotations

from search.codes.construct import bb_code, coprime_bb_code

# (name, l, m, A, B, n, k, d, d_kind, source)
IBM_TABLE3 = [
    ("[[72,12,6]]", 6, 6, "x^3+y+y^2", "y^3+x+x^2", 72, 12, 6, "exact"),
    ("[[90,8,10]]", 15, 3, "x^9+y+y^2", "1+x^2+x^7", 90, 8, 10, "exact"),
    ("[[108,8,10]]", 9, 6, "x^3+y+y^2", "y^3+x+x^2", 108, 8, 10, "exact"),
    ("[[144,12,12]]", 12, 6, "x^3+y+y^2", "y^3+x+x^2", 144, 12, 12, "exact"),
    ("[[288,12,18]]", 12, 12, "x^3+y^2+y^7", "y^3+x+x^2", 288, 12, 18, "exact"),
    ("[[360,12,<=24]]", 30, 6, "x^9+y+y^2", "y^3+x^25+x^26", 360, 12, 24, "upper"),
    ("[[756,16,<=34]]", 21, 18, "x^3+y^10+y^17", "y^5+x^3+x^19", 756, 16, 34, "upper"),
]
IBM_SECTION4 = [  # examples in Sec. 4 text, outside Table 3 (k only from paper text)
    ("[[784,24,<=24]]", 28, 14, "x^26+y^6+y^8", "y^7+x^9+x^20", 784, 24, 24, "upper"),
    ("[[432,4,<=22]]", 18, 12, "x+y^11+y^3", "y^2+x^15+x", 432, 4, 22, "upper"),
]
WANG_MUELLER_T1 = [  # arXiv:2408.10001 Table 1
    ("WM[[54,8,6]]", 3, 9, "1+y^2+y^4", "y^3+x+x^2", 54, 8, 6, "reported"),
    ("WM[[98,6,12]]", 7, 7, "x^3+y^5+y^6", "y^2+x^3+x^5", 98, 6, 12, "reported"),
    ("WM[[126,8,10]]", 3, 21, "1+y^2+y^10", "y^3+x+x^2", 126, 8, 10, "reported"),
    ("WM[[150,16,8]]", 5, 15, "1+y^6+y^8", "y^5+x+x^4", 150, 16, 8, "reported"),
    ("WM[[162,8,14]]", 3, 27, "1+y^10+y^14", "y^12+x+x^2", 162, 8, 14, "reported"),
    ("WM[[180,8,16]]", 6, 15, "x^3+y+y^2", "y^6+x^4+x^5", 180, 8, 16, "reported"),
]
WANG_MUELLER_T2 = [  # arXiv:2408.10001 Table 2 (coprime; exponents of pi = xy)
    ("WMc[[30,4,6]]", 3, 5, (0, 1, 2), (0, 2, 7), 30, 4, 6, "reported"),
    ("WMc[[42,6,6]]", 3, 7, (0, 2, 3), (0, 2, 10), 42, 6, 6, "reported"),
    ("WMc[[70,6,8]]", 5, 7, (0, 1, 5), (0, 1, 12), 70, 6, 8, "reported"),
    ("WMc[[108,12,6]]", 2, 27, (0, 3, 42), (0, 6, 39), 108, 12, 6, "reported"),
    ("WMc[[126,12,10]]", 7, 9, (0, 1, 58), (0, 13, 41), 126, 12, 10, "reported"),
    ("WMc[[154,6,16]]", 7, 11, (0, 1, 31), (0, 19, 53), 154, 6, 16, "reported"),
]

# Weight-6 (n, k, d) reported in the literature without polynomials in our catalog, used only to
# flag "same parameters as a published code".  (n, k, d, source, note)
LITERATURE_PARAMS = [
    (84, 6, 10, "2408.10001 Tab.4", ""), (112, 6, 12, "2408.10001 Tab.4", ""),
    (126, 6, 14, "2408.10001 Tab.4", ""), (180, 8, 16, "2408.10001 Tab.1/4", ""),
    (216, 12, 12, "2511.13560 Tab.1", ""),
    (36, 8, 4, "2511.13560 Tab.3", ""), (72, 8, 8, "2511.13560 Tab.3", ""),
    (144, 8, 12, "2511.13560 Tab.3", ""), (140, 6, 14, "2511.13560 Tab.4", ""),
    (108, 16, 6, "2407.03973 Tab.1", "weight not re-checked"),
    (162, 4, 16, "2407.03973 Tab.1", ""), (162, 12, 8, "2407.03973 Tab.1", ""),
    (150, 4, 10, "2502.17052 Tab.1", "d is +-2 estimate"),
]


def ibm_table3_codes():
    return [(row, bb_code(row[1], row[2], row[3], row[4], name=row[0])) for row in IBM_TABLE3]


def all_known_codes():
    out = []
    for row in IBM_TABLE3 + IBM_SECTION4 + WANG_MUELLER_T1:
        out.append((row, bb_code(row[1], row[2], row[3], row[4], name=row[0])))
    for row in WANG_MUELLER_T2:
        out.append((row, coprime_bb_code(row[1], row[2], row[3], row[4], name=row[0])))
    return out


def known_params() -> list[tuple[int, int, int, str]]:
    """(n, k, d, source) for every literature weight-6 code we know of."""
    out = [(r[5], r[6], r[7], r[0]) for r in IBM_TABLE3 + IBM_SECTION4 + WANG_MUELLER_T1 + WANG_MUELLER_T2]
    out += [(n, k, d, f"{src} {note}".strip()) for n, k, d, src, note in LITERATURE_PARAMS]
    return out
