# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status

This repository is currently a scaffold: it contains only `README.md` and `LICENSE` (MIT, © 2026 HONDOH Atsushi). There is no source code, build tooling, dependency manifest, or test suite yet.

## Purpose

Office2RAGKnowledge converts Office documents (Word/Excel/PowerPoint) into Markdown intended for consumption by AI RAG pipelines. Design decisions should be driven by that target: the output is chunked and embedded, not read directly by humans, so structural fidelity (headings, tables, lists, sheet/slide boundaries) matters more than visual fidelity.

## Guidance for the first implementation

Once code lands, replace this section with the real build/test/lint commands and the actual module layout. Until then:

- No language or framework has been chosen. Ask the user before assuming one — do not scaffold a stack unilaterally.
- Record the chosen toolchain's commands (build, run, lint, single-test invocation) here as soon as they exist.
