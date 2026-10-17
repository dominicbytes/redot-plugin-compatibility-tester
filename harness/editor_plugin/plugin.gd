@tool
extends EditorPlugin

const SENTINEL_PREFIX: String = "REDOT_COMPAT_EVENT "

var _sequence: int = 0
var _run_id: String = "unconfigured-run"
var _session_key: String = ""
var _config: Dictionary = {}


func _enter_tree() -> void:
	_config = _read_config()
	_emit_event("start", {"harness": "editor"})
	call_deferred("_run_phase")


func _run_phase() -> void:
	if _config.is_empty():
		_finish("error", "invalid_harness_config")
		return
	var editor: EditorInterface = get_editor_interface()
	var file_system: EditorFileSystem = editor.get_resource_filesystem()
	if not await _wait_for_scan(file_system):
		_finish("error", "scan_did_not_finish")
		return
	if _config.get("mode") == "import":
		_finish("pass", "scan_complete")
		return
	var plugin_id: String = str(_config.get("plugin_id", ""))
	if plugin_id.is_empty() or not plugin_id.is_valid_filename():
		_finish("error", "missing_or_invalid_plugin_id")
		return
	var plugin_path: String = "res://addons/%s/plugin.cfg" % plugin_id
	if not FileAccess.file_exists(plugin_path):
		_finish("error", "plugin_cfg_missing")
		return
	editor.set_plugin_enabled(plugin_path, true)
	if not await _wait_for_scan(file_system):
		_finish("error", "scan_did_not_finish")
		return
	_finish("pass" if editor.is_plugin_enabled(plugin_path) else "fail", "activation_check")


func _wait_for_scan(file_system: EditorFileSystem) -> bool:
	for _frame: int in range(600):
		await get_tree().process_frame
		if not file_system.is_scanning():
			return true
	return false


func _finish(event_name: String, reason: String) -> void:
	_emit_event(event_name, {"reason": reason})
	get_tree().quit(0 if event_name == "pass" else 2 if event_name == "error" else 1)


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
