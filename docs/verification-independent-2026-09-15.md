Independent Verification Report: figures-as-interfaces (2026-09-15)

Defects and Gaps (ranked)
1. Missing general V,C,D,M per-figure tuple in example artifact (examples/taxi-artifact.json)
   - Finding: The paper defines each figure as F_t = {V_t, C_t, D_t, M_t} (sources/figures-as-interfaces.txt:218-235), but the committed example artifact stores a single top-level dataset and per-figure V/C/D/M without an explicit per-figure dataset slice.
   - Evidence: `.venv/bin/python - << 'PY'` … `print('example_dataset_len', len(art['dataset']))` printed `example_dataset_len 50000` and `example_figure f0001 rows 44816 results 24` (figure rows are a subset drawn from the shared dataset).
   - Impact: Conceptually aligned but the portable artifact does not isolate D_t per figure; reconstruction still works because Mapping and D embed row_id and result rows, but the structure is less strict than the paper’s per-figure D_t definition.

2. Coordination graph restricted to single hard-coded pattern (src/figureflow/pipeline.py:84-105, model.py:58-116)
   - Finding: Coordination links are implemented only for the specific hourly→zone ranking pattern, with hard-coded checks on action tails and link dimensions, rather than a general coordination graph across arbitrary figures as described in Sec. 3.1/Artifact.
   - Evidence: pipeline.follow_up enforces `source.C['actions'][-7]['field'] == 'pickup_hour'` and `actions[-7]['field'] == 'pickup_zone_id'` and pushes links with `dimensions: ['pickup_hour','pickup_borough']`; Artifact.validate enforces `link['dimensions'] != ['pickup_hour', 'pickup_borough']` as the only valid form.
   - Impact: The demo implements one concrete coordination edge type (hour/borough → zone counts) instead of a general coordination schema over arbitrary analytical dimensions.

3. Action space coverage limited to a small subset of Sec. 5.2
   - Finding: Implemented actions are select_table, filter_rows, group_by, aggregate(count), sort_rows, add_chart_type, add_encoding, add_params, add_data; there is no implementation of many action types referenced in Sec. 5.2 (e.g., joins, derive column, modeling, multi-figure layouts beyond the single coordination pattern).
   - Evidence: src/figureflow/actions.py:13-48 and planner.RuleBasedPlanner (src/figureflow/planner.py:31-47) constrain ops to that fixed tail and filter_rows over pickup_borough/pickup_hour only.
   - Impact: The implemented system covers only the “trip count by hour / by zone” slice of the paper’s action space; more complex analytical workflows in Sec. 5.2 are out of scope here.

4. Bidirectional mapping constrained to one dataset and two grouping dimensions
   - Finding: The Mapping object (model.py:23-40) and compile_visualization/materialize (actions.py:66-125) provide a real mark→rows mapping, but only for the TLC schema, with marks defined as version_id plus a single grouping key (pickup_hour or pickup_zone_id).
   - Evidence: `.venv/bin/python - << 'PY'` on .scratch/verify/artifact.json printed `figure f0001 rows 44816 results 24 mark_ids 24` and `mark f0001 f0001:0 row_ids_len 1136 rows_len 1136 hours [0] boroughs ['Manhattan']`; similarly for f0002: `row_ids_len 191 rows_len 191 hours [17, 18, 19, 20] boroughs ['Manhattan']`.
   - Impact: Bidirectional mapping is correct for this domain and grouping, but not generalized to arbitrary schemas or multiple grouping dimensions as might be implied by the broader framework.

5. Example artifact inflated by duplicated dataset and embedded PNGs
   - Finding: The 28 MB size of examples/taxi-artifact.json is driven by the full 50,000-row dataset plus three large base64-encoded PNG images and repeated per-figure D blocks.
   - Evidence: `wc -c examples/taxi-artifact.json` printed `29016489 examples/taxi-artifact.json`; `.venv/bin/python` inspection printed `example_dataset_len 50000` and `example_figure f0001 rows 44816 ... png_len 78852`, `f0002 ... png_len 536976`, `f0003 ... png_len 423612`.
   - Impact: This is a faithful but verbose research-format artifact; a small portable example should contain: a much smaller dataset sample, one or two figures, compact V (spec + summary without PNGs), C (actions + SQL + visualization_python), D (rows/results for those figures only), M, and R, plus artifact metadata (dataset_hash, source) but not the entire 50k-row sample.

