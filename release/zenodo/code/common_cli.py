"""Small helpers shared by the command-line scripts."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from gross12.code import load_code                    # noqa: E402
from gross12.paths import CIRCUIT_FILES               # noqa: E402
from gross12.schedule import load_schedule            # noqa: E402


def parse_range(s: str) -> list[int]:
    """'1-3,5,7-8' -> [1, 2, 3, 5, 7, 8]"""
    out = []
    for part in s.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def circuit(name: str):
    return load_schedule(CIRCUIT_FILES[name])


class Verdict:
    def __init__(self):
        self.bad = 0

    def __call__(self, ok: bool, msg: str):
        print(("PASS  " if ok else "FAIL  ") + msg, flush=True)
        self.bad |= not ok

    def exit(self):
        sys.exit(int(self.bad))
