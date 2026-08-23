# Office2RAGKnowledge — CLI 配布用イメージ
#
# 本アプリは常駐サービスではなく **CLI ツール** である。したがって本イメージは
# 「起動して待ち受ける」のではなく、「入力ディレクトリを変換して終了する」
# 使い方を想定している (docker compose run で都度実行する)。
#
# 外部バイナリ (LibreOffice・OCRエンジン) を必要としないため、slim ベースで足りる
# (REQ-NF-019)。

FROM python:3.12-slim AS builder

WORKDIR /build
COPY app/pyproject.toml app/README.md ./
COPY app/src ./src

# wheel を作ってから実行イメージへ渡す。ビルド用の道具を実行イメージに残さない。
RUN pip install --no-cache-dir build \
    && python -m build --wheel --outdir /dist


FROM python:3.12-slim

LABEL org.opencontainers.image.title="Office2RAGKnowledge" \
      org.opencontainers.image.description="Office文書をRAG向けMarkdownに変換するCLI" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.licenses="MIT"

# 変換処理は外部通信を一切行わない (REQ-NF-010)。
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONIOENCODING=utf-8

COPY --from=builder /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm -f /tmp/*.whl

# root で動かさない。出力ファイルの所有者を揃えるため UID を指定できるようにする。
ARG UID=1000
RUN useradd --create-home --uid ${UID} app
USER app

WORKDIR /work

# 既定は変換のヘルプ。実際の変換は docker compose run で引数を渡す。
ENTRYPOINT ["office2rag"]
CMD ["--help"]
