# Declarative plugin test manifest

`plugin-test.toml` selects one plugin ID, unique supported phases, a timeout from 1–600 seconds, and at most 128 declarative probes. Unknown fields are rejected.

Supported probes:

- `class_exists`: compares `ClassDB.class_exists(value)` with `expected`.
- `resource_exists`: requires a non-escaping `res://` path and compares `ResourceLoader.exists(value)`.
- `node_exists`: requires a safe relative NodePath and checks the generated harness tree.

The manifest cannot express arbitrary scripts, commands, environment values, network requests, clicks, or shell fragments. `import`, `editor`, and `runtime` are implemented for the trusted-host alpha. Other accepted future phases return explicit missing-capability evidence instead of running a substitute.

See [examples/plugin-test.toml](../examples/plugin-test.toml) and [manifest.schema.json](../schemas/manifest.schema.json).
