# Release 1.0.1 — Notes

> Tag **`v1.0.1`** · 2026-06-02 · Follow-up to [1.0.0](https://github.com/livezingy/DocuVision/releases/tag/v1.0.0)

## Scope

- Ship **DocuVision Lite** on `main` (CPU table/OCR track) alongside unchanged Pro KIE baseline.
- Remove confirmed dead code in `docuvision-core` and legacy test assets.
- Document Pro/Lite boundaries; **v1.1** remains reserved for **custom KIE fields MVP**.

## Verify before tag

- [ ] GitHub Actions **CI Lite** green (push with `[run ci]` or PR to `main`).
- [ ] GitHub Actions **KIE Phase A** green.
- [ ] Cloud (optional): Lite §G + Pro §C/D spot-check per [CLOUD_VALIDATION.md](../architecture/CLOUD_VALIDATION.md).

## Not in 1.0.1

- Custom fields / dynamic schema (v1.1).
- Batch Processing UI productization.
- Multi-page PDF KIE strategy.
- Lite demo GIFs (record separately; see [media/README.md](../architecture/media/README.md)).

## Links

- [CHANGELOG.md](../../CHANGELOG.md) — `[1.0.1]`
- [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md)
- [lite-api.md](../architecture/lite-api.md)