Verified Correct Against Paper Claims
1. Per-figure F_t = {V_t, C_t, D_t, M_t} representation is instantiated
   - Finding: Figure dataclass encodes exactly F_t = {V_t, C_t, D_t, M_t} plus R_t; Artifact holds a DAG of versions and coordination links, matching Sec. 3.1.
   - Evidence: model.Figure is defined as `"F_t = {V_t, C_t, D_t, M_t}, plus its explicit bidirectional relation."` with fields V,C,D,M,R; pipeline._make constructs V via materialize, C (actions, sql, visualization_python, environment), D (rows, schema, results, result_schema), M (figure_id, version_id, timestamp, operation, instruction, artifact_id, artifact_version).

2. Every Vega-Lite mark id maps back to source rows in D
   - Finding: For the demo artifact, every inspected mark_id has a non-empty, exact set of source rows in D, and Mapping.select enforces that mapping.
   - Evidence: `.venv/bin/python` on .scratch/verify/artifact.json printed `dataset_len 50000`, `figure_versions ['f0001', 'f0002', 'f0003']`, and for f0001 `rows 44816 results 24 mark_ids 24`; for sampled marks, `mark f0001 f0001:0 row_ids_len 1136 rows_len 1136` and `mark f0001 f0001:2 row_ids_len 568 rows_len 568`, with hours and boroughs consistent with the grouping; Mapping.select in model.py checks that every mark id exists and that all referenced row_ids are present in D['rows'], raising on mismatch.

3. Bidirectional mapping is real in both directions for the taxi demo slice
   - Instruction → actions → SQL → data → spec: RuleBasedPlanner.plan constructs a constrained action sequence; actions.validate enforces the grammar; compile_sql and compile_visualization are derived from those actions; materialize executes the SQL against a DuckDB trips table derived solely from the JSON dataset snapshot and executes the visualization code to attach data values and mark ids to the Vega-Lite spec and to build Mapping.mark_to_rows.
   - Visualization marks → source rows and new actions: Pipeline.follow_up calls Mapping.select(source, mark_ids) to obtain a Selection (rows, hours, boroughs, mark_ids), passes it to planner.plan (selection), then validates the returned actions and enforces that the resulting filters match the brushed hours and boroughs; Pipeline.brush uses stored coordination links and selection_filters(selection) to build updated actions and new figures, and stores these coordination rules in the artifact.
   - Evidence: Running `.venv/bin/figureflow demo --output .scratch/verify` printed `TLC January 2024: 50,000 sampled trips... Manhattan: 44,816 trips across 24 hourly marks.` and `Replayed 3 figure versions with identical data, mappings and specs.`; the JSON-only inspection (above) re-derived rows behind three mark ids and confirmed matching row counts and attributes.

4. Coordination between linked figures implemented as a concrete coordination graph
   - Finding: Artifact.versions nodes carry a `links` list with source, target, dimensions, and action_template; Pipeline.follow_up appends links for source→target; Pipeline.brush uses those links to update coordinated figures when brushes change, and Artifact.validate checks for dangling or malformed links.
   - Evidence: model.Artifact.validate iterates node['links'] and enforces that link['source'] and link['target'] refer to figures in the same node and that dimensions are exactly ['pickup_hour','pickup_borough']; pipeline.follow_up builds `node['links'].append({'source':source_id,'target':logical,'dimensions':['pickup_hour','pickup_borough'],'action_template':...})`; pipeline.brush filters links by source_id and uses action_template plus selection_filters to regenerate coordinated figures and commits them as new artifact versions.

5. Stored SQL and replay reproduce data and specs byte-for-byte
   - Finding: Re-executing stored SQL and visualization code against the recorded dataset reproduces D, R, and key parts of V identically; replay() rejects any mismatch.
   - Evidence: The demo CLI printed `Replayed 3 figure versions with identical data, mappings and specs.`; separate JSON-only replay for f0001 used compiled SQL against art['dataset'] and printed `sql_equal True`, `results_equal True`, `rows_equal True`.
   - Mechanism: Pipeline.replay re-calls materialize with stored `figure.C['sql']` and `figure.C['visualization_python']` and raises if D, R, V['spec'], or V['summary'] differ from the stored figure.

6. Action space slice implemented
   - Finding: Within Sec. 5.2’s broader plan–action–execution loop, this codebase implements a constrained action space consisting of: select_table(trips), filter_rows on pickup_borough and pickup_hour, group_by on pickup_hour or pickup_zone_id, aggregate(count), sort_rows, add_chart_type (line or bar), add_encoding, add_params (interval brush), and add_data.
   - Evidence: actions.validate hard-codes the allowed ops and arguments; planner.RuleBasedPlanner generates only these operations.

Overall Verdict
FAIL – The implementation correctly instantiates F_t = {V_t, C_t, D_t, M_t} plus R_t, supports real bidirectional mappings and deterministic replay for the taxi slice, and encodes a concrete coordination graph, but it only covers a narrow action space and a single coordination pattern relative to the paper’s more general Sec. 3.1 and 5 claims.
