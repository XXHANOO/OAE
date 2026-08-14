# OAE Agent Contract

Before any work:

1. Read:
   docs/specs/00_OAE_v0.1_FROZEN_MATH_SPEC.md
   docs/specs/01_OAE_v0.1_DATA_BACKTEST_SPEC.md
   docs/specs/02_OAE_v0.1_IMPLEMENTATION_SPEC.md
   docs/CHANGE_CONTROL.md

2. Work on ONE micro-stage only.

3. Do not alter frozen mathematical rules.

4. Do not introduce additional features, models, dependencies,
   optimizations, or refactors unless required by the current stage.

5. Write tests before or together with implementation.

6. Run the exact required tests before completion.

7. After implementation:
   - write the stage development log;
   - commit code;
   - push;
   - commit the audit log referencing the code commit;
   - push again.

8. STOP after the current stage.
   Never automatically start the next stage.

9. Report:
   - files changed;
   - tests executed;
   - test results;
   - known limitations;
   - deviations from spec;
   - code commit SHA;
   - audit commit SHA.

Any conflict with the frozen specification must stop development
and be escalated for human review.
