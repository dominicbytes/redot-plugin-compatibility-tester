@tool
extends EditorPlugin

const SENTINEL_PREFIX: String = "REDOT_COMPAT_EVENT "

var _sequence: int = 0
var _run_id: String = "unconfigured-run"


func _enter_tree() -> void:
	_run_id = OS.get_environment("REDOT_COMPAT_RUN_ID")
	if _run_id.is_empty():
		_run_id = "unconfigured-run"
	_emit_event("start", {"harness": "editor"})
	call_deferred("_activate_selected_plugin")


func _activate_selected_plugin() -> void:
	var plugin_id: String = OS.get_environment("REDOT_COMPAT_PLUGIN_ID")
	if plugin_id.is_empty() or not plugin_id.is_valid_filename():
		_finish(false, "missing_or_invalid_plugin_id")
		return
	var plugin_path: String = "res://addons/%s/plugin.cfg" % plugin_id
	if not FileAccess.file_exists(plugin_path):
		_finish(false, "plugin_cfg_missing")
		return
	var editor: EditorInterface = get_editor_interface()
	editor.set_plugin_enabled(plugin_path, true)
	var file_system: EditorFileSystem = editor.get_resource_filesystem()
	for _frame: int in range(30):
		await get_tree().process_frame
		if not file_system.is_scanning():
			break
	_finish(editor.is_plugin_enabled(plugin_path), "activation_check")


func _finish(passed: bool, reason: String) -> void:
	_emit_event("pass" if passed else "fail", {"reason": reason})
	get_tree().quit(0 if passed else 1)


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
