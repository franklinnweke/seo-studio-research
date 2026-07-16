# SEO Studio Evaluation Harness

This package is the offline-first research execution path. It does not call the product API, discover product `.env` files, or access the DGX during unit tests.

Implemented commands:

```bash
python -m seo_studio_eval preflight --config configs/pilot.toml
python -m seo_studio_eval validate --run-dir runs/<experiment-id>
```

The preflight validates frozen configuration structure, model declarations, dataset paths, licenses, and SHA-256 hashes. The validator checks append-only attempt records against the Pydantic/JSON-schema contract. Live model inventory and experiment execution will be added behind `$davneet-dgx-access`; there are no hidden retries in research mode.

Raw `runs/`, dataset cache files, and private reviewer mappings are ignored by Git.
