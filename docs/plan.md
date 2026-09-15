# Figures as Interfaces Implementation Plan

**Goal:** Implement and test the paper's Figure 1 loop as a small, offline Python project.
**Architecture:** `figureflow` compiles validated action sequences into deterministic pandas code, renders Vega-Lite, and records immutable figures in a JSON artifact ledger. A replaceable planner translates language; a mapping translates selected marks into source rows and explicit follow-up constraints.
**Source:** `sources/figures-as-interfaces.txt`, read in full, especially Section 3.1 (lines 175-329) and Section 5 (lines 596-790). This is a minimal implementation of the representation and mappings, not a reproduction of Nexus or its evaluation results.
**Execution:** Complete Stages A, B, C inline, with failing tests before implementation and explicit-path commits after each stage, as requested.

## Constraints and completion criteria

- Python 3.12+, repository-local `.venv`, exact direct dependency pins in `pyproject.toml`, resolved dependency lock.
- Scratch, test temporary directories, caches, and demo outputs stay inside this repository.
- Tests prohibit network connections. The default planner and Vega-Lite PNG rendering work offline.
- No publication, external account access, or API key required. No em-dashes in authored docs.
- Done: test-first evidence, correct numerical results and provenance, JSON round-trip, exact data replay, branching history, linked summer/winter updates, inspected PNGs, and three stage commits.

## 1. Figure representation and mark identity

Section 3.1 calls figures "structured analytical states" and defines `F_t = {V_t, C_t, D_t, M_t}`.

| Component | Implementation |
| --- | --- |
| `V_t` | Vega-Lite spec with embedded data, actual PNG rendered from that spec, and a textual summary of values and scope. PNG stored as base64 in JSON for portability and exported by the demo. |
| `C_t` | Ordered analytical actions, deterministic executable pandas source, executable visualization source, and execution environment versions. No model-provided Python is executed. |
| `D_t` | Selected original rows, row schema, aggregate results and result schema. The artifact embeds the complete input dataset and checksum for replay and follow-up queries. |
| `M_t` | UTC timestamp, stable logical figure id, unique figure-version id, operation type, user instruction/interaction, and artifact/version links. |

Every source row has a unique `row_id`. Every aggregate mark has a globally version-scoped `mark_id` and maps to every contributing source row, not just one representative row. Line charts use identifiable monthly point marks over a connecting line; the line is a guide, not a separately selectable datum. Bars have one mark per state. The spec embeds the ids in its data and tooltip. Monthly point brushing is discrete membership, including noncontiguous winter months; this pass does not infer continuous ranges from a pair of endpoints.

## 2. Bidirectional mapping R_t

The paper names both directions "Analytical operations → Visualization" and "Visualization → Analytical operations".

Forward path:

1. `Planner.plan(instruction, selection=None)` returns a constrained action sequence.
2. `Pipeline.execute(actions, instruction, parent_version=None)` validates and compiles it.
3. Stored pandas source executes over an embedded dataset snapshot and produces selected rows plus grouped results.
4. Generated visualization source adds identifiers, a Vega-Lite specification, an offline PNG and summary.
5. A new artifact version records input, actions, code, data, mapping and figure links.

Reverse path:

1. `Mapping.select(figure, mark_ids)` resolves version-specific mark ids, deduplicates rows, and returns a selection with rows, months and years.
2. `Pipeline.follow_up(source_id, mark_ids, instruction)` combines this selection with the request for a ranking across states.
3. The selected Florida rows are the provenance evidence. Only the selected month and year constraints transfer to the full dataset for an all-state comparison. A stored coordination rule makes this scope expansion explicit.
4. Empty brushes and unknown or stale mark ids raise clear errors without changing history. A failed action or render creates no ledger version.

## 3. Artifact A_t and provenance

Section 3.1 describes a "version-controlled ledger" and a "directed acyclic graph of artifact versions". Section 5.3 distinguishes figure versions from artifact versions.

- `Artifact` owns the embedded input snapshot, immutable figure versions, immutable artifact-version nodes, and a current head.
- Each artifact node records parent version ids, input/interaction, its logical-figure-to-figure-version map, and coordination links. Parent references must already exist, so new versions cannot introduce cycles.
- Executing from an earlier version creates a branch. Existing snapshots remain unchanged; logical figure ids persist during updates.
- An extension adds a linked logical figure. A manipulation creates a new version of the target logical figure. A brush update creates one new artifact state containing updated linked targets.
- Each coordination link stores initiating/target figure ids, propagated dimensions (`month`, `year`), and the target's reusable action template. A later brush replaces only the corresponding filters, re-executes all directly linked targets, and preserves the prior state.
- JSON persistence includes a format version, dataset checksum, all figure records, nodes, and head. Save by temporary sibling file then replace. Validate ids, DAG references and checksums on load.
- `Pipeline.replay(figure_version_id)` re-runs the stored analytical and visualization source against the embedded dataset, checks exact rows/results/mapping/spec, and regenerates PNG. Replay rejects source that differs from the validated compiler's output rather than executing arbitrary edited code. This is a bounded code compiler, not a security sandbox for arbitrary Python.

