extends SceneTree

const SENTINEL_PREFIX: String = "REDOT_COMPAT_EVENT "

var _sequence: int = 0
var _run_id: String = "unconfigured-run"
var _session_key: String = ""


func _initialize() -> void:
	var config: Dictionary = _read_config()
	_emit_event("start", {"harness": "runtime"})
	if config.is_empty():
		_emit_event("error", {"reason": "invalid_harness_config"})
		quit(2)
		return
	var probes: Array = config.get("probes", [])
	if config.get("mode") == "canary":
		probes = []
	var passed: bool = true
	for probe_value: Variant in probes:
		if not probe_value is Dictionary:
			_emit_event("error", {"reason": "probe_must_be_object"})
			quit(2)
			return
		var probe: Dictionary = probe_value as Dictionary
		var probe_passed: bool = _run_probe(probe)
		passed = passed and probe_passed
		_emit_event("probe", {"type": probe.get("type", ""), "passed": probe_passed})
	_emit_event("pass" if passed else "fail", {"probe_count": probes.size()})
	quit(0 if passed else 1)


func _read_config() -> Dictionary:
	var path: String = OS.get_environment("REDOT_COMPAT_HARNESS_JSON")
	if path.is_empty() or not FileAccess.file_exists(path):
		return {}
	var text: String = FileAccess.get_file_as_string(path)
	DirAccess.remove_absolute(path)
	var parsed: Variant = JSON.parse_string(text)
	if not parsed is Dictionary:
		return {}
	var config: Dictionary = parsed as Dictionary
	_run_id = str(config.get("run_id", "unconfigured-run"))
	_session_key = str(config.get("session_key", ""))
	if _session_key.length() != 64 or _session_key.hex_decode().size() != 32:
		return {}
	if not config.get("probes") is Array:
		return {}
	if not str(config.get("mode", "")) in ["import", "activate", "canary"]:
		return {}
	return config


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
		"schema": 2,
		"run_id": _run_id,
		"sequence": _sequence,
		"event": event_name,
		"payload": payload,
	}
	_sequence += 1
	var body: String = JSON.stringify(event)
	var signature: String = Crypto.new().hmac_digest(
		HashingContext.HASH_SHA256, _session_key.hex_decode(), body.to_utf8_buffer()
	).hex_encode()
	print(SENTINEL_PREFIX + signature + " " + body)
