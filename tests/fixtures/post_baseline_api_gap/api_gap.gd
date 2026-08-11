extends Node

func _ready() -> void:
	var constants: PackedStringArray = ClassDB.class_get_enum_constants(
		"SpringBoneSimulator3D",
		"BoneDirection",
		true,
	)
	if constants.has("BONE_DIRECTION_PLUS_X"):
		print("REDOT_COMPAT_API_GAP_CONTROL_OK")
		get_tree().quit(0)
		return
	push_error("SpringBoneSimulator3D.BoneDirection is absent from this exact class API")
	get_tree().quit(1)
