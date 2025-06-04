from __future__ import annotations

import random
import time
from dataclasses import dataclass

import win32api

from .heroes import get_body_bone_index, get_head_bone_index
from .helpers import calculate_camera_rotation
from .memory import DeadlockMemory


@dataclass
class AimbotSettings:
    headshot_probability: float = 0.25
    aim_assist_probability: float = 0.8
    target_select_type: str = "fov"  # "distance" or "fov"
    max_angle_change: float = 5.0


class Aimbot:
    def __init__(self, mem: DeadlockMemory, settings: AimbotSettings | None = None) -> None:
        self.mem = mem
        self.settings = settings or AimbotSettings()
        self.locked_on: int | None = None

    def should_aim_for_head(self) -> bool:
        return random.random() < self.settings.headshot_probability

    def run(self) -> None:
        while True:
            cam_pos = self.mem.camera_position()
            current_yaw, current_pitch = self.mem.current_angles()
            my_data = self.mem.read_entity(0)
            if self.locked_on is not None and win32api.GetKeyState(0x01) >= 0:
                self.locked_on = None

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

            yaw, pitch = calculate_camera_rotation(cam_pos, target_pos)
            self.mem.set_angles(yaw, -pitch)
            time.sleep(0.001)


def main() -> None:
    mem = DeadlockMemory()
    bot = Aimbot(mem)
    bot.run()


if __name__ == "__main__":
    main()
