"""U005-T4 の単体テスト: CLI オプションの検証 (V-01〜V-52)。"""

from __future__ import annotations

from pathlib import Path

import pytest

from office2ragknowledge.cli.options import build_config, resolve_targets
from office2ragknowledge.errors import Office2RagError
from office2ragknowledge.models import ExcelModes, ImageMode, OnExists, ShapeStyle
from tests.helpers.make_office import make_docx, make_xlsx

#: CLI のオプションはすべて既定 None (「利用者が指定しなかった」の意)。
#: 既定値は load_config が返す Config が持つ (REQ-F-098)。
BASE: dict[str, object] = dict(
    inputs=[],
    output=None,
    recursive=False,
    on_exists=None,
    use_stdout=False,
    excel_modes=None,
    grid_separator=None,
    table_regions=None,
    max_table_regions=None,
    formulas=None,
    max_rows=None,
    images=None,
    shapes=None,
    shape_style=None,
    include_hidden=None,
    notes=None,
    headers_footers=None,
    comments=None,
    jobs=None,
    config_path=None,
    quiet=False,
    verbose=False,
    log_file=None,
    log_format=None,
    front_matter=None,
)


def build(**over: object):  # type: ignore[no-untyped-def]
    return build_config(**{**BASE, **over})  # type: ignore[arg-type]


def code_of(exc: Office2RagError) -> str:
    return exc.code


# ケース1: 既定値
def test_defaults() -> None:
    cfg, warnings = build()
    assert cfg.convert.excel.modes is ExcelModes.BOTH
    assert cfg.convert.excel.grid_separator == ""
    assert cfg.convert.excel.max_table_regions == 100
    assert cfg.convert.excel.max_rows == 10_000
    assert cfg.convert.images is ImageMode.NONE
    assert cfg.convert.shape_style is ShapeStyle.QUOTE
    assert cfg.batch.on_exists is OnExists.SKIP
    assert warnings == []


# ケース2/3/4: パスの検証
def test_no_inputs() -> None:
    with pytest.raises(Office2RagError) as exc:
        resolve_targets([], recursive=False, use_stdout=False, modes=ExcelModes.BOTH)
    assert code_of(exc.value) == "E-010"


def test_missing_path(tmp_path: Path) -> None:
    with pytest.raises(Office2RagError) as exc:
        resolve_targets(
            [tmp_path / "nope"], recursive=False, use_stdout=False, modes=ExcelModes.BOTH
        )
    assert code_of(exc.value) == "E-001"


def test_zero_targets(tmp_path: Path) -> None:
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")
    with pytest.raises(Office2RagError) as exc:
        resolve_targets([tmp_path], recursive=False, use_stdout=False, modes=ExcelModes.BOTH)
    assert code_of(exc.value) == "E-011"


# ケース5: --output と --stdout の併用
def test_output_and_stdout_conflict(tmp_path: Path) -> None:
    with pytest.raises(Office2RagError) as exc:
        build(use_stdout=True, output=tmp_path)
    assert code_of(exc.value) == "E-012"


# ケース6: --stdout で対象2件以上
def test_stdout_with_multiple_targets(tmp_path: Path) -> None:
    make_docx(tmp_path / "a.docx", [("p", "1")])
    make_docx(tmp_path / "b.docx", [("p", "2")])
    with pytest.raises(Office2RagError) as exc:
        resolve_targets([tmp_path], recursive=False, use_stdout=True, modes=ExcelModes.BOTH)
    assert code_of(exc.value) == "E-014"


# ケース7/8: --stdout + Excel
def test_stdout_excel_both_is_error(tmp_path: Path) -> None:
    path = make_xlsx(tmp_path / "a.xlsx", {"S": [["x"]]})
    with pytest.raises(Office2RagError) as exc:
        resolve_targets([path], recursive=False, use_stdout=True, modes=ExcelModes.BOTH)
    assert code_of(exc.value) == "E-017"


def test_stdout_excel_single_mode_ok(tmp_path: Path) -> None:
    path = make_xlsx(tmp_path / "a.xlsx", {"S": [["x"]]})
    targets, _ = resolve_targets([path], recursive=False, use_stdout=True, modes=ExcelModes.TABLE)
    assert len(targets) == 1


# ケース9: 列挙値
def test_invalid_enum_values() -> None:
    for key, value in (
        ("excel_modes", "invalid"),
        ("images", "invalid"),
        ("shape_style", "invalid"),
        ("on_exists", "invalid"),
        ("log_format", "invalid"),
    ):
        with pytest.raises(Office2RagError) as exc:
            build(**{key: value})
        assert code_of(exc.value) == "E-013", key


# ケース10/11: --grid-separator
def test_grid_separator_newline() -> None:
    with pytest.raises(Office2RagError) as exc:
        build(grid_separator="a\nb")
    assert code_of(exc.value) == "E-018"


def test_grid_separator_too_long() -> None:
    with pytest.raises(Office2RagError) as exc:
        build(grid_separator="123456789")
    assert code_of(exc.value) == "E-018"


# ケース12: --max-table-regions の範囲
def test_max_table_regions_range() -> None:
    with pytest.raises(Office2RagError) as exc:
        build(max_table_regions=0)
    assert code_of(exc.value) == "E-019"
    assert build(max_table_regions=1)[0].convert.excel.max_table_regions == 1
    assert build(max_table_regions=10_000)[0].convert.excel.max_table_regions == 10_000


# ケース13: --max-rows
def test_max_rows_range() -> None:
    assert build(max_rows=0)[0].convert.excel.max_rows == 0
    with pytest.raises(Office2RagError) as exc:
        build(max_rows=-1)
    assert code_of(exc.value) == "E-015"


