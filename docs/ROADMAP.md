# Roadmap

BrandGuard is currently a local judging and review tool. Future work should preserve the deterministic offline path and keep human decisions in control.

## Next reliability work

- Add database backup and restore commands, with a documented way to include uploaded media and the retrieval index.
- Add durable background-job state and restart recovery before introducing multi-process operation.
- Track approved documents affected when a cited fact expires or changes, with duplicate-safe alerts and a reviewed recheck flow.
- Expand supported file-layout fixtures and evaluate OCR and PDF coordinates on more operating systems and accessibility cases.
- Improve the English writing rules with a larger reviewed test corpus before adding broader language support.

## Hosted deployment, if needed later

Hosted use would need a new threat model and deployment design: tenant isolation, managed secrets, durable job workers, object storage, database backups, provider-data controls, and rate limits shared across instances. The removed Render and container configuration should not be restored until those requirements are designed and tested.

## Collaboration and integrations

- Consider optional external review links only after token lifecycle, abuse controls, audit events, and data-retention behavior are fully tested.
- Add integrations only with explicit user consent and clear disclosure of which content and metadata leave the local workspace.
