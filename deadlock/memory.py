from __future__ import annotations

"""Thin wrapper over :mod:`pymem` for reading Deadlock game memory."""

from dataclasses import dataclass
from typing import Dict, Tuple, Optional

import pymem

from .heroes import HeroIds
from .helpers import Vector3
from . import mem_offsets as mo
import offset_finder

# Pattern to locate the glow check conditional in client.dll
GLOW_PATTERN = bytes.fromhex(
    "0F 85 70 02 00 00 44 0F 11 54 24 58 C7 44 24 68 FF FF 7F FF "
    "48 8B CB C7 44 24 6C FF FF 7F FF 48"
)
GLOW_PATCH = b"\x90" * 6
GLOW_ORIGINAL = bytes.fromhex("0F 85 70 02 00 00")


@dataclass
class Offsets:
    local_player_controller: int
    view_matrix: int
    entity_list: int
    camera_manager: int
    schema_system_interface: int


class DeadlockMemory:
    """Small wrapper around ``pymem`` with dynamic offsets."""

    def __init__(self, process: str = "deadlock.exe") -> None:
        """Open the game process and locate dynamic offsets."""

        self.process_name = process
        self.pm = pymem.Pymem(process)
        self.client_base = pymem.process.module_from_name(
            self.pm.process_handle, "client.dll"
        ).lpBaseOfDll
        self.offsets = self._read_offsets()
        self._glow_addr: Optional[int] = None
        self._glow_original: bytes | None = None

    def _read_offsets(self) -> Offsets:
        """Read offsets via :mod:`offset_finder`."""

        offs = offset_finder.find_offsets(self.process_name)
        return Offsets(**offs)

    # Memory helpers -----------------------------------------------------
    def read_int(self, address: int) -> int:
        return self.pm.read_int(address)

    def read_float(self, address: int) -> float:
        return self.pm.read_float(address)

    def read_longlong(self, address: int) -> int:
        return self.pm.read_longlong(address)

    def write_float(self, address: int, value: float) -> None:
        self.pm.write_float(address, value)

    # Game specific helpers ---------------------------------------------
    @property
    def entity_list(self) -> int:
        return self.read_longlong(self.client_base + self.offsets.entity_list)

    @property
    def local_controller(self) -> int:
        return self.read_longlong(
            self.client_base + self.offsets.local_player_controller
        )

    @property
    def camera(self) -> int:
        return self.read_longlong(
            self.client_base + self.offsets.camera_manager + mo.CAMERA_PTR_OFFSET
        )

    def camera_position(self) -> Vector3:
        cam = self.camera
        return (
            self.read_float(cam + mo.CAMERA_POS_X),
            self.read_float(cam + mo.CAMERA_POS_Y),
            self.read_float(cam + mo.CAMERA_POS_Z),
        )

    def current_angles(self) -> Tuple[float, float]:
        cam = self.camera
        return self.read_float(cam + mo.CAMERA_YAW), self.read_float(
            cam + mo.CAMERA_PITCH
        )

    def set_angles(self, yaw: float, pitch: float, aim_angle: float = 0.0) -> None:
        cam = self.camera
        self.write_float(cam + mo.CAMERA_YAW, yaw)
        self.write_float(
            cam + mo.CAMERA_PITCH, pitch - aim_angle
        )  # Subtract aim_angle for recoil compensation
        self.write_float(cam + mo.CAMERA_ROLL, 0.0)

    def get_entity_base(self, index: int) -> Tuple[int, int]:
        """Return controller and pawn addresses for entity ``index``."""

        entity_list = self.entity_list
        address_base = self.read_longlong(entity_list + 0x8 * ((index & 0x7FFF) >> 0x9) + 0x10)
        controller_base = self.read_longlong(address_base + 120 * (index & 0x1FF))
        if index == 0:
            controller_base = self.local_controller
        pawn_handle = self.read_longlong(controller_base + 0x6ac) # C_BasePlayerController -> m_hPawn
        list_entry = self.read_longlong(entity_list + 0x8 * ((pawn_handle & 0x7FFF) >> 0x9) + 0x10)
        pawn = self.read_longlong(list_entry + 0x78 * (pawn_handle & 0x1FF))
        return controller_base, pawn

    def read_entity(self, index: int) -> Dict:
        """Return a dict describing the entity at ``index``."""

        controller_base, pawn = self.get_entity_base(index)
        hero_id = HeroIds(self.read_int(controller_base + mo.HERO_ID_OFFSET))
        game_scene_node = self.read_longlong(pawn + mo.GAME_SCENE_NODE)
        pos_addr = game_scene_node + mo.NODE_POSITION
        pos = (
            self.read_float(pos_addr),
            self.read_float(pos_addr + 4),
            self.read_float(pos_addr + 8) + 70,
        )
        team = self.read_int(controller_base + mo.TEAM_OFFSET)
        health = self.read_int(pawn + mo.HEALTH_OFFSET)
        
        # Get aim angle for local player (index 0) - for recoil compensation
        aim_angle = 0.0
        if index == 0:
            try:
                camera_services = self.read_longlong(
                    pawn + mo.CAMERA_SERVICES
                )  # C_BasePlayerPawn + CPlayer_CameraServices
                aim_angle = self.read_float(
                    camera_services + mo.PUNCH_ANGLE
                )  # m_vecPunchAngle
            except:
                aim_angle = 0.0
        
        return {
            "controller": controller_base,
            "pawn": pawn,
            "team": team,
            "health": health,
            "position": pos,
            "node": game_scene_node,
            "hero": hero_id,
            "aim_angle": aim_angle,
        }

    # Glow override -----------------------------------------------------
    def _find_glow_address(self) -> Optional[int]:
        module = pymem.process.module_from_name(
            self.pm.process_handle, "client.dll"
        )
        data = self.pm.read_bytes(module.lpBaseOfDll, module.SizeOfImage)
        idx = data.find(GLOW_PATTERN)
        if idx == -1:
            return None
        return module.lpBaseOfDll + idx

    def toggle_glow_override(self, enable: bool) -> bool:
        """Enable or disable the glow check NOP patch."""

        if self._glow_addr is None:
            self._glow_addr = self._find_glow_address()
            if self._glow_addr is None:
                return False

        if self._glow_original is None:
            try:
                self._glow_original = self.pm.read_bytes(self._glow_addr, len(GLOW_PATCH))
            except pymem.exception.MemoryReadError as e:
                print(f"Failed to read glow bytes: {e}")
                self._glow_original = None
        patch = GLOW_PATCH if enable else self._glow_original
        self.pm.write_bytes(self._glow_addr, patch, len(patch))
        return True
