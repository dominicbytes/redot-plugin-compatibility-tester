# Architecture decisions

This document records the architecture decisions for the implemented alpha.

## ADR-0001: Static inspection is the first executable slice

- Date: 2026-08-10
- Status: accepted
- Context: Plugin packages can contain arbitrary scripts, native libraries, hostile archives, and mutable remote references.
- Decision: Resolve immutable source evidence, preflight every archive member, inventory without loading code, and apply the baseline policy before dynamic work.
- Alternatives considered: Start with Redot execution; trust marketplace metadata; load candidate libraries for introspection.
- Consequences: Useful screening works without an engine. Dynamic milestones remain gated by containment and exact engine evidence.

## ADR-0002: Exact engine identities are mandatory

- Date: 2026-08-10
- Status: accepted
- Context: Redot 26.2 has Godot 4.5.2 compatibility lineage, while the retained Godot reference snapshot is 4.5.0.
- Decision: Store product and compatibility versions separately and never substitute a nearby control.
- Alternatives considered: Compare all evidence only to `26.2`; silently use the 4.5.0 reference as a 4.5.2 control.
- Consequences: Differential specificity is available only when an exact matching control is supplied. The local gate used the retained Godot 4.5.2 binary; a nearby reference snapshot is never substituted.

## ADR-0003: `result.json` is authoritative

- Date: 2026-08-10
- Status: accepted
- Context: Independently generated reports can drift into inconsistent conclusions.
- Decision: Version and validate one Pydantic result contract; derive every human view from it.
- Alternatives considered: Treat Markdown as authoritative; compute batch summaries independently.
- Consequences: Schema changes require an explicit migration decision and golden updates.

## ADR-0004: Host execution never satisfies the untrusted sandbox gate

- Date: 2026-08-10
- Status: accepted
- Context: Host execution needs race-free descendant ownership but cannot restrict filesystem/network rights; Docker needs a reproducible hardened profile and deterministic cleanup.
- Decision: `auto` never falls back to host. Host mode requires `--backend host`, `--trusted-source`, and `--allow-unsafe-host-execution`; Windows assigns a waiting launcher to a kill-on-close Job Object before releasing the target. Docker becomes eligible only with a digest-pinned image, expected engine hash, live daemon, fixed restrictions, and controller heartbeat.
- Consequences: Host evidence remains `trusted_host` and scope-limited. Docker evidence is Linux-scoped and materially contained, while hostile native submissions still require stronger VM isolation.

## ADR-0005: Prepare an alpha repository, not a fictitious 1.0 release

- Date: 2026-08-10
- Status: accepted
- Context: Exact control, clean API dumps, Windows/Docker containment, differential classification, and the optional Mono proof are now green locally, while several phase/platform adapters and the full release matrix remain open.
- Decision: Package version stays `0.1.0`; GitHub metadata and dry-run workflows are ready, but no remote, tag, release, or publication is created automatically.
- Consequences: Wheel/sdist/SBOM/checksum work can be verified now without converting blocked evidence into release claims.
