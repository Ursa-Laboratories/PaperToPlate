# Question-first workflow publication check

This update adds the question/deck entry screen, Valency paper exploration,
source-specific RYB preparation and Bradford demonstration design. CubOS
continues to own physical execution, inventory and native validation. The
execution panel ties recorded video and observations to run events.

The supported question-first RYB path uses bounded recipe checks instead of
the independent-review dialog. Free-form extraction and its review rules are
preserved. Offline or recorded setups cannot submit physical runs; setup,
loading, current inventory and duplicate-submission checks still apply.

Verification for this publication:

- Backend suite: 107 passed, 4 optional tests skipped in the main environment.
- Dedicated vision environment: 9 vision tests passed.
- TypeScript and Vite production build passed.
- The frontend test command currently finds no test files; it is not counted
  as a passing test suite.
- Whitespace checks passed.
- Tracked and publishable files were checked for configured private credential
  values and common token/private-key patterns, with no matches.
- `.env`, private Bond OAuth state, runtime data, model weights and video
  exports are excluded. No new video file is included in this update.

Physical evidence is limited to the earlier operator-supervised color-mixture
run described in [the run record](color-run-record.md). No hardware was operated
for these publication checks. Controller completion is not independent volume,
assay or computer-vision error-detection validation.
