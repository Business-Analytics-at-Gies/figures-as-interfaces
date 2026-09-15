# Figures as Interfaces Implementation Plan

**Goal:** Implement and test the paper's Figure 1 loop as a small, offline Python project.
**Architecture:** `figureflow` compiles validated action sequences into deterministic DuckDB SQL, renders Vega-Lite, and records immutable figures in a JSON artifact ledger. A replaceable planner translates language; a mapping translates selected marks into source rows and explicit follow-up constraints.
**Source:** `sources/figures-as-interfaces.txt`, read in full, especially Section 3.1 (lines 175-329) and Section 5 (lines 596-790). This is a minimal implementation of the representation and mappings, not a reproduction of Nexus or its evaluation results.
**Execution:** Complete Stages A, B, C inline, with failing tests before implementation and explicit-path commits after each stage, as requested.

## Constraints and completion criteria

- Python 3.12+, repository-local `.venv`, exact direct dependency pins in `pyproject.toml`, resolved dependency lock.
- Scratch, test temporary directories, caches, and demo outputs stay inside this repository.
- Tests prohibit network connections. The default planner and Vega-Lite PNG rendering work offline.
- No publication, external account access, or API key required. No em-dashes in authored docs.
- Done: test-first evidence, correct counts and provenance, JSON round-trip, exact data replay, branching history, linked evening/morning updates, inspected PNGs, and three stage commits.

## 1. Figure representation and mark identity

Section 3.1 calls figures "structured analytical states" and defines `F_t = {V_t, C_t, D_t, M_t}`.

| Component | Implementation |
| --- | --- |
| `V_t` | Vega-Lite spec with embedded data, actual PNG rendered from that spec, and a textual summary of values and scope. PNG stored as base64 in JSON for portability and exported by the demo. |
| `C_t` | Ordered analytical actions, deterministic executable DuckDB SQL, executable visualization source, and execution environment versions. No model-provided Python or arbitrary SQL is executed. SQL comes from a small allowlisted compiler. |
| `D_t` | Selected original rows, row schema, aggregate results and result schema. The artifact embeds the complete input dataset and checksum for replay and follow-up queries. |
| `M_t` | UTC timestamp, stable logical figure id, unique figure-version id, operation type, user instruction/interaction, and artifact/version links. |

Every source row has a unique `row_id`. Every aggregate mark has a globally version-scoped `mark_id` and maps to every contributing source row, not just one representative row. Line charts use identifiable hourly point marks over a connecting line; the line is a guide, not a separately selectable datum. Bars have one mark per pickup zone. The spec embeds the ids in its data and tooltip. Hourly point brushing is discrete membership, including noncontiguous hours; this pass does not infer continuous ranges from a pair of endpoints.

## 2. Bidirectional mapping R_t

The paper names both directions "Analytical operations → Visualization" and "Visualization → Analytical operations".

Forward path:

1. `Planner.plan(instruction, selection=None)` returns a constrained action sequence.
2. `Pipeline.execute(actions, instruction, parent_version=None)` validates and compiles it.
3. Stored DuckDB SQL executes over an embedded dataset snapshot and produces selected rows plus grouped results.
4. Generated visualization source adds identifiers, a Vega-Lite specification, an offline PNG and summary.
5. A new artifact version records input, actions, code, data, mapping and figure links.

Reverse path:

1. `Mapping.select(figure, mark_ids)` resolves version-specific mark ids, deduplicates rows, and returns a selection with rows, hours and boroughs.
2. `Pipeline.follow_up(source_id, mark_ids, instruction)` combines this selection with the request for a ranking of pickup zones.
3. Selected trip rows are the provenance evidence. Hour-of-day and pickup-borough constraints transfer to the complete January sample for a zone ranking within the initiating borough. Date coverage stays January 2024; a brush selects recurring hours across the month, not just the dates on which those hours had trips. The rule stores this scope explicitly.
4. Empty brushes and unknown or stale mark ids raise clear errors without changing history. A failed action or render creates no ledger version.

## 3. Artifact A_t and provenance

Section 3.1 describes a "version-controlled ledger" and a "directed acyclic graph of artifact versions". Section 5.3 distinguishes figure versions from artifact versions.

