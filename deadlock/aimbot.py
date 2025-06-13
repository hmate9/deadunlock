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
import logging
import argparse
import ctypes

import win32api
import win32con

try:
    from .heroes import get_body_bone_index, get_head_bone_index
    from .helpers import calculate_camera_rotation, calculate_new_camera_angles
    from .memory import DeadlockMemory
    from . import mem_offsets as mo
    from .update_checker import ensure_up_to_date
except ImportError:
    # Fallback for when running directly
    from heroes import get_body_bone_index, get_head_bone_index
    from helpers import calculate_camera_rotation, calculate_new_camera_angles
    from memory import DeadlockMemory
    import mem_offsets as mo

logger = logging.getLogger(__name__)


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

    paradox_shortcut_enabled: bool = True
    #: if ``True`` trigger Paradox ability combo

    paradox_r_key: int = ord("R")
    #: key that initiates Paradox combo

    paradox_e_key: int = ord("E")
    #: key automatically pressed after ``paradox_r_key``

    headshot_on_acquire: bool = True
    #: force headshots for 0.4s when locking on after a 2s gap

    aimbot_button: int = 0x01
    #: virtual-key code that activates the aimbot while held

    fire_only_button: int = 0x02
    #: virtual-key code to fire without running aimbot logic


class Aimbot:
    """Basic aimbot controller."""
    
    def __init__(self, mem: DeadlockMemory, settings: AimbotSettings | None = None) -> None:
        """Create a new aimbot bound to ``mem``."""

        self.mem = mem
        self.settings = settings or AimbotSettings()
        self.locked_on: int | None = None
        self.force_aim_until: float = 0.0
        self.paused = False
        self.stop_requested = False

        # Headshot decision caching
        self._headshot_cache: bool = False
        self._headshot_cache_time: float = 0.0
        self._headshot_cache_interval: float = 0.4

        self._force_head_until: float = 0.0
        self._last_lock_lost: float = 0.0

        # Paradox shortcut state
        self._paradox_next_e: float = 0.0
        self._paradox_r_held: bool = False

        logger.info("Aimbot initialised with settings: %s", self.settings)

    def _update_ability_lock(self, hero) -> None:
        """Extend ``force_aim_until`` when ability keys are pressed."""
        now = time.time()
        if hero.name == "GreyTalon" and self.settings.grey_talon_lock_enabled and self.settings.grey_talon_lock > 0:
            if win32api.GetKeyState(self.settings.grey_talon_key) < 0:
                self.force_aim_until = max(self.force_aim_until, now + self.settings.grey_talon_lock)
                logger.debug("Grey Talon ability lock triggered; holding until %.2f", self.force_aim_until)        
        elif hero.name == "Yamato" and self.settings.yamato_lock_enabled and self.settings.yamato_lock > 0:
            if win32api.GetKeyState(self.settings.yamato_key) < 0:
                self.force_aim_until = max(self.force_aim_until, now + self.settings.yamato_lock)
                logger.debug("Yamato ability lock triggered; holding until %.2f", self.force_aim_until)
        elif hero.name == "Vindicta" and self.settings.vindicta_lock_enabled and self.settings.vindicta_lock > 0:
            if win32api.GetKeyState(self.settings.vindicta_key) < 0:
                self.force_aim_until = max(self.force_aim_until, now + self.settings.vindicta_lock)
                logger.debug("Vindicta ability lock triggered; holding until %.2f", self.force_aim_until)
        elif hero.name == "Paradox" and self.settings.paradox_shortcut_enabled:
            self._handle_paradox_shortcut(now)

    def _handle_paradox_shortcut(self, now: float) -> None:
        """Trigger Paradox ``E`` after ``R`` is pressed."""
        if win32api.GetKeyState(self.settings.paradox_r_key) < 0:
            if not self._paradox_r_held:
                self._paradox_r_held = True
                self._paradox_next_e = now + 0.05
        else:
            self._paradox_r_held = False

        if self._paradox_next_e and now >= self._paradox_next_e:
            win32api.keybd_event(self.settings.paradox_e_key, 0, 0, 0)
            win32api.keybd_event(
                self.settings.paradox_e_key, 0, win32con.KEYEVENTF_KEYUP, 0
            )
            logger.debug("Paradox shortcut triggered")
            self._paradox_next_e = 0.0

    def should_aim_for_head(self) -> bool:
        """Return ``True`` if the bot should attempt a headshot.

        Caches the random decision for 0.4 seconds to avoid frequent changes.
        """
        current_time = time.time()

        if self.settings.headshot_on_acquire and current_time < self._force_head_until:
            return True

        if current_time - self._headshot_cache_time >= self._headshot_cache_interval:
            self._headshot_cache = random.random() < self.settings.headshot_probability
            self._headshot_cache_time = current_time

        return self._headshot_cache

    def pause(self) -> None:
        """Pause the aimbot."""
        self.paused = True
        logger.info("Aimbot paused")
    
    def resume(self) -> None:
        """Resume the aimbot."""
        self.paused = False
        logger.info("Aimbot resumed")
    
    def stop(self) -> None:
        """Request the aimbot to stop."""
        self.stop_requested = True
        logger.info("Aimbot stop requested")

    def run(self) -> None:
        """Main aimbot loop."""

        logger.info("Aimbot loop started - hold the aimbot button to aim")
        active = (
            win32api.GetKeyState(self.settings.aimbot_button) < 0
            or time.time() < self.force_aim_until
        )
        log_state_changes = False
        prev_locked = None
        hold_down_left_click = False
        while not self.stop_requested:
            # Check if paused
            if self.paused:
                time.sleep(0.1)
                continue
                
            my_data = self.mem.read_entity(0)
            self._update_ability_lock(my_data["hero"])
            my_aim_angle = my_data["aim_angle"]

            if (
                not hold_down_left_click
                and win32api.GetKeyState(self.settings.fire_only_button) < 0
            ):
                hold_down_left_click = True
                ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)

            if (
                hold_down_left_click
                and win32api.GetKeyState(self.settings.fire_only_button) >= 0
            ):
                hold_down_left_click = False
                ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)

            if hold_down_left_click:
                time.sleep(0.01)
                continue

            mouse_down = (
                win32api.GetKeyState(self.settings.aimbot_button) < 0
                or time.time() < self.force_aim_until
            )
            if not log_state_changes and not mouse_down:
                log_state_changes = True
                active = False
            elif mouse_down != active:
                active = mouse_down
                if log_state_changes:
                    logger.info("Aimbot turned %s", "on" if active else "off")
            if not mouse_down:
                # Aimbot button is not held and no ability lock active
                if self.locked_on is not None:
                    self._last_lock_lost = time.time()
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
                if self.locked_on is not None:
                    if time.time() - self._last_lock_lost > 2:
                        self._force_head_until = (
                            time.time() + self._headshot_cache_interval
                        )
                    logger.debug("Locked on to entity %d", self.locked_on)

            if prev_locked != self.locked_on:
                if self.locked_on is None:
                    if prev_locked is not None:
                        logger.debug("Lost target")
                else:
                    if prev_locked is not None:
                        logger.debug("Changed target from %d to %d", prev_locked, self.locked_on)
                prev_locked = self.locked_on

            if self.locked_on is None:
                time.sleep(0.01)
                continue

            try:
                target = self.mem.read_entity(self.locked_on)
            except Exception:
                logger.debug("Failed to read entity %s; losing target", self.locked_on)
                if self.locked_on is not None:
                    self._last_lock_lost = time.time()
                self.locked_on = None
                continue

            bone_index = (
                get_head_bone_index(target["hero"]) if self.should_aim_for_head() else get_body_bone_index(target["hero"])
            )
            if bone_index is not None:
                bone_array = self.mem.read_longlong(
                    target["node"] + mo.SKELETON_BASE + mo.BONE_ARRAY
                )
                head_vector = (
                    self.mem.read_float(bone_array + bone_index * mo.BONE_STEP),
                    self.mem.read_float(bone_array + bone_index * mo.BONE_STEP + 4),
                    self.mem.read_float(bone_array + bone_index * mo.BONE_STEP + 8),
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
            self.mem.set_angles(new_yaw, new_pitch, my_aim_angle)
            time.sleep(0.001)
            
        logger.info("Aimbot loop ended")


def main(argv: list[str] | None = None) -> None:
    """Run the aimbot entry point.

    Parameters
    ----------
    argv:
        Optional command line arguments.  Providing ``--debug`` enables
        verbose output.
    """

    parser = argparse.ArgumentParser(description="Deadlock aimbot")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="enable debug logging",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    ensure_up_to_date()
    mem = DeadlockMemory()
    bot = Aimbot(mem)
    bot.run()


if __name__ == "__main__":
    main()
