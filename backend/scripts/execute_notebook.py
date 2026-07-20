"""nbconvert 없이 Jupyter 노트북을 실행하고 출력까지 저장한다."""

from __future__ import annotations

import argparse
from pathlib import Path

import nbformat
from nbclient import NotebookClient


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--kernel", default=None)
    args = parser.parse_args()

    source = args.input.resolve()
    destination = args.output.resolve()
    notebook = nbformat.read(source, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=args.timeout,
        kernel_name=(
            args.kernel
            or notebook.metadata.get("kernelspec", {}).get("name", "python3")
        ),
        resources={"metadata": {"path": str(source.parent)}},
    )
    client.execute()
    destination.parent.mkdir(parents=True, exist_ok=True)
    nbformat.write(notebook, destination)
    print(destination)


if __name__ == "__main__":
    main()
