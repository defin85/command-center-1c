# refactor-14 acceptance evidence and cutover templates

This directory contains two checked-in evidence classes for workflow-centric hardening.

- `repository-acceptance-evidence.md` is the checked-in repository acceptance evidence for the
  shipped default path.
- `*.template.json` files are checked-in templates/examples for operator evidence capture during
  tenant-scoped cutover. They are not production rollout evidence.

Usage:
- use `repository-acceptance-evidence.md` when you need the canonical in-repo proof path for
  shipped behavior;
- copy a template next to your working evidence bundle;
- replace placeholder values with real tenant/pool/run data;
- attach screenshots, API responses, or log refs in `evidence_refs`;
- keep the original templates unchanged in git.

Repository evidence:
- `repository-acceptance-evidence.md`

Templates:
- `shared-metadata-evidence.template.json`
- `legacy-document-policy-migration-evidence.template.json`
- `operator-canary-evidence.template.json`
