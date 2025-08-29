"""Signature patterns for Deadlock offset scanning."""

# Mapping of offset names to (pattern, offset, extra)
SIGNATURES = {
    "local_player_controller": (
        "48 8B 1D ? ? ? ? 48 8B 6C 24",
        3,
        7,
    ),
    "view_matrix": (
        "48 8D ? ? ? ? ? 48 C1 E0 06 48 03 C1 C3",
        3,
        7,
    ),
    "entity_list": (
        "48 8B 0D ?? ?? ?? ?? 48 89 7C 24 ?? 8B FA C1 EB",
        3,
        7,
    ),
    "camera_manager": (
        "48 8D 3D ? ? ? ? 8B D9",
        3,
        7,
    ),
    "schema_system_interface": (
        "48 89 05 ? ? ? ? 4C 8D 0D ? ? ? ? 0F B6 45 E8 4C 8D 45 E0 33 F6",
        3,
        7,
    ),
}
