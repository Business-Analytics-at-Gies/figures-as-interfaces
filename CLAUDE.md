# figures-as-interfaces

type: code

Implementation of "Figures as Interfaces: Toward LLM-Native Artifacts for Scientific Discovery" (Wang, Sheng, Shao, Qian, Li, Cao, Wang; arXiv:2604.08491v2, Apr 2026). Paper: https://arxiv.org/abs/2604.08491. PDF and text extract in `sources/` (gitignored; not redistributable). Demo site named in the paper: www.llm-native-figure.com.

Core idea to implement: an LLM-native figure is a data-driven artifact that is human-legible and machine-addressable. Each figure embeds its full provenance (data subset, analytical operations and code, visualization spec) so an agent can trace a selection back to source rows, generate code to extend the analysis, and produce new figures from natural-language instructions or direct manipulation, via a bidirectional mapping between figure marks and underlying data.

## Lane

Built on Codex (gpt-6-astra, reasoning effort low) in this workspace to conserve Claude quota (Vishal, 2026-09-15). Control holds merges and reviews. Tests required for logic; TDD red first.

## Rules

- Scratch files inside this repo. Pin dependency versions. Venv via `uv` or `python3 -m venv .venv`.
- Convert any new PDF to text in `sources/` before reading it.
- Public repo: https://github.com/Business-Analytics-at-Gies/figures-as-interfaces (MIT). PRs only on main. Student contributors get triage, never write. Nothing learner-facing (announcements) goes out without Vishal's approval.

## Current Focus

First pass: read the paper, write `docs/plan.md` (architecture, minimal viable slice, what is out of scope), then implement the minimal slice with tests.

## Session Log

- 2026-09-15: repo created by control; paper staged and converted; Codex workspace opened.
