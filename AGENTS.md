# OAE Agent Contract

## Authority and preflight

Before any work, read and follow:

1. `docs/specs/00_OAE_v0.1_FROZEN_MATH_SPEC.md`
2. `docs/specs/01_OAE_v0.1_DATA_BACKTEST_SPEC.md`
3. `docs/specs/02_OAE_v0.1_IMPLEMENTATION_SPEC.md`
4. `docs/specs/03_OAE_v0.1_IMPLEMENTATION_ERRATA.md`
5. `docs/specs/04_OAE_v0.1_PERSISTENCE_ERRATA.md`
6. `docs/CHANGE_CONTROL.md`
7. `docs/specs/SPEC_MANIFEST.sha256`

Verify the specification manifest before implementation. The authoritative
specification identity is the manifest file plus the SHA-256 of the manifest
itself. Do not use an unexplained free-standing `Spec hash`.

### S1.02 bootstrap exception

During S1.02 only, if the canonical repository specification files do not yet
exist, Codex may use only the complete canonical source texts explicitly
supplied in the S1.02 task to create them. Codex must not reconstruct, infer,
summarize, or rewrite missing source material. If any complete source text is
not supplied, S1.02 is blocked. After the canonical files exist, every future
stage must read the repository copies before work.

## Stage discipline

1. Work on one micro-stage only.
2. Do not alter frozen mathematical or trading-semantic rules.
3. Do not introduce features, models, dependencies, optimizations, or
   refactors unless required by the current stage.
4. Write tests before or together with implementation when applicable.
5. Run the exact required tests and verification commands.
6. Stop and escalate any conflict with a frozen semantic specification.

## Commit and review workflow

After implementation:

1. Commit and push the implementation.
2. Create one independent report at
   `docs/devlog/<STAGE>_<short_name>.md` that references the code commit.
3. Update `docs/devlog/INDEX.md` with the report path and review state.
4. Commit and push the report record.
5. Stop after the current stage; never automatically start the next stage.

Once committed as the final report for a stage, its historical factual content
must not be silently rewritten. Project-level review state belongs in
`docs/devlog/INDEX.md`.

## Permanent stage-report contract

Every stage report must be self-contained for Human + ChatGPT audit and use
these sections:

### 1. Stage Identity

- Stage ID
- Stage name
- Agent status
- Date/time
- Branch

### 2. Scope

- Assigned objective
- Explicit in-scope work
- Explicit out-of-scope work
- Acceptance criteria

### 3. Specification Baseline

- Frozen Math Spec SHA256
- Data/Backtest Spec SHA256
- Implementation Spec SHA256
- Implementation Errata SHA256
- Persistence Errata SHA256
- CHANGE_CONTROL SHA256
- SPEC_MANIFEST SHA256
- Normalized config SHA256 when applicable

### 4. Git Baseline

- Base commit SHA
- Branch
- Initial working-tree status
- Expected remote

### 5. Files Changed

Separate added, modified, and deleted files. State why every file changed.

### 6. Implementation Details

- What was implemented
- Important implementation decisions
- APIs, classes, and functions involved when applicable

### 7. Tests and Verification

Include exact commands actually executed and record passed, failed, skipped,
`git diff --check`, and CI results when CI exists. Never claim an unrun test.

### 8. Specification Compliance

Explicitly state whether the stage changed mathematical rules, feature
definitions, market-data semantics, timestamp semantics, execution
assumptions, risk/Edge thresholds, dependencies, scope, or look-ahead exposure.

### 9. Deviations

State `NONE` or provide a complete explicit list.

### 10. Known Limitations / Risks

List unresolved limitations and risks.

### 11. Verification State

Record whether the working tree is clean, local and remote HEAD values, and
whether the code and report commits were pushed.

### 12. Next Proposed Stage

Suggestion only.

Every report must end with:

```text
STOPPING FOR HUMAN / CHATGPT AUDIT.
```
