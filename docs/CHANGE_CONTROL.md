# OAE v0.1 Change Control

## Purpose

This document controls changes to the frozen OAE v0.1 baseline and records the
governance-only amendments approved for S1.02. It does not modify any financial,
model, market-data, execution, or backtest semantic.

## Authority hierarchy

1. `docs/specs/00_OAE_v0.1_FROZEN_MATH_SPEC.md` governs financial and model
   mathematics, including features, parameters, trading rules, thresholds,
   gates, payoffs, and acceptance criteria.
2. `docs/specs/01_OAE_v0.1_DATA_BACKTEST_SPEC.md` governs market-data
   definitions, timestamp semantics, point-in-time rules, execution
   assumptions, historical replay, and anti-leakage rules.
3. `docs/specs/02_OAE_v0.1_IMPLEMENTATION_SPEC.md` governs implementation
   architecture and preserves the original development baseline.
4. `AGENTS.md` and this file may amend development governance only. They may
   not change a frozen model, data, trading, execution, or backtest semantic.

If two authorities conflict on a frozen semantic, implementation must stop and
the conflict must be escalated for Human + ChatGPT architectural review. An
Agent must not silently select or synthesize a resolution.

## Frozen change flow

```text
FROZEN SPEC
    ↓
Implementation
    ↓
Tests
    ↓
Observed Problem
    ↓
Human Review
    ↓
Decision
    ├── implementation bug -> fix under v0.1
    └── mathematical/semantic rule change -> create v0.2
```

Test or backtest results must never justify silently changing a specification.

## Frozen semantic boundary

Governance amendments must not modify:

- financial mathematics or feature formulas;
- model class or parameters;
- trading universe or strategy construction;
- market-data or timestamp semantics;
- execution pricing or fees;
- Edge, risk, model-health, OOD, or ambiguity thresholds;
- No-Trade logic;
- walk-forward, anti-leakage, settlement, or backtest semantics.

A proposed change to any item above is not a governance correction. It requires
OAE v0.2 or explicit Human + ChatGPT architectural review and versioning.

## S1.02 governance amendments and precedence

S1.02 supersedes only conflicting development-governance mechanics in the
original Implementation Specification:

1. `docs/devlog/INDEX.md` uses `Stage | Agent Status | Code SHA | Report |
   Review`. It does not store a self-referential audit-commit SHA.
2. Each micro-stage has one immutable, independent report under `docs/devlog/`.
   Review status is maintained in `docs/devlog/INDEX.md` rather than by
   rewriting historical report facts.
3. The canonical specification identity is
   `docs/specs/SPEC_MANIFEST.sha256` plus the SHA-256 of that manifest.
4. S1.02 has the narrow bootstrap exception documented in `AGENTS.md`. Once the
   repository copies exist, all future stages must read and verify them.

These amendments do not supersede financial mathematics, market-data
semantics, timestamps, execution assumptions, risk gates, or backtest rules.
The original canonical specification documents remain preserved verbatim so
the historical baseline remains auditable.

## Specification identity

`docs/specs/SPEC_MANIFEST.sha256` contains actual-byte SHA-256 values for
exactly:

- `docs/specs/00_OAE_v0.1_FROZEN_MATH_SPEC.md`
- `docs/specs/01_OAE_v0.1_DATA_BACKTEST_SPEC.md`
- `docs/specs/02_OAE_v0.1_IMPLEMENTATION_SPEC.md`
- `docs/CHANGE_CONTROL.md`

Every future stage report must record each of these hashes and the SHA-256 of
the manifest itself. The frozen config SHA-256 must also be recorded once that
config exists.

Changing a frozen specification requires the applicable version-control rule.
An approved governance-only edit to this file or `AGENTS.md` must be explicit,
auditable, and accompanied by a regenerated and verified manifest when a
manifest-listed file changes.

## Enforcement

- Never change `k`, thresholds, features, strikes, execution assumptions,
  fees, timestamps, or model-health ranges because results are unfavorable.
- Never modify a frozen rule merely to make a test pass.
- Fix implementation bugs only by restoring compliance with the applicable
  canonical specification.
- Stop and escalate before implementing any unresolved semantic conflict.