# ケース14: --jobs
def test_jobs_range() -> None:
    with pytest.raises(Office2RagError) as exc:
        build(jobs=0)
    assert code_of(exc.value) == "E-016"
    with pytest.raises(Office2RagError):
        build(jobs=65)
    assert build(jobs=1)[0].batch.jobs == 1
    assert build(jobs=64)[0].batch.jobs == 64


# ケース15: -q と -v の併用
def test_quiet_and_verbose_conflict() -> None:
    with pytest.raises(Office2RagError) as exc:
        build(quiet=True, verbose=True)
    assert code_of(exc.value) == "E-012"


# ケース16: --excel-modes grid + --formulas は警告のみ
def test_grid_with_formulas_warns() -> None:
    cfg, warnings = build(excel_modes="grid", formulas=True)
    assert any("--formulas" in w for w in warnings)
    assert cfg.convert.excel.formulas is True


# ケース17: -r でディレクトリ入力なしは警告のみ
def test_recursive_without_directory_warns(tmp_path: Path) -> None:
    path = make_docx(tmp_path / "a.docx", [("p", "本文")])
    _, warnings = build(inputs=[path], recursive=True)
    assert any("-r" in w for w in warnings)


# ケース18/19: 設定ファイルとの優先順位
def test_cli_overrides_config(tmp_path: Path) -> None:
    config = tmp_path / "office2rag.toml"
    config.write_text('[excel]\nmodes = "table"\nmax_rows = 500\n', encoding="utf-8")
    cfg, _ = build(config_path=config, excel_modes="grid")
    assert cfg.convert.excel.modes is ExcelModes.GRID, "CLI 引数が優先されていません"
    assert cfg.convert.excel.max_rows == 500, "設定ファイルの値が反映されていません"


def test_config_error_is_reported(tmp_path: Path) -> None:
    config = tmp_path / "office2rag.toml"
    config.write_text("[excel]\nunknown = 1\n", encoding="utf-8")
    with pytest.raises(Office2RagError) as exc:
        build(config_path=config)
    assert code_of(exc.value) == "E-006"


# ケース20: 検証順序 — 値不正 (段階1) がパス不存在 (段階3) より先
def test_validation_order(tmp_path: Path) -> None:
    with pytest.raises(Office2RagError) as exc:
        build(inputs=[tmp_path / "nope"], excel_modes="invalid")
    assert code_of(exc.value) == "E-013", "検証順序が仕様と異なります"


# ============================================================
# F001: 設定ファイルの優先順位 (REQ-F-098)
# ============================================================


def write_config(tmp_path: Path, *lines: str) -> Path:
    """TOML の各行を渡して設定ファイルを作る。"""
    path = tmp_path / "cfg.toml"
    text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def test_config_modes_applies_when_cli_omits_it(tmp_path: Path) -> None:
    """設定ファイルの excel.modes が、CLI 未指定時に反映される。"""
    config = write_config(tmp_path, "[excel]", 'modes = "table"')
    cfg, _ = build(config_path=config)
    assert cfg.convert.excel.modes is ExcelModes.TABLE


def test_config_applies_to_other_enums(tmp_path: Path) -> None:
    config = write_config(
        tmp_path,
        "[convert]",
        'images = "extract"',
        'shape_style = "plain"',
        'on_exists = "overwrite"',
    )
    cfg, _ = build(config_path=config)
    assert cfg.convert.images is ImageMode.EXTRACT
    assert cfg.convert.shape_style is ShapeStyle.PLAIN
    assert cfg.batch.on_exists is OnExists.OVERWRITE


def test_cli_negative_flag_overrides_config_true(tmp_path: Path) -> None:
    """設定ファイルで true にした真偽値を、CLI の否定フラグで false に戻せる。"""
    config = write_config(tmp_path, "[convert]", "include_hidden = true", "comments = true")
    from_config, _ = build(config_path=config)
    assert from_config.convert.include_hidden is True
    assert from_config.convert.comments is True

    overridden, _ = build(config_path=config, include_hidden=False, comments=False)
    assert overridden.convert.include_hidden is False
    assert overridden.convert.comments is False


def test_cli_value_beats_config(tmp_path: Path) -> None:
    config = write_config(tmp_path, "[excel]", 'modes = "table"', "max_rows = 500")
    cfg, _ = build(config_path=config, excel_modes="grid")
    assert cfg.convert.excel.modes is ExcelModes.GRID, "CLI 引数が優先されていません"
    assert cfg.convert.excel.max_rows == 500, "CLI 未指定の項目まで上書きされています"


def test_defaults_apply_when_neither_specifies(tmp_path: Path) -> None:
    config = write_config(tmp_path, "[excel]", "max_rows = 500")
    cfg, _ = build(config_path=config)
    assert cfg.convert.excel.modes is ExcelModes.BOTH  # 既定値
    assert cfg.convert.excel.max_rows == 500  # 設定ファイル


def test_config_log_format(tmp_path: Path) -> None:
    config = write_config(tmp_path, "[log]", 'format = "json"')
    cfg, _ = build(config_path=config)
    assert cfg.log.format == "json"
    overridden, _ = build(config_path=config, log_format="text")
    assert overridden.log.format == "text"


# ============================================================
# F002: resolve_targets がスキップも返す
# ============================================================


def test_resolve_targets_returns_skipped(tmp_path: Path) -> None:
    make_docx(tmp_path / "a.docx", [("p", "本文")])
    (tmp_path / "old.doc").write_bytes(b"legacy")
    (tmp_path / "memo.txt").write_text("x", encoding="utf-8")
    targets, skipped = resolve_targets(
        [tmp_path], recursive=False, use_stdout=False, modes=ExcelModes.BOTH
    )
    assert [p.name for p in targets] == ["a.docx"]
    assert sorted(p.name for p, _ in skipped) == ["memo.txt", "old.doc"]
