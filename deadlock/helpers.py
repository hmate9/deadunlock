from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence, Tuple


Vector3 = Tuple[float, float, float]


def calculate_camera_rotation(v1: Vector3, v2: Vector3) -> Tuple[float, float]:
    """Return yaw and pitch in degrees required to look from ``v1`` to ``v2``."""
    dx = v2[0] - v1[0]
    dy = v2[1] - v1[1]
    dz = v2[2] - v1[2]
    yaw = math.degrees(math.atan2(dy, dx))
    pitch = math.degrees(math.atan2(dz, math.hypot(dx, dy)))
    return yaw, pitch


def calculate_new_camera_angles(
    current_yaw: float,
    current_pitch: float,
    desired_yaw: float,
    desired_pitch: float,
    max_change: float,
) -> Tuple[float, float]:
    """Return new yaw and pitch gradually moving towards desired angles."""
    diff_yaw = min(
        desired_yaw - current_yaw,
        desired_yaw - current_yaw + 360,
        desired_yaw - current_yaw - 360,
        key=abs,
    )
    diff_pitch = min(
        desired_pitch - current_pitch,
        desired_pitch - current_pitch + 360,
        desired_pitch - current_pitch - 360,
        key=abs,
    )
    diff_yaw = max(-max_change, min(max_change, diff_yaw))
    diff_pitch = max(-max_change, min(max_change, diff_pitch))
    return current_yaw + diff_yaw, current_pitch + diff_pitch


def world_to_screen(
    view_matrix: Sequence[Sequence[float]],
    pos: Vector3,
    width: int,
    height: int,
) -> Optional[Tuple[int, int]]:
    """Convert ``pos`` from world coordinates to screen coordinates."""
    clip = [
        pos[0] * view_matrix[0][0]
        + pos[1] * view_matrix[0][1]
        + pos[2] * view_matrix[0][2]
        + view_matrix[0][3],
        pos[0] * view_matrix[1][0]
        + pos[1] * view_matrix[1][1]
        + pos[2] * view_matrix[1][2]
        + view_matrix[1][3],
        pos[0] * view_matrix[2][0]
        + pos[1] * view_matrix[2][1]
        + pos[2] * view_matrix[2][2]
        + view_matrix[2][3],
        pos[0] * view_matrix[3][0]
        + pos[1] * view_matrix[3][1]
        + pos[2] * view_matrix[3][2]
        + view_matrix[3][3],
    ]
    if clip[3] < 0.1:
        return None

    ndc_x = clip[0] / clip[3]
    ndc_y = clip[1] / clip[3]
    screen_x = int((ndc_x + 1) * width / 2)
    screen_y = int((1 - ndc_y) * height / 2)
    return screen_x, screen_y
