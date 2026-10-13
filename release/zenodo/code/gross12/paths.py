"""Locations of the data files (relative to the package root, i.e. the directory that contains code/ and data/)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
CODE_JSON = DATA / "code" / "gross_code.json"
CIRCUITS = DATA / "circuits"
EXT = DATA / "extended_code"
LOGICALS = DATA / "logicals"
WITNESSES = ROOT / "witnesses"
CERTIFICATES = ROOT / "certificates"

CIRCUIT_FILES = {
    "A": CIRCUITS / "circuit_A.json",
    "B": CIRCUITS / "circuit_B.json",
    "C": CIRCUITS / "circuit_C.json",
    "fig12": CIRCUITS / "fig12.json",
}
for _k in range(4):
    CIRCUIT_FILES[f"fig12_retiming_{_k}"] = CIRCUITS / f"fig12_retiming_{_k}.json"
