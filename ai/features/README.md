# Feature Packs

`ai/features/<feature-id>/` stores portable autoresearch process assets for this repository.

Use a feature pack when you need:
- a narrow feature contract;
- explicit change constraints;
- open development checks;
- holdout-only confirmation;
- repeatable baseline -> iteration -> holdout evidence.

Do not move business code into `ai/features/`. Keep product code where the repo already owns it.
