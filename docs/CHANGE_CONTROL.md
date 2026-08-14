# OAE v0.1 Change Control

## Purpose

This document controls changes to the frozen OAE v0.1 baseline, records the
governance-only amendments approved for S1.02, and recognizes the narrow
implementation-consistency errata approved for S1.03B. It does not modify any
financial, model, market-data, execution, or backtest semantic.

## Authority hierarchy

1. `docs/specs/00_OAE_v0.1_FROZEN_MATH_SPEC.md` governs financial and model
   mathematics, including features, parameters, trading rules, thresholds,
   gates, payoffs, and acceptance criteria.
2. `docs/specs/01_OAE_v0.1_DATA_BACKTEST_SPEC.md` governs market-data
   definitions, timestamp semantics, point-in-time rules, execution
   assumptions, historical replay, and anti-leakage rules.
3. `docs/specs/03_OAE_v0.1_IMPLEMENTATION_ERRATA.md` has narrow authority only
   over the explicit implementation inconsistencies enumerated in that errata.
4. `docs/specs/02_OAE_v0.1_IMPLEMENTATION_SPEC.md` governs all implementation
   architecture not superseded by an explicit erratum and preserves the
   original development baseline.
5. `AGENTS.md` and this file may amend development governance only. They may
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

## S1.03B implementation errata and precedence

The S1.03B Implementation Errata is a v0.1 consistency repair approved by
Human + ChatGPT. It does not constitute OAE v0.2 because it changes no frozen
financial, model, market-data, execution, timestamp, trading, or backtest
semantic.

Its authority is limited to the exact discrepancies it enumerates:

- complete implementation structure for the already-frozen configuration in
  Data/Backtest Specification section 76;
- the explicitly listed raw/core market-data fields omitted from examples in
  Implementation Specification sections 10 and 28.

The Data/Backtest Specification retains authority over the already-frozen
market-data and backtest semantics. The Implementation Specification remains
authoritative for implementation architecture wherever the errata does not
explicitly supersede it. The errata creates no broad rule that one
specification always overrides another.

Any unlisted conflict requires implementation to stop and escalate to Human +
ChatGPT. An Agent must not infer a precedence rule from the S1.03B repair.

## Specification identity

`docs/specs/SPEC_MANIFEST.sha256` contains actual-byte SHA-256 values for
exactly:

- `docs/specs/00_OAE_v0.1_FROZEN_MATH_SPEC.md`
- `docs/specs/01_OAE_v0.1_DATA_BACKTEST_SPEC.md`
- `docs/specs/02_OAE_v0.1_IMPLEMENTATION_SPEC.md`
- `docs/specs/03_OAE_v0.1_IMPLEMENTATION_ERRATA.md`
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
