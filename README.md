# Redot Plugin Compatibility Tester

`redot-compat` is an offline-first command-line tool for gathering reproducible evidence about whether a Godot plugin needs work for Redot. It safely inventories packages before any code is allowed to execute, preserves source and engine identities, and produces a versioned `result.json` plus human-readable reports.

> [!WARNING]
> Plugin scripts and native libraries are arbitrary code. Static `inspect` never executes them. Docker execution requires an explicitly configured digest-pinned worker; trusted host execution separately requires source trust and operator consent. Docker reduces risk but is not a universal security boundary.

## Status

This repository is an alpha implementation prepared for `dominicbytes/redot-plugin-compatibility-tester`. Safe static inspection, a hardened Linux worker, bounded trusted-host phases, deterministic Redot/API evidence, an optional exact Godot 4.5.2 control, declarative probes, classification/reports, and resumable static batches are implemented. The full export/native/platform matrix and version 1.0 audit remain future work; see [BLOCKERS.md](BLOCKERS.md).

The project baseline is Godot `4.5.2`. `NO_PORT_NEEDED_BASELINE_POLICY` means authoritative evidence places the target at or below that baseline and dynamic testing was skipped by policy. It **does not prove runtime compatibility**.

## Architecture

```text
source -> immutable provenance -> safe extraction -> static inventory
       -> baseline policy -> gated disposable worker -> engine phases
       -> deterministic classifier -> result.json -> derived reports
```

Python owns acquisition, policy, process control, and reporting. Tiny typed GDScript harnesses perform only generated engine-context probes. `result.json` is authoritative.

## Install for development

Requirements: Python 3.12 or newer and [uv](https://docs.astral.sh/uv/).

```console
uv sync --frozen
uv run redot-compat version
uv run redot-compat schema export --check
```

Run the quality gate:

```console
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest -q
```

## First static inspection

```console
uv run redot-compat inspect ./path/to/plugin --output ./reports/example
```

The command never imports Python modules from the package, loads native libraries, invokes Redot, or runs plugin scripts. See [classifications](docs/classifications.md), [security](SECURITY.md), and [troubleshooting](docs/troubleshooting.md).

## Dynamic testing

Dynamic commands require an eligible backend. Host mode is for explicitly trusted fixtures only and requires both trust/consent flags. It isolates engine state, bounds logs and time, and uses a kill-on-close Windows Job Object, but it is not a filesystem or network sandbox. Docker mode requires both a digest-pinned image identity and the expected engine hash; it never silently falls back to host. See [sandboxing](docs/sandboxing.md).

```console
uv run redot-compat doctor --redot /exact/path/to/redot --output reports/doctor
uv run redot-compat test ./trusted-plugin \
  --force-test-baseline \
  --backend host \
  --trusted-source \
  --allow-unsafe-host-execution \
  --redot /exact/path/to/redot \
  --manifest examples/plugin-test.toml \
  --output reports/trusted-test
```

Use an exact control for matched host phases:

```console
uv run redot-compat test ./trusted-plugin \
  --backend host --trusted-source --allow-unsafe-host-execution \
  --redot /exact/path/to/redot \
  --godot-control /exact/path/to/godot-4.5.2 \
  --manifest examples/plugin-test.toml \
  --output reports/differential-test
```

Use a locally built or pulled worker only by immutable identity:

```console
uv run redot-compat test ./plugin \
  --backend docker \
  --worker-image registry.example/redot-compat-worker@sha256:<image-digest> \
  --worker-engine-sha256 <sha256-of-/opt/redot/redot> \
  --manifest examples/plugin-test.toml \
  --output reports/docker-test
```

`plugin-test.toml` is declarative: it selects supported phases and bounded class/resource/node existence probes; it cannot contain commands or code strings. See [manifest documentation](docs/manifest.md).

## Engine API evidence

```console
uv run redot-compat api snapshot /exact/path/to/engine \
  --product redot --output reports/redot-api
uv run redot-compat api index extension_api.json --output api-index.json
uv run redot-compat api diff exact-control.json redot.json --output api-diff.json
```

The exact Redot 26.2 and Godot 4.5.2 snapshots used to close G-02 were generated twice from isolated state and agreed byte-for-byte; local identities are recorded in [gate closure evidence](docs/gamedev/references/gate-closure-evidence.md).

## Sources and batches

Local directories and archives are the first source forms. HTTPS, GitHub, and Codeberg adapters resolve immutable identities before caching bytes. Marketplace metadata remains corroborating evidence.

```console
uv run redot-compat inspect https://github.com/owner/repository --ref v1.2.3
uv run redot-compat batch examples/plugins.toml
```

Each completed inspection writes `result.json` (authoritative), `report.md`, `codex_port_brief.md`, `reproduce.ps1`, and `reproduce.sh`. Dynamic results also embed a portable JSON probe manifest.

## GitHub repository preparation

The repository includes an MIT license, community files, pinned read-only quality workflows, a manual trusted-engine workflow, and a non-publishing release dry run. To create the remote later, review [GitHub release preparation](docs/github-release.md). No remote creation or publication is performed by this checkout.

## Project records

- [Implementation plan](docs/gamedev/implementation-plan.md)
- [Preflight report](docs/gamedev/preflight-report.md)
- [Security policy](SECURITY.md)
- [Contributing guide](CONTRIBUTING.md)
- [Changelog](CHANGELOG.md)
- [Support](SUPPORT.md)
- [Alpha release evidence](docs/release/README.md)

## License

MIT. The bundled Redot and Godot API snapshots retain their upstream attribution and licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).

## Notes

I vibe coded this in GPT Sol 5.6. Use at your own risk. Actual programmers are welcome to submit PR's and feedback.

## About Dominic Bytes

Greetings! I am Dominic Bytes, the synth walker. I hail from the distant future. Where brains occupy robot bodies, time travel is a trip to the corner store, and the neon glow of our attire is powered by the light of our souls. Join me on a 1.21 gigawatt powered journey of chill vibes with gaming, anime, movies, and more!

- [Website](https://dominicbytes.carrd.co/)
- [X](https://x.com/DominicBytes)
- [Twitch](https://www.twitch.tv/dominicbytes)
- [YouTube](http://www.youtube.com/@DominicBytes)
- [Kick](https://kick.com/dominicbytes)
