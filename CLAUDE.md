# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Purpose

Office2RAGKnowledge converts Office documents (Word/Excel/PowerPoint) and PDF into Markdown for AI RAG pipelines (chunking + vector DB). Output is read by chunkers and embedding models, not humans: **structural fidelity** (headings, tables, lists, sheet/slide boundaries, text inside shapes) matters more than visual fidelity. Image binaries are a secondary feature (off by default); text extraction is the goal.

Two differentiators drive the design: text inside auto-shapes/SmartArt is never dropped (no OCR — text is read from the file), and Excel is always emitted in **both** "table" (`.table.md`) and "grid / 方眼紙" (`.grid.md`) modes without guessing which one applies.

## Layout

- `app/` — the Python package (`src/office2ragknowledge/`) and tests (`tests/`). Module map: `app/INDEX.md`.
- `docs/` — spec-driven design docs (P001 requirements … P302 delivery), `ADR.md`, `ArchitectureHandbook.md`, test records, change requests (`CR.md`, `P901-cr-direction/`, `P903-cr-records/`). Repo-wide index: `INDEX.md`.
- `deploy/` — `Dockerfile` / `compose.yml` (CLI image; run with `docker compose run --rm convert ...`, not `up`).
- `.claude/skills/spec-driven-dev/` — the workflow this repo follows (see "Workflow").

**Read before changing code:** `docs/ArchitectureHandbook.md` §4 (verified pitfalls) and §9 (accepted constraints), and `docs/ADR.md`.

## Commands

Run from `app/`. Python ≥ 3.11 (verified on 3.11, 3.12; originally 3.13/3.14 on Windows).

```bash
# Environment. NOTE: app/.venv is a Windows venv and cannot be used from WSL/Linux;
# create a separate venv there, e.g.:
uv venv /path/to/venv --python 3.12 && VIRTUAL_ENV=/path/to/venv uv pip install -e '.[dev]'
# (or: python -m venv .venv && pip install -e ".[dev]")

pytest -q                                   # full suite (perf tests excluded by default)
pytest tests/unit/test_pdf_layout.py::test_two_columns_left_then_right   # single test
pytest tests/unit -k pdf                    # subset by keyword
pytest -m perf -s                           # performance tests (4)
pytest --cov=office2ragknowledge            # coverage (target ≥ 80%)

ruff check src tests && ruff format --check src tests && mypy src   # quality gates (also enforced by tests/acceptance/test_quality_gates.py)

uv build --wheel --sdist                    # → app/dist/ (git-ignored)
cd ../deploy && docker compose build        # image office2ragknowledge:<version>
```

The suite must pass **twice in a row** (tests isolate output via `tmp_path`). After changing dependencies, verify in a **fresh** venv — a stale venv once hid a missing `pypdf[crypto]` dev dependency.

## Architecture

Three layers: **parser → intermediate representation (`models/`) → renderer**.

```
cli/ → convert.py / batch.py / inspection.py / config.py
          ↓
     parsers/ → ooxml/ (OOXML) , pdf/ (PDF)
          ↓
      models/ ← render/
```

- `models/` depends on nothing; `render/` depends only on `models/`; `parsers/` never imports `render/`. Renderer tests build `Document` objects directly.
- Excel: one parse (`Sheet` keeps merged ranges unexpanded) feeds **two renderers** (`excel_table.py` duplicates merged values, `excel_grid.py` does not). Never parse twice.
- OOXML access only via `ooxml/zip_reader.py` (`SafeZipReader`: zip-bomb / path-traversal checks) and `ooxml/xml_utils.py` (XXE disabled). `ooxml/shapes.py` follows `mc:Choice` only (ADR-003).
- PDF: `detect_format` recognizes `%PDF-`; `convert.py` calls `parsers/pdf.py` (`PdfParser`) without `SafeZipReader`. **Only `pdf/backend.py` may import the PDF library (pdfminer.six)**; everything else uses the library-neutral types in `pdf/model.py`. Tagged PDFs map the structure tree (ordered by `/K`, `pdf/structure.py`); untagged PDFs go through `pdf/layout.py` (header/footer removal, column detection, figure regions) without inferring headings (ADR-013/014).

## Rules that are easy to break

- **License: the project is MIT and must stay MIT.** Runtime dependencies (including transitive ones) must be non-copyleft (REQ-NF-021); `tests/acceptance/test_dependency_licenses.py` enforces this. PyMuPDF (AGPL) was removed for this reason (ADR-015; old ADR-012 in `docs/ADR_master.md`). Check licenses before adding any dependency.
- Determinism (REQ-NF-018): same input + options → identical Markdown except `converted_at`. Don't let output order depend on `set`/`dict` iteration; current time is taken only in `convert.py`.
- Never log document text (cell values, paragraphs, shape text, title/author) — paths, counts, sheet names and error codes only (REQ-NF-014). Library loggers/warnings (pdfminer) are silenced in `pdf/backend.py`.
- Markdown escaping happens only in the renderer, and only for line-leading structural characters (ADR-010). Parsers store raw text.
- Files are UTF-8, **LF** line endings (the repo is LF; edits from Windows have introduced CRLF before — normalize before committing). CLI messages are Japanese.
- Error codes/messages live in `errors.py` (`ERROR_CATALOG`); external behavior is specified in `docs/P002-frontend-spec.md`.

## Workflow

Development follows the spec-driven-dev skill (`.claude/skills/spec-driven-dev/SKILL.md`). Changes after delivery go through a **CR**: P901 (write `docs/P901-cr-direction/CR-NNN.md` + row in `docs/CR.md`) → P902 (update `docs/P001-requirement.md`, keeping a dated backup) → P903 (scope record, then re-run P002…P302 with `docs/.inprogress` set to `P903:P0NN`) → P904 (map each expected behavior to a test) → P905 (ADR check). Mark assumed content with `★FIXME★` and deliberate trade-offs with `★ACCEPTED★` (with what was considered, why rejected, residual risk) next to the statement itself.

Current state: version **1.1.0**, CR-001〜CR-003 completed, release verdict OK (`docs/P302-deliver.md` §11).
