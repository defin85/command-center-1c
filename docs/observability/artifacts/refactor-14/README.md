# refactor-14 cutover evidence templates

These files are checked-in templates/examples for operator evidence capture during
workflow-centric cutover. They are not production rollout evidence.

Usage:
- copy a template next to your working evidence bundle;
- replace placeholder values with real tenant/pool/run data;
- attach screenshots, API responses, or log refs in `evidence_refs`;
- keep the original templates unchanged in git.

Templates:
- `shared-metadata-evidence.template.json`
- `legacy-document-policy-migration-evidence.template.json`
- `operator-canary-evidence.template.json`
