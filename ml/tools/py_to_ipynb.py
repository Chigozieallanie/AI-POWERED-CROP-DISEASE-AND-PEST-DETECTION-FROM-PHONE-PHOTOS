"""Build a .ipynb from a percent-format .py file ("# %%" code cells, "# %% [markdown]" text).

Usage: python ml/tools/py_to_ipynb.py ml/notebooks/01_convert_and_test_pretrained.py
"""

import json
import sys
from pathlib import Path


def cells_from(source: str) -> list[dict]:
    cells: list[dict] = []
    kind, lines = None, []

    def flush() -> None:
        while lines and not lines[-1].strip():
            lines.pop()
        if kind is None or not lines:
            return
        if kind == "markdown":
            text = [line[2:] if line.startswith("# ") else line.lstrip("#") for line in lines]
            cells.append({"cell_type": "markdown", "metadata": {}, "source": _join(text)})
        else:
            cells.append(
                {"cell_type": "code", "execution_count": None, "metadata": {}, "outputs": [], "source": _join(lines)}
            )

    for line in source.splitlines():
        if line.startswith("# %%"):
            flush()
            kind, lines = ("markdown" if "[markdown]" in line else "code"), []
        elif kind is not None:
            if not lines and not line.strip():
                continue
            lines.append(line)
    flush()
    return cells


def _join(lines: list[str]) -> list[str]:
    return [line + "\n" for line in lines[:-1]] + lines[-1:]


def main() -> None:
    source = Path(sys.argv[1])
    notebook = {
        "cells": cells_from(source.read_text()),
        "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    target = source.with_suffix(".ipynb")
    target.write_text(json.dumps(notebook, indent=1) + "\n")
    print(f"Wrote {target}")


if __name__ == "__main__":
    main()
