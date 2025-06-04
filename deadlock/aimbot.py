from __future__ import annotations

"""Aimbot implementation used by :mod:`deadlock`.

The logic here aims to be straightforward and easy to maintain.  The
``Aimbot`` class exposes a ``run`` loop that continuously reads game
memory via :class:`deadlock.memory.DeadlockMemory` and adjusts the
player camera toward enemy targets.

This module is intentionally platform specific (Windows only) as it
relies on ``win32api`` to query mouse button state.
"""

from dataclasses import dataclass
import random
import time

import win32api

try:
    from .heroes import get_body_bone_index, get_head_bone_index
    from .helpers import calculate_camera_rotation, calculate_new_camera_angles
    from .memory import DeadlockMemory
    from .update_checker import ensure_up_to_date
except ImportError:
    # Fallback for when running directly
    from heroes import get_body_bone_index, get_head_bone_index
    from helpers import calculate_camera_rotation, calculate_new_camera_angles
    from memory import DeadlockMemory


@dataclass
class AimbotSettings:
    """Configuration for :class:`Aimbot`."""

    headshot_probability: float = 0.25
    #: chance to aim at the enemy's head instead of centre mass

    target_select_type: str = "fov"  # "distance" or "fov"
    #: prioritisation strategy when selecting targets

    smooth_speed: float = 5.0
    #: maximum angle change (degrees) per frame when locking on

    grey_talon_lock: float = 0.5
    #: seconds to keep aiming after Grey Talon's ability 1 (``Q``)

    grey_talon_lock_enabled: bool = True
    #: if ``True`` check for Grey Talon's ability 1 key

    grey_talon_key: int = ord("Q")
    #: virtual-key code for Grey Talon's lock trigger

    yamato_lock: float = 1.5
    #: seconds to keep aiming after Yamato's ability 1 (``Q``)

    yamato_lock_enabled: bool = True
    #: if ``True`` check for Yamato's ability 1 key

    yamato_key: int = ord("Q")
    #: virtual-key code for Yamato's lock trigger

    vindicta_lock: float = 0.65
    #: seconds to keep aiming after Vindicta's ability 4 (``R``)

    vindicta_lock_enabled: bool = True
    #: if ``True`` check for Vindicta's ability 4 key

    vindicta_key: int = ord("R")
    #: virtual-key code for Vindicta's lock trigger


class Aimbot:
    """Basic aimbot controller."""
    
    def __init__(self, mem: DeadlockMemory, settings: AimbotSettings | None = None) -> None:
        """Create a new aimbot bound to ``mem``."""

        self.mem = mem
        self.settings = settings or AimbotSettings()
        self.locked_on: int | None = None
        self.force_aim_until: float = 0.0

    def _update_ability_lock(self, hero) -> None:
        """Extend ``force_aim_until`` when ability keys are pressed."""
        now = time.time()
        if hero.name == "GreyTalon" and self.settings.grey_talon_lock_enabled and self.settings.grey_talon_lock > 0:
            if win32api.GetKeyState(self.settings.grey_talon_key) < 0:
                self.force_aim_until = max(self.force_aim_until, now + self.settings.grey_talon_lock)
        elif hero.name == "Yamato" and self.settings.yamato_lock_enabled and self.settings.yamato_lock > 0:
            if win32api.GetKeyState(self.settings.yamato_key) < 0:
                self.force_aim_until = max(self.force_aim_until, now + self.settings.yamato_lock)
        elif hero.name == "Vindicta" and self.settings.vindicta_lock_enabled and self.settings.vindicta_lock > 0:
            if win32api.GetKeyState(self.settings.vindicta_key) < 0:
                self.force_aim_until = max(self.force_aim_until, now + self.settings.vindicta_lock)

    def should_aim_for_head(self) -> bool:
        """Return ``True`` if the bot should attempt a headshot."""

        return random.random() < self.settings.headshot_probability

    def run(self) -> None:
        """Main aimbot loop."""

        while True:
            my_data = self.mem.read_entity(0)
            self._update_ability_lock(my_data["hero"])

            mouse_down = win32api.GetKeyState(0x01) < 0 or time.time() < self.force_aim_until
            if not mouse_down:
                # Left mouse button is not held and no ability lock active
                self.locked_on = None
                time.sleep(0.01)
                continue

            cam_pos = self.mem.camera_position()
            current_yaw, current_pitch = self.mem.current_angles()

            if self.locked_on is None:
                target_idx = None
                best_score = None
                for i in range(1, 16):
                    try:
                        data = self.mem.read_entity(i)
                    except Exception:
                        continue
                    if data["team"] == my_data["team"] or data["health"] <= 0:
                        continue
                    if self.settings.target_select_type == "distance":
                        dx = my_data["position"][0] - data["position"][0]
                        dy = my_data["position"][1] - data["position"][1]
                        dz = my_data["position"][2] - data["position"][2]
                        dist = (dx * dx + dy * dy + dz * dz) ** 0.5
                        if best_score is None or dist < best_score:
                            best_score = dist
                            target_idx = i
                    else:
                        yaw, pitch = calculate_camera_rotation(cam_pos, data["position"])
                        dyaw = min(abs(yaw - current_yaw), abs(yaw - current_yaw + 360), abs(yaw - current_yaw - 360))
                        dpitch = min(abs(-pitch - current_pitch), abs(-pitch - current_pitch + 360), abs(-pitch - current_pitch - 360))
                        score = dyaw + dpitch
                        if best_score is None or score < best_score:
                            best_score = score
                            target_idx = i
                self.locked_on = target_idx

            if self.locked_on is None:
                time.sleep(0.01)
                continue

            try:
                target = self.mem.read_entity(self.locked_on)
            except Exception:
                self.locked_on = None
                continue

            bone_index = (
                get_head_bone_index(target["hero"]) if self.should_aim_for_head() else get_body_bone_index(target["hero"])
            )
            if bone_index is not None:
                bone_array = self.mem.read_longlong(target["node"] + 0x170 + 0x80)
                head_vector = (
                    self.mem.read_float(bone_array + bone_index * 32),
                    self.mem.read_float(bone_array + bone_index * 32 + 4),
                    self.mem.read_float(bone_array + bone_index * 32 + 8),
                )
                target_pos = head_vector
            else:
                target_pos = target["position"]

            # Gradually rotate the camera towards the desired angles for a
            # slightly more human-like movement.
            yaw, pitch = calculate_camera_rotation(cam_pos, target_pos)
            new_yaw, new_pitch = calculate_new_camera_angles(
                current_yaw,
                current_pitch,
                yaw,
                -pitch,
                self.settings.smooth_speed,
            )
            self.mem.set_angles(new_yaw, new_pitch)
            time.sleep(0.001)


def main() -> None:
    ensure_up_to_date()
    mem = DeadlockMemory()
    bot = Aimbot(mem)
    bot.run()


if __name__ == "__main__":
    main()
