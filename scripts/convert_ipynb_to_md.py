#!/usr/bin/env python3
"""Convert Jupyter Notebooks (.ipynb) to clean, LLM-friendly, readable Markdown (.md).

Features:
- Pure Python stdlib (no heavy nbconvert/pandoc dependencies required)
- Strips base64 image bloat while keeping lightweight visual indicators
- Formats code cells with syntax highlighting (`python)
- Preserves readable stream, text, and markdown outputs while truncating giant dumps
- Formats error traces cleanly
- CLI interface with flexible input and output paths
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def clean_ansi(text: str) -> str:
    """Remove ANSI escape sequences (terminal colors/styles) from text."""
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def format_source(source: str | list[str]) -> str:
    """Normalize notebook cell source into a single string."""
    if isinstance(source, list):
        return "".join(source)
    return str(source or "")


def convert_ipynb_to_md(
    ipynb_path: str | Path,
    output_path: str | Path | None = None,
    include_outputs: bool = True,
    max_output_chars: int = 4000,
) -> Path:
    """Convert a .ipynb file to clean markdown format."""
    input_file = Path(ipynb_path).resolve()
    if not input_file.exists():
        raise FileNotFoundError(f"Notebook file not found: {input_file}")

    if output_path is None:
        target_file = input_file.with_suffix(".md")
    else:
        target_file = Path(output_path).resolve()

    target_file.parent.mkdir(parents=True, exist_ok=True)

    with open(input_file, "r", encoding="utf-8") as f:
        try:
            notebook = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in notebook {input_file}: {e}")

    cells = notebook.get("cells", [])
    md_lines: list[str] = []

    # Notebook title header metadata if present
    metadata = notebook.get("metadata", {})
    kernel_spec = metadata.get("kernelspec", {}).get("display_name")
    language = metadata.get("language_info", {}).get("name", "python")

    for idx, cell in enumerate(cells, 1):
        cell_type = cell.get("cell_type", "")
        source = format_source(cell.get("source", "")).strip()

        if cell_type == "markdown":
            if source:
                md_lines.append(source)
                md_lines.append("\n\n")

        elif cell_type == "code":
            if not source:
                continue

            # Add code block with appropriate language tag
            lang = language if language else "python"
            md_lines.append(f"```{lang}\n{source}\n```\n\n")

            if not include_outputs:
                continue

            outputs = cell.get("outputs", [])
            for out in outputs:
                out_type = out.get("output_type", "")

                # 1. Stream outputs (stdout / stderr)
                if out_type == "stream":
                    stream_text = clean_ansi(format_source(out.get("text", ""))).strip()
                    if stream_text:
                        if len(stream_text) > max_output_chars:
                            stream_text = (
                                stream_text[:max_output_chars]
                                + f"\n... [Output truncated: {len(stream_text)} characters total]"
                            )
                        stream_name = out.get("name", "stdout")
                        md_lines.append(f"**Output ({stream_name}):**\n```text\n{stream_text}\n```\n\n")

                # 2. Execution / Display Data
                elif out_type in ("execute_result", "display_data"):
                    data = out.get("data", {})

                    # Markdown output
                    if "text/markdown" in data:
                        md_text = format_source(data["text/markdown"]).strip()
                        if md_text:
                            md_lines.append(f"{md_text}\n\n")

                    # Plain text output
                    elif "text/plain" in data:
                        plain_text = clean_ansi(format_source(data["text/plain"])).strip()
                        if plain_text:
                            if len(plain_text) > max_output_chars:
                                plain_text = (
                                    plain_text[:max_output_chars]
                                    + f"\n... [Output truncated: {len(plain_text)} characters total]"
                                )
                            md_lines.append(f"**Output:**\n```text\n{plain_text}\n```\n\n")

                    # Image outputs (Plots / figures) - omit massive base64, insert clean marker
                    has_image = any(k.startswith("image/") for k in data.keys())
                    if has_image:
                        image_types = [k for k in data.keys() if k.startswith("image/")]
                        md_lines.append(f"*`[Visual Plot Generated: {', '.join(image_types)}]`*\n\n")

                # 3. Error / Exception traceback
                elif out_type == "error":
                    ename = out.get("ename", "Error")
                    evalue = out.get("evalue", "")
                    traceback_lines = out.get("traceback", [])
                    tb_text = clean_ansi("\n".join(traceback_lines)).strip()
                    if tb_text:
                        if len(tb_text) > max_output_chars:
                            tb_text = (
                                tb_text[:max_output_chars]
                                + f"\n... [Traceback truncated: {len(tb_text)} characters total]"
                            )
                        md_lines.append(f"**Error ({ename}: {evalue}):**\n```text\n{tb_text}\n```\n\n")

        elif cell_type == "raw":
            if source:
                md_lines.append(f"```text\n{source}\n```\n\n")

    # Combine and clean up excessive trailing empty lines
    full_text = "".join(md_lines)
    full_text = re.sub(r"\n{3,}", "\n\n", full_text).strip() + "\n"

    target_file.write_text(full_text, encoding="utf-8")
    print(f"Successfully converted '{input_file}' -> '{target_file}' ({len(full_text):,} chars)")
    return target_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Jupyter Notebook (.ipynb) to clean, LLM-friendly Markdown (.md)."
    )
    parser.add_argument("input", help="Path to input .ipynb file")
    parser.add_argument("-o", "--output", help="Path to destination .md file (default: same name with .md)")
    parser.add_argument(
        "--no-outputs",
        action="store_true",
        help="Exclude code execution outputs entirely",
    )
    parser.add_argument(
        "--max-output-chars",
        type=int,
        default=4000,
        help="Maximum characters to retain per cell output before truncating (default: 4000)",
    )

    args = parser.parse_args()

    convert_ipynb_to_md(
        ipynb_path=args.input,
        output_path=args.output,
        include_outputs=not args.no_outputs,
        max_output_chars=args.max_output_chars,
    )


if __name__ == "__main__":
    main()
