# Figures as Interfaces

An open implementation of the ideas in

> **Figures as Interfaces: Toward LLM-Native Artifacts for Scientific Discovery**
> Yifang Wang, Rui Sheng, Erzhuo Shao, Yifan Qian, Haotian Li, Nan Cao, Dashun Wang
> arXiv:2604.08491 (2026). **Paper: https://arxiv.org/abs/2604.08491**. Demo by the authors: https://www.llm-native-figure.com

This repository is not affiliated with the paper's authors. It is a teaching and research build from the Gies College of Business, University of Illinois, started for students in BADM 554 (Enterprise Database Management) and BDI 513 (Data Storytelling).

## The idea in one paragraph

A figure should not be a dead picture. Each figure here is a tuple of the rendered visualization (a Vega-Lite spec with an id on every mark), the code that produced it (SQL run on DuckDB), the data subset behind it, and metadata about when and why it was made. Because every mark maps back to rows, a person or an AI assistant can select part of a chart, get the rows behind the selection, and ask a follow-up question that becomes the next chart. Figures are stored in artifacts, a version-controlled ledger of the exploration, so any figure can be re-executed and reproduced.

## Data

The demo uses one month of NYC TLC yellow taxi trips and the taxi zone lookup, the same data the courses use, queried locally with DuckDB. A deterministic sample is committed so the tests and demo run offline; the full month is read from a local parquet file if present.

## Formats

Figures and artifacts are plain JSON: the Vega-Lite spec, the SQL, the rows, and metadata. They load in a Python notebook (Colab), in a Wolfram notebook, or anywhere else that can parse JSON and render Vega-Lite. The Python package here is the reference implementation, not a requirement for reading artifacts. See `docs/` for the schema and an example.

## Package layout and run

Python 3.12 or newer (see `requires-python` in `pyproject.toml`; 3.10+ tooling is fine for editing). Runtime dependencies are pinned: `duckdb==1.3.2` and `vl-convert-python==1.8.0`. PNG rendering via `vl-convert` is optional for consumers that only need the Vega-Lite JSON; the demo exports PNGs by default.

```
src/figureflow/   package (actions, dataset, model, pipeline, planner, cli)
data/             50,000-trip sample parquet + zone lookup (bundled in the wheel)
docs/             plan, artifact format, JSON Schema, verification notes
examples/         committed artifact, Colab notebook
```

```sh
mkdir -p .scratch .cache
UV_CACHE_DIR="$PWD/.cache/uv" TMPDIR="$PWD/.scratch" uv sync --extra test --locked
.venv/bin/figureflow demo --output demo-output
.venv/bin/figureflow replay demo-output/artifact.json
.venv/bin/python -m pytest -q
```

**Size policy:** `examples/taxi-artifact.json` stays under 2 MB. Full re-execution reads `data/yellow_tripdata_sample.parquet` via `dataset_path`; the artifact inlines at most 200 mark-referenced rows for JSON-only selection. PNGs are referenced by `png_path`, not base64.

Colab: [`examples/taxi_figures.ipynb`](examples/taxi_figures.ipynb).

## Status

Early. Read `docs/plan.md` for the architecture and the minimal slice. Issues labelled `good first issue` are the entry points for contributors. See `CONTRIBUTING.md`.

## License

CC BY-NC-SA 4.0. The paper itself is the authors' work; read it at the arXiv link above.