- `Artifact` owns the embedded input snapshot, immutable figure versions, immutable artifact-version nodes, and a current head.
- Each artifact node records parent version ids, input/interaction, its logical-figure-to-figure-version map, and coordination links. Parent references must already exist, so new versions cannot introduce cycles.
- Executing from an earlier version creates a branch. Existing snapshots remain unchanged; logical figure ids persist during updates.
- An extension adds a linked logical figure. A manipulation creates a new version of the target logical figure. A brush update creates one new artifact state containing updated linked targets.
- Each coordination link stores initiating/target figure ids, propagated dimensions (`pickup_hour`, `pickup_borough`), and the target's reusable action template. A later brush replaces only the corresponding filters, re-executes all directly linked targets, and preserves the prior state.
- JSON persistence includes a format version, dataset checksum, all figure records, nodes, and head. Save by temporary sibling file then replace. Validate ids, DAG references and checksums on load.
- `Pipeline.replay(figure_version_id)` re-runs the stored SQL and visualization source against the embedded dataset, checks exact rows/results/mapping/spec, and regenerates PNG. Replay rejects SQL or visualization source that differs from the validated compiler's output rather than executing arbitrary edited code. This is a bounded code compiler, not a security sandbox for arbitrary Python.

## 4. Action space (Section 5.2)

The paper defines a "compositional action space" of "atomic operations" in four categories: "data filtering", "data transformation", "data analysis", and "data visualization". It explicitly names `add chart type`, `add params`, `add data`, `update data`, `add encoding`, and `update encoding`.

| Paper category | Minimal implemented operations | Deferred |
| --- | --- | --- |
| Data filtering | `select_table` (bundled taxi trips); `filter_rows` with typed `in` values for pickup borough/hour | Joins, arbitrary predicates, fuzzy matching |
| Data transformation | `group_by` on pickup hour or pickup zone, stable sort keys | Derived columns, general expressions |
| Data analysis | `aggregate` trip count; `sort_rows` with deterministic ties | Modeling, statistics beyond count, stochastic methods |
| Data visualization | `add_chart_type` line/bar; `add_encoding`; `add_params` for brush; `add_data` via execution results | Arbitrary encodings and chart grammars; generic update actions |

Actions compose in a validated order: table, zero or more filters, group, aggregate, sort, chart, encoding, parameters, data. Chart encodings must match the grouping. Unsupported operations and malformed values are rejected before execution. `update data` behavior occurs through re-execution of a coordination template, not through a general mutable chart API.

The paper's "Planner, Executor, and Evaluator" and "plan–action–observation loop" inform separate responsibilities here: the planner returns actions, the deterministic executor returns artifacts, and validation/replay checks results. This slice does not claim to implement multi-agent search or an LLM self-reflection loop.

## 5. Package and test layout

- `pyproject.toml`, `uv.lock`, `.gitignore`: pinned packaging, CLI entry point and local runtime exclusions.
- `src/figureflow/model.py`: Figure, Mapping, Selection, Artifact and version validation/persistence.
- `src/figureflow/actions.py`: action validation, SQL compiler, visualization source and rendering.
- `src/figureflow/planner.py`: Planner protocol, RuleBasedPlanner, opt-in `FIGUREFLOW_PLANNER=module:factory` hook. Factory returns a provider-backed planner; tests use only a local fake module. Provider integrations are responsible for their own keys and transport.
- `src/figureflow/pipeline.py`: execution, follow-up, coordination, branching and replay.
- `data/taxi_zone_lookup.csv`: verbatim copy of the course lookup; `LocationID`, `Borough`, `Zone`, `service_zone`.
- `data/yellow_tripdata_sample.parquet`: committed 50,000-trip deterministic sample of the local January 2024 TLC extract. Preserve original Parquet row offsets as stable source ids. The full Parquet is never committed.
- `data/sample_manifest.json`, `scripts/build_sample.py`: input hashes, cleaning SQL, sampling order and count. Read `FIGUREFLOW_TAXI_PARQUET` only for explicit sample regeneration or full-data mode; a missing path produces a clear error. Default runtime uses the committed sample.
- `src/figureflow/dataset.py`: DuckDB load and pickup-zone join; enforce the course cleaning conditions and project trip-level row ids into the analytical table.
- `src/figureflow/cli.py`, `__main__.py`: offline Fig. 1 demo and saved-ledger replay.
- `tests/conftest.py`: repository-local temp directories and blocked sockets.
- `tests/test_pipeline.py`: numerical counts, aggregate lineage, mark selection, action rejection, saved replay, failed-operation atomicity, branching, multiple linked figures, planner injection and corruption rejection.
- `tests/test_cli.py`: subprocess demo, exported files and fresh-process replay.
- `README.md`: install, API boundaries, demo, expected results and limitations.

