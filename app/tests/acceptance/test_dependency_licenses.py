"""A007 受け入れテスト: 実行時依存のライセンス (REQ-NF-021。※CR-003)。

導入した環境のパッケージのメタデータから、``office2ragknowledge`` の実行時依存を
推移的に辿り、MIT と両立しないライセンス (AGPL・GPL) が無いことを確認する。
開発時依存 (extra の ``dev``) は検査の対象にしない。
"""

from __future__ import annotations

import re
from importlib import metadata
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from typer.testing import CliRunner

from office2ragknowledge import convert_bytes
from office2ragknowledge.cli.main import app
from tests.helpers.make_pdf import Elem, Page, Text, build_pdf

ROOT = "office2ragknowledge"
_COPYLEFT = re.compile(r"\b(A?GPL|LGPL|Affero)\b|GNU (Affero |Lesser )?General Public", re.I)


def _runtime_dependencies() -> dict[str, metadata.Distribution]:
    """実行時依存 (推移的) を、正規化した名前 → Distribution で返す。"""
    found: dict[str, metadata.Distribution] = {}
    pending = [ROOT]
    while pending:
        name = canonicalize_name(pending.pop())
        if name in found:
            continue
        dist = metadata.distribution(name)
        found[name] = dist
        for raw in dist.requires or []:
            req = Requirement(raw)
            # extra の指定がある依存 (dev 等) は実行時依存ではない
            if req.marker is not None and not req.marker.evaluate({"extra": ""}):
                continue
            pending.append(req.name)
    del found[canonicalize_name(ROOT)]
    return found


def _license_texts(dist: metadata.Distribution) -> list[str]:
    meta = dist.metadata
    texts = [meta.get("License-Expression") or "", meta.get("License") or ""]
    texts += [c for c in meta.get_all("Classifier") or [] if c.startswith("License ::")]
    return [t for t in texts if t.strip()]


# 1: AGPL・GPL が含まれない
def test_1_no_copyleft_in_runtime_dependencies() -> None:
    offenders = {}
    for name, dist in sorted(_runtime_dependencies().items()):
        hits = [t[:80] for t in _license_texts(dist) if _COPYLEFT.search(t)]
        if hits:
            offenders[name] = hits
    assert offenders == {}, f"MIT と両立しないライセンスの依存: {offenders}"


# 2: pdfminer.six が入り、PyMuPDF が入らない
def test_2_pdf_library_is_pdfminer() -> None:
    deps = _runtime_dependencies()
    assert "pdfminer-six" in deps
    assert "pymupdf" not in deps
    assert "fitz" not in deps


# 3: ライセンス情報の欠落が無い (確認できないものを合格扱いにしない)
def test_3_every_dependency_declares_a_license() -> None:
    missing = sorted(
        name for name, dist in _runtime_dependencies().items() if not _license_texts(dist)
    )
    assert missing == [], f"ライセンス情報の無い依存: {missing}"


# 4: バージョン画面
def test_4_version_screen() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert "pdfminer.six" in result.output
    assert "PyMuPDF" not in result.output


# 5: Docker イメージのラベル
def test_5_docker_label_is_mit() -> None:
    dockerfile = Path(__file__).resolve().parents[3] / "deploy" / "Dockerfile"
    text = dockerfile.read_text(encoding="utf-8")
    assert 'org.opencontainers.image.licenses="MIT"' in text


# 6: MCR 形式のタグ付き PDF がタグ付きとして変換される
def test_6_mcr_form_is_tagged() -> None:
    data = build_pdf(
        [Page(items=[Text(50, 780, "第1章", 18, mcid=0), Text(50, 740, "本文です。", 12, mcid=1)])],
        Elem("Document", [Elem("H1", [(0, 0)]), Elem("P", [(0, 1)])]),
        mcr=True,
    )
    md = convert_bytes(data, "mcr.pdf").markdown
    assert 'pdf_structure: "tagged"' in md
    assert "\n# 第1章\n" in md


def test_detector_catches_copyleft_strings() -> None:
    """検出の正規表現が、実在のコピーレフトの表記を捕らえることを確かめる。"""
    for text in (
        "Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License",  # PyMuPDF
        "AGPL-3.0-only",
        "GPL-2.0-or-later",
        "LGPL-3.0",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
    ):
        assert _COPYLEFT.search(text), text
    for text in ("MIT", "BSD-3-Clause", "Apache-2.0 OR BSD-3-Clause", "PSF-2.0", "MIT-CMU"):
        assert not _COPYLEFT.search(text), text
