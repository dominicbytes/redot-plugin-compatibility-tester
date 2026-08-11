# Engine API reference snapshots


This directory contains upstream API reference snapshots for schema/index development. These files do not replace freshly generated exact-engine snapshots.

## Machine-readable API material

| File | Provenance | SHA-256 | Use and limits |
|---|---|---|---|
| `redot-26.2-extension-api.json` | [`Redot-Engine/redot-cpp`, tag `redot-26.2-stable`](https://raw.githubusercontent.com/Redot-Engine/redot-cpp/redot-26.2-stable/gdextension/extension_api.json), tag commit `598ec78e86b2c240a023f6de13daba70f7de8610` | `453A0CC128BB58333A001F7F43573A5961D973FB7B151AF43139869F22D5915C` | Authoritative tagged Redot 26.2 binding input. Header reports Godot API `4.5.2`, single precision, `redot.custom_build`. Suitable for schema/index development and comparison fixtures. It does not prove that the locally configured editor can regenerate the dump. |
| `godot-4.5-extension-api.json` | [`godotengine/godot-cpp`, tag `godot-4.5-stable`](https://raw.githubusercontent.com/godotengine/godot-cpp/godot-4.5-stable/gdextension/extension_api.json), tag commit `e83fd0904c13356ed1d4c3d09f8bb9132bdc6b77` | `23D807E3F914F7A91B152A8A7B03638D4853F8E642B79F10CE85A43B44340BFD` | Godot 4.5.0 stable reference material only. It is not a substitute for a freshly generated Godot 4.5.2 control snapshot and must not be labeled as one. |

Both repositories identify their code as MIT-licensed. Preserve upstream attribution when redistributing the snapshots.