## 6. Staged work and verification

### Stage A: plan

- [x] Review representation, both mappings, ledger and Section 5 action space against the paper.
- [x] Check doc for em-dashes; commit only `docs/plan.md` with `docs: plan minimal figures-as-interfaces slice`.

### Stage B: package

- [ ] Create pinned project configuration and venv; write tests against the public API before implementation.
- [ ] Run `.venv/bin/python -m pytest tests/test_pipeline.py -q`; capture expected failures in `docs/verification.md`.
- [ ] Implement typed records, compiler, actual rendering, stub planner, JSON persistence and pipeline.
- [ ] Verify hand-counted fixture results, full sample counts against an independent DuckDB query, row-id lineage, replay, branching and invalid inputs.
- [ ] Run package tests and commit explicit Stage B paths with `feat: implement offline figure provenance pipeline`.

### Stage C: demo

- [ ] Write failing CLI tests before CLI implementation.
- [ ] Implement `figureflow demo --output demo-output`: Manhattan hourly trip counts across January, brush hours 17-20 inclusive, rank pickup zones within Manhattan, brush hours 7-10 inclusive, automatically update the same linked chart.
- [ ] Export JSON ledger, specs, PNGs, code and a readable transcript. Run `figureflow replay demo-output/artifact.json` in a fresh process.
- [ ] Run full tests, inspect all exported PNGs, check package installation, ensure clean git state after explicit-path commit `feat: demonstrate linked taxi exploration`.

## 7. Out of scope and next slice

The full hybrid web UI, actual browser brush event wiring, general natural-language comprehension, the science-of-science database and corpus, cloud hosting, multi-user collaboration, LLM provider SDKs, tree-based planning, evaluator confidence scoring, arbitrary SQL/Python sandboxes, transitive coordination and DAG merges are out of scope. This CLI accepts/simulates resolved brush mark ids and proves the backend contract. Next slice: a small local two-chart viewer that sends real Vega-Lite brush selections into the same tested mapping and displays version history.

## Course correction: DuckDB and NYC taxi data

Vishal revised the engine and dataset after the initial Stage A commit and first temperature test failures. Retain the architecture above, replace those uncompleted temperature tests and implementation with taxi-specific tests before implementing the revised pipeline. DuckDB local is for fast iteration; a student-facing deployment engine is a later decision.

Read the course's `learner-files/sql/M4I6-taxi-star.sql`. Raw columns are `tpep_pickup_datetime`, `tpep_dropoff_datetime`, `PULocationID`, `DOLocationID`, `fare_amount`, `trip_distance`, and `payment_type`. The course star uses `pickup_zone_id`, `dropoff_zone_id`, `payment_type_id`, `fare`, `distance`, and `duration`. This minimal analytical projection retains `row_id`, `pickup_zone_id`, `pickup_zone`, `pickup_borough`, `pickup_hour`, and `pickup_date`; the sample retains raw columns so source rows can be recovered by original file offset.

Apply the course cleaning rules before sampling: January pickups, dropoff after pickup, duration at most 720 minutes, positive distance at most 100 miles, positive fare at most 500 dollars. Assign row ids from `file_row_number` before filtering. Select the first 50,000 valid trips ordered by MD5 of the original row number with row number as the tie-breaker. Sort the resulting file by original row number. This spreads the sample across the month deterministically; it is a sample, not the full month totals.

The DuckDB analytical actions operate over the normalized, joined trip table. The artifact embeds that complete analytical input and its schema/checksum, plus source-file hashes and preparation SQL. Re-execution does not depend on the course folder or the full Parquet. The lookup and deterministic Parquet sample are packaged for installed use. Tests use a small hand-counted trip fixture for fine-grained checks and the actual committed sample for integration checks. The CLI reports sample scope clearly and exports the full zone ranking; its printed preview may show only leading zones.
