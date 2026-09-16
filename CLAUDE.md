# figures-as-interfaces

type: code

Implementation of "Figures as Interfaces: Toward LLM-Native Artifacts for Scientific Discovery" (Wang, Sheng, Shao, Qian, Li, Cao, Wang; arXiv:2604.08491v2, Apr 2026). Paper: https://arxiv.org/abs/2604.08491. PDF and text extract in `sources/` (gitignored; not redistributable). Demo site named in the paper: www.llm-native-figure.com.

Core idea to implement: an LLM-native figure is a data-driven artifact that is human-legible and machine-addressable. Each figure embeds its full provenance (data subset, analytical operations and code, visualization spec) so an agent can trace a selection back to source rows, generate code to extend the analysis, and produce new figures from natural-language instructions or direct manipulation, via a bidirectional mapping between figure marks and underlying data.

## Authors' permission

Vishal asked the paper's authors for permission on LinkedIn on 2026-09-15; reply pending. Until it arrives, the repo stays an attributed CC BY-NC-SA 4.0 implementation and no announcement to students goes out. Record the reply here when it comes.

## Lanes (Vishal, 2026-09-15: conserve Claude quota; Codex main pool is low)

| Work | Lane | How |
|---|---|---|
| Design, plan, architecture decisions | Codex gpt-6-astra, reasoning low | `codex --model gpt-6-astra -c model_reasoning_effort=low` |
| Mechanical implementation, test runs, review fixes, rebases | Cursor agent or opencode (Codex Spark was rejected on this account on 2026-09-15: 'not supported when using Codex with a ChatGPT account'; retry only after re-verifying) | `herdr agent start <name> --kind cursor --pane <id>` or `--kind opencode` |
| Independent verification, second attempt, premise checks | opencode | `herdr agent start <name> --kind opencode --pane <id>`; scratch files inside this repo, never /tmp |
| Notebook, UI, front-end work (Colab example, any web view) | Cursor agent | `herdr agent start <name> --kind cursor --pane <id>`; accept the trust dialog then re-send the prompt |
| Merges, reviews of merges, anything learner-facing | Claude (control) | holds main; PRs only |

Tests required for logic, red first. Control verifies claims against the running code, not the agent's brief.

## Rules

- Scratch files inside this repo. Pin dependency versions. Venv via `uv` or `python3 -m venv .venv`.
- Convert any new PDF to text in `sources/` before reading it.
- Public repo: https://github.com/Business-Analytics-at-Gies/figures-as-interfaces (MIT). PRs only on main. Student contributors get triage, never write. Nothing learner-facing (announcements) goes out without Vishal's approval.

## Current Focus

First pass: read the paper, write `docs/plan.md` (architecture, minimal viable slice, what is out of scope), then implement the minimal slice with tests.


## Lane lessons (2026-09-15)

- opencode wedged for two hours on a long multi-step edit (process at 110 percent CPU, screen and context counter frozen, Escape ignored); its scaffold and read-only verification passes were fine. Give it bounded tasks and check for file writes; if nothing changes for 15 minutes, stop it and hand the remainder to Cursor.
- Cursor on Auto finished the size policy, the merge from main, and the fresh-clone fix; its Opus default was out of usage.
- Codex Spark returned HTTP 400 on this account (OpenAI-side, see ~/.claude/references/codex-cli.md); re-probe before relying on it.
- Control verifies every agent brief from a clean worktree before merging: a fresh checkout found 11 errors that the agents' checkout hid.

## Session Log

- 2026-09-15: PR #2 merged into main on 2026-09-16 08:24 CDT (minimal pipeline: DuckDB, taxi sample, artifact ledger with mark-to-row mapping, rule-based planner, Colab demo, 44 tests, independent verification report with a FAIL-on-scope verdict). Next slice for the astra lane: generalize the coordination graph and the action space per docs/verification-independent-2026-09-15.md.
- 2026-09-15: repo created by control; paper staged and converted; Codex workspace opened.
