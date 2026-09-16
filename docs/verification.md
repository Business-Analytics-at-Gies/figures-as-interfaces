# Verification record

## Stage A

Read `CLAUDE.md`, the full paper text, and Section 5 before writing the plan. Committed the initial plan, then the DuckDB/taxi correction. The Consumers section incorporates the notebook interoperability requirement.

## Stage B

- Initial temperature API skeleton: 26 failures, 1 passing network guard. This uncompleted slice was replaced following Vishal's course correction.
- Revised taxi API skeleton: 31 failures, 1 passing network guard. Failures were missing pipeline/planner behavior, not test collection failures.
- DuckDB implementation and actual 50,000-trip sample: 32 passed.
- Additional interoperability and integrity checks exposed one loader issue: 1 failure, 37 passed. A missing dataset checksum was incorrectly regenerated during load.
- Loader corrected to reject missing checksums: 38 passed, with network sockets disabled.
- The schema validator accepts serialized figures and artifacts. A test resolves selections using only ordinary JSON, without Mapping, and another executes the stored SQL directly in DuckDB without the compiler.
- Regenerated the sample twice from the original local Parquet. Both sample hashes and complete manifests were identical (`cmp` exit 0). The sample is approximately 914 KiB; the original 48 MiB file is not added to Git.
- Actual sample integration independently queries the raw sample and lookup in DuckDB and compares all 24 Manhattan hourly counts with the pipeline results.

Tests use repository-local temporary files. Rendering denies external data URLs and tests disable Python sockets. The optional provider hook is tested with an in-memory local module, without an API call.

## Stage C

- CLI, export, committed-example and notebook tests before implementation: 6 failures.
- Completed suite: 44 passed, including all 38 Stage B checks and 6 Stage C checks. CLI subprocesses inherit a socket-blocking guard; notebook analysis cells execute under the same offline test environment.
- Ran the actual demo on all 50,000 sample trips: 44,816 Manhattan trips; evening hours 17-20 select 11,738 trips; morning hours 7-10 select 7,157 trips. The leading pickup zone changes from Midtown Center (868 evening trips) to Upper East Side North (538 morning trips).
- Reloaded the demo JSON in a fresh process and replayed all 3 figure versions, comparing complete selected rows, counts, mappings, text summaries and Vega-Lite specs.
- Viewed all 3 exported PNGs. Hour labels, trip counts and zone names are readable; the rankings and titles reflect the intended selection.
- Validated the committed example against the documented JSON Schema and replayed it in a subprocess. It contains the full demo snapshot; it is not a reduced illustrative fixture.
- Built both source and wheel distributions. Installed the wheel into a separate repository-local virtual environment, ran the demo from a separate working directory, and successfully replayed every figure. This checks that the sample and lookup are included in the installed package.
- Executed every notebook analysis cell locally, including rendering and plain-JSON selection. Google Colab's upload widget itself was not exercised in a live Colab session; its setup uses a repository ZIP and standard pip installation. Package installation was verified separately as above.

Concurrent repository setup introduced a license, contribution guidance, paper attribution and a remote while implementation was underway. The README preserves the attribution/license and contribution link; unrelated `docs/drafts/` content is left untouched. No push or publication was performed by this implementation session.
