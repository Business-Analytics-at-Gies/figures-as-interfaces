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
