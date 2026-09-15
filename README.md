# Figures as Interfaces / FigureFlow

An open implementation of **Figures as Interfaces: Toward LLM-Native Artifacts for Scientific Discovery**, by Yifang Wang, Rui Sheng, Erzhuo Shao, Yifan Qian, Haotian Li, Nan Cao, and Dashun Wang. [Paper: arXiv:2604.08491](https://arxiv.org/abs/2604.08491). [Authors' demo](https://www.llm-native-figure.com).

This repository is not affiliated with the paper's authors. It is a teaching and research build from the Gies College of Business, University of Illinois, for BADM 554 (Enterprise Database Management) and BDI 513 (Data Storytelling).

A small, working implementation of *Figures as Interfaces*: figures preserve their data, SQL, Vega-Lite specification, source-row mappings and exploration history. DuckDB runs the analysis locally. A deterministic planner makes the demo work offline without an API key.

The teaching example uses actual NYC yellow taxi trips for BADM 554 students also taking BDI 513 Data Storytelling. A committed 50,000-trip sample and zone lookup support both installation and offline use. It is not a full-month count. The complete original Parquet is not committed.

## Install and run

From this repository, with Python 3.12 or newer and `uv` installed:

```sh
mkdir -p .scratch .cache
UV_CACHE_DIR="$PWD/.cache/uv" TMPDIR="$PWD/.scratch" uv sync --extra test --locked
.venv/bin/figureflow demo --output demo-output
.venv/bin/figureflow replay demo-output/artifact.json
.venv/bin/python -m pytest -q
```

Alternatively, create `.venv` with `python3 -m venv .venv` and install with `.venv/bin/python -m pip install '.[test]'`. Direct dependencies are pinned in `pyproject.toml`; `uv.lock` also pins resolved dependencies. Installation may download packages. Tests and the demo make no network calls.

## What the demo shows

1. Plot Manhattan pickup counts for all 24 hours of the day, aggregated across the January sample.
2. Select evening hours 17 through 20 inclusive and ask to rank pickup zones within that window and borough.
3. Select morning hours 7 through 10 inclusive. The same linked chart updates through its stored coordination rule, without another planner call.
4. Save all three figure versions and replay their stored SQL against the embedded input snapshot.

The sample includes **44,816 Manhattan trips**. Evening selects **11,738** trips, led by **Midtown Center (868)**. Morning selects **7,157** trips, led by **Upper East Side North (538)**. Both rankings remain available in the saved history. These are sample observations, not population estimates.

`demo-output/` contains a portable `artifact.json`, three PNG charts, three Vega-Lite specs, three SQL files and a transcript. The CLI simulates a brush by supplying the selected marks' ids; a live browser interaction is the next slice.

## Notebooks and language-neutral artifacts

- [Colab notebook](examples/taxi_figures.ipynb): installs the repository, runs the demo, renders saved specs, and resolves selections using plain JSON.
- [Committed demo artifact](examples/taxi-artifact.json): the full demo history, including the 50,000-row analytical snapshot. It is intentionally self-contained and larger than the compressed Parquet sample.
- [Format guide](docs/artifact-format.md) and [JSON Schema](docs/artifact.schema.json): describe figures, data types, mark mappings, SQL and the version graph.
- [Plan](docs/plan.md): paper terminology, architecture, scope and consumer requirements.
- [Verification record](docs/verification.md): red and green test counts and replay checks.

To distribute this revision of the notebook and package to Colab students before publication, provide a repository ZIP. After committing your desired revision:

```sh
git archive --format=zip --prefix=figures-as-interfaces/ HEAD -o .scratch/figures-as-interfaces.zip
```

Open the notebook in Colab and run its setup cell, uploading that ZIP if the repository has not already been cloned. Wolfram users can parse the same JSON and render its Vega-Lite specification without importing Python. A Wolfram loader is outside this pass. DuckDB local is for fast iteration; the student-facing deployment engine remains a later decision.

## Package layout

`src/figureflow/` contains the records and ledger (`model.py`), DuckDB data preparation (`dataset.py`), action compiler and renderer (`actions.py`), planner interface (`planner.py`), execution/coordination/replay (`pipeline.py`), and CLI (`cli.py`). Tests live in `tests/`, committed inputs in `data/`, and notebook/example output in `examples/`.

## Python API

```python
from figureflow import Pipeline, Mapping, RuleBasedPlanner

pipeline = Pipeline(planner=RuleBasedPlanner())
prompt = 'Plot hourly trip counts for Manhattan in January 2024'
figure = pipeline.execute(pipeline.planner.plan(prompt), prompt)
ids = [row['mark_id'] for row in figure.V['spec']['data']['values']
       if 17 <= row['pickup_hour'] <= 20]
selection = Mapping.select(figure, ids)
ranking = pipeline.follow_up(figure.M['figure_id'], ids,
                            'Rank pickup zones by trip count within the selected hours')
pipeline.artifact.save('demo-output/my-artifact.json')
```

`Pipeline.execute(..., parent_version='a0001')` creates a branch from a prior state. Empty selections, stale ids, unsupported actions and unmatched filters fail without appending a partial history entry. Original row ids refer to the full Parquet's zero-based row offset, preserved in the sample as `source_row_number`.

## Optional full data and planner

To prepare the sample again, follow [data/README.md](data/README.md). `Pipeline(full_data=True)` reads the local file named by `FIGUREFLOW_TAXI_PARQUET` and reports a clear error if absent. The default never needs that variable or the course folder. Full-data artifacts can be large because this minimal implementation embeds rows.

`FIGUREFLOW_PLANNER=your_module:factory` enables an optional provider hook for API use. The factory returns an object with `plan(instruction, selection=None) -> list[dict]`. It may call your chosen LLM and returns only constrained actions, which the pipeline validates. No provider SDK or key is required; the CLI teaching demo explicitly uses the offline stub. Provider adapters are installed/configured separately and own their authentication and network calls.

The rule-based stub handles the documented hourly-count and zone-ranking prompts. It is not a general language model. The implementation covers filtering, grouping, counting, deterministic sorting, chart specification and direct coordination. It does not implement the full paper's multi-agent planning/evaluation, arbitrary modeling, science-of-science database, hybrid web UI, transitive links or collaborative editing. Rendering uses [Vega's vl-convert](https://github.com/vega/vl-convert), with inline data and external URL access disabled.

## Contributing and license

See [CONTRIBUTING.md](CONTRIBUTING.md). Issues labelled `good first issue` are entry points for contributors. Code is MIT licensed. The paper remains the authors' work; read it at the arXiv link above.
