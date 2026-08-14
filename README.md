# Options Alpha Engine

Options Alpha Engine (OAE) v0.1 is a research system for a frozen,
point-in-time options strategy baseline.

## Status

The repository is currently at micro-stage **S1.01 — Repository Bootstrap**.
Only the project skeleton and its bootstrap verification exist at this stage.

## Frozen baseline

The OAE v0.1 mathematical rules are frozen. Implementation work must not
silently change strategy mathematics, data timing, execution assumptions, or
acceptance thresholds. Any mathematical change requires human review and a new
system version.

## Development workflow

Development takes place on `dev/oae-v0.1`, one micro-stage at a time:

1. Implement the assigned scope and its tests.
2. Run the required verification.
3. Commit and push the implementation.
4. Record the implementation in the stage development log.
5. Commit and push the audit record.
6. Stop for human review.

Later-stage specifications, configuration, database schemas, market-data
logic, feature calculations, models, and backtesting code are intentionally
absent from S1.01.
