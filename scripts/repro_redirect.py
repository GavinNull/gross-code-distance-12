"""Run an experiment / audit script unchanged, but with its hard-coded results directories redirected.

Several E-017/E-019/E-020 scripts write to fixed paths (results/E-019-morphing-family, results/E-017-audit, ...).
For a reproduction from a clean directory, this runner rewrites those path strings at load time, both in the target
script and in every project module it imports (source text substitution; the files on disk are not touched).

    REPRO_MAP="results/E-019-morphing-family=results/reproduce_theorems/morph/e019;..." \
        uv run python scripts/repro_redirect.py -m search.experiments.e019.instance bb72_x_paper Z 4
    REPRO_MAP=... uv run python scripts/repro_redirect.py research/audits/.../c3_rounds.py x repo Z 4

Old strings are matched literally; give the new directory relative to the repository root (it is also substituted
inside absolute paths such as /Users/.../qec-ai-search/results/E-017-audit) and run from the repository root.
"""
from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAP = [tuple(p.split("=", 1)) for p in os.environ.get("REPRO_MAP", "").split(";") if "=" in p]
for _, new in MAP:
    os.makedirs(os.path.join(ROOT, new), exist_ok=True)


def patch(src: str) -> str:
    for old, new in MAP:
        src = src.replace(old, new)
    return src


class Loader(importlib.machinery.SourceFileLoader):
    def get_data(self, path):
        data = super().get_data(path)
        if path.endswith(".py"):
            return patch(data.decode()).encode()
        return data

    def path_stats(self, path):          # force recompilation (no stale .pyc of the unpatched source)
        raise OSError


class Finder(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path, target=None):
        spec = importlib.machinery.PathFinder.find_spec(name, path)
        if spec is None or not spec.origin or not spec.origin.endswith(".py"):
            return spec
        if not os.path.abspath(spec.origin).startswith(ROOT + os.sep) or "/.venv/" in spec.origin:
            return spec
        spec.loader = Loader(name, spec.origin)
        return spec


def main():
    sys.meta_path.insert(0, Finder())
    sys.dont_write_bytecode = True
    args = sys.argv[1:]
    if args[0] == "-m":
        import runpy
        sys.argv = [args[1]] + args[2:]
        if ROOT not in sys.path:
            sys.path.insert(0, ROOT)
        runpy.run_module(args[1], run_name="__main__", alter_sys=True)
    else:
        path = os.path.abspath(args[0])
        sys.argv = [path] + args[1:]
        sys.path.insert(0, os.path.dirname(path))
        code = compile(patch(open(path).read()), path, "exec")
        exec(code, {"__name__": "__main__", "__file__": path, "__builtins__": __builtins__})


if __name__ == "__main__":
    main()
