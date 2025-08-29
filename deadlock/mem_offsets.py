"""Memory offsets and helper constants for Deadlock."""

# Relative pointer offsets
CAMERA_PTR_OFFSET = 0x28  # client.dll -> camera_manager -> camera pointer
CAMERA_POS_X = 0x38  # camera base -> X coordinate
CAMERA_POS_Y = 0x3C  # camera base -> Y coordinate
CAMERA_POS_Z = 0x40  # camera base -> Z coordinate
CAMERA_YAW = 0x48     # camera base -> yaw
CAMERA_PITCH = 0x44   # camera base -> pitch
CAMERA_ROLL = 0x4C    # camera base -> roll (unused)

# Entity offsets
HERO_ID_OFFSET = 0x8b8 + 0x1C  # m_PlayerDataGlobal -> m_heroID
GAME_SCENE_NODE = 0x330  # pawn -> CGameSceneNode pointer
NODE_POSITION = 0xD0     # CGameSceneNode -> position vector
TEAM_OFFSET = 0x3F3      # controller -> team id
HEALTH_OFFSET = 0x354    # pawn -> health
CAMERA_SERVICES = 0xf68  # pawn -> CPlayer_CameraServices
PUNCH_ANGLE = 0x40       # CPlayer_CameraServices -> m_vecPunchAngle

# Skeleton offsets
BONE_ARRAY = 0x210      # # game scene node -> skeleton base -> bone array pointer
BONE_STEP = 32         # bone struct size in bytes