## 4. Action space (Section 5.2)

The paper defines a "compositional action space" of "atomic operations" in four categories: "data filtering", "data transformation", "data analysis", and "data visualization". It explicitly names `add chart type`, `add params`, `add data`, `update data`, `add encoding`, and `update encoding`.

| Paper category | Minimal implemented operations | Deferred |
| --- | --- | --- |
| Data filtering | `select_table` (bundled temperatures); `filter_rows` with typed `in` values for state/year/month | Joins, arbitrary predicates, fuzzy matching |
| Data transformation | `group_by` on month or state, stable sort keys | Derived columns, general expressions |
| Data analysis | `aggregate` mean temperature; `sort_rows` with deterministic ties | Modeling, statistics beyond mean, stochastic methods |
| Data visualization | `add_chart_type` line/bar; `add_encoding`; `add_params` for brush; `add_data` via execution results | Arbitrary encodings and chart grammars; generic update actions |

Actions compose in a validated order: table, zero or more filters, group, aggregate, sort, chart, encoding, parameters, data. Chart encodings must match the grouping. Unsupported operations and malformed values are rejected before execution. `update data` behavior occurs through re-execution of a coordination template, not through a general mutable chart API.

The paper's "Planner, Executor, and Evaluator" and "plan–action–observation loop" inform separate responsibilities here: the planner returns actions, the deterministic executor returns artifacts, and validation/replay checks results. This slice does not claim to implement multi-agent search or an LLM self-reflection loop.

## 5. Package and test layout

- `pyproject.toml`, `uv.lock`, `.gitignore`: pinned packaging, CLI entry point and local runtime exclusions.
- `src/figureflow/model.py`: Figure, Mapping, Selection, Artifact and version validation/persistence.
- `src/figureflow/actions.py`: action validation, pandas compiler, visualization source and rendering.
- `src/figureflow/planner.py`: Planner protocol, RuleBasedPlanner, opt-in `FIGUREFLOW_PLANNER=module:factory` hook. Factory returns a provider-backed planner; tests use only a local fake module. Provider integrations are responsible for their own keys and transport.
- `src/figureflow/pipeline.py`: execution, follow-up, coordination, branching and replay.
- `src/figureflow/data/temperatures.csv`: synthetic monthly Celsius temperatures for Florida, Arizona, California and Illinois, 2014 through 2024 inclusive. This deliberately follows the paper's stated bounds, which contain 11 calendar years despite its phrase "past ten years". Not measured climate data and not all 50 states.
- `src/figureflow/cli.py`, `__main__.py`: offline Fig. 1 demo and saved-ledger replay.
- `tests/conftest.py`: repository-local temp directories and blocked sockets.
- `tests/test_pipeline.py`: numerical means, aggregate lineage, mark selection, action rejection, saved replay, failed-operation atomicity, branching, multiple linked figures, planner injection and corruption rejection.
- `tests/test_cli.py`: subprocess demo, exported files and fresh-process replay.
- `README.md`: install, API boundaries, demo, expected results and limitations.

## 6. Staged work and verification

### Stage A: plan

- [ ] Review representation, both mappings, ledger and Section 5 action space against the paper.
- [ ] Check doc for em-dashes; commit only `docs/plan.md` with `docs: plan minimal figures-as-interfaces slice`.

### Stage B: package

- [ ] Create pinned project configuration and venv; write tests against the public API before implementation.
- [ ] Run `.venv/bin/python -m pytest tests/test_pipeline.py -q`; capture expected failures in `docs/verification.md`.
- [ ] Implement typed records, compiler, actual rendering, stub planner, JSON persistence and pipeline.
- [ ] Verify independent expected means (Florida June 28.5 C; summer Arizona 33.5 C and Florida 29.5 C; winter Florida 18.5 C and Arizona 13.5 C), row-id lineage, replay, branching and invalid inputs.
- [ ] Run package tests and commit explicit Stage B paths with `feat: implement offline figure provenance pipeline`.

### Stage C: demo

- [ ] Write failing CLI tests before CLI implementation.
- [ ] Implement `figureflow demo --output demo-output`: Florida 12-month trend, brush June-August, rank the four states, brush December/January/February, automatically update the same linked chart.
- [ ] Export JSON ledger, specs, PNGs, code and a readable transcript. Run `figureflow replay demo-output/artifact.json` in a fresh process.
- [ ] Run full tests, inspect all exported PNGs, check package installation, ensure clean git state after explicit-path commit `feat: demonstrate linked seasonal exploration`.

## 7. Out of scope and next slice

The full hybrid web UI, actual browser brush event wiring, general natural-language comprehension, the science-of-science database and corpus, cloud hosting, multi-user collaboration, LLM provider SDKs, tree-based planning, evaluator confidence scoring, arbitrary SQL/Python sandboxes, transitive coordination and DAG merges are out of scope. This CLI accepts/simulates resolved brush mark ids and proves the backend contract. Next slice: a small local two-chart viewer that sends real Vega-Lite brush selections into the same tested mapping and displays version history.
