@tool
extends EditorPlugin


func _enter_tree() -> void:
	var constants: PackedStringArray = ClassDB.class_get_enum_constants(
		"SpringBoneSimulator3D",
		"BoneDirection",
		true,
	)
	if not constants.has("BONE_DIRECTION_PLUS_X"):
		push_error("SpringBoneSimulator3D.BoneDirection is absent from this exact class API")
