extends SceneTree

const SENTINEL_PREFIX: String = "REDOT_COMPAT_EVENT "
const DEFAULT_RUN_ID: String = "unconfigured-run"

var _sequence: int = 0
var _run_id: String = DEFAULT_RUN_ID


func _initialize() -> void:
	_run_id = OS.get_environment("REDOT_COMPAT_RUN_ID")
	if _run_id.is_empty():
		_run_id = DEFAULT_RUN_ID
	_emit_event("start", {"harness": "runtime"})
	var config_path: String = OS.get_environment("REDOT_COMPAT_HARNESS_JSON")
	var config: Dictionary = {}
	if not config_path.is_empty():
		config = _read_config(config_path)
		if config.is_empty():
			_emit_event("error", {"reason": "invalid_harness_config"})
			quit(2)
			return
	var probes_value: Variant = config.get("probes", [])
	if not probes_value is Array:
		_emit_event("error", {"reason": "probes_must_be_array"})
		quit(2)
		return
	var passed: bool = true
	for probe_value: Variant in probes_value:
		if not probe_value is Dictionary:
			passed = false
			_emit_event("probe", {"passed": false, "reason": "probe_must_be_object"})
			continue
		var probe: Dictionary = probe_value as Dictionary
		var probe_passed: bool = _run_probe(probe)
		passed = passed and probe_passed
		_emit_event("probe", {"type": probe.get("type", ""), "passed": probe_passed})
	_emit_event("pass" if passed else "fail", {"probe_count": probes_value.size()})
	quit(0 if passed else 1)


func _read_config(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not parsed is Dictionary:
		return {}
	return parsed as Dictionary


func _run_probe(probe: Dictionary) -> bool:
	var probe_type: String = str(probe.get("type", ""))
	var value: String = str(probe.get("value", ""))
	var expected: bool = bool(probe.get("expected", true))
	var observed: bool = false
	match probe_type:
		"class_exists":
			observed = ClassDB.class_exists(value)
		"resource_exists":
			observed = ResourceLoader.exists(value)
		"node_exists":
			observed = root.get_node_or_null(NodePath(value)) != null
		_:
			return false
	return observed == expected


func _emit_event(event_name: String, payload: Dictionary) -> void:
	var event: Dictionary = {
		"schema": 1,
		"run_id": _run_id,
		"sequence": _sequence,
		"event": event_name,
		"payload": payload,
	}
	_sequence += 1
	print(SENTINEL_PREFIX + JSON.stringify(event))
