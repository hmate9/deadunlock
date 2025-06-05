from __future__ import annotations

"""Simplistic ESP (Extra Sensory Perception) overlay using pygame."""

import ctypes
import time
import logging
import argparse

import numpy as np
import pygame

from .helpers import world_to_screen
from .memory import DeadlockMemory
from . import mem_offsets as mo
from .update_checker import ensure_up_to_date

logger = logging.getLogger(__name__)


class ESP:
    """Tiny pygame-based overlay rendering player skeletons."""

    def __init__(self, mem: DeadlockMemory) -> None:
        """Create an overlay bound to ``mem``."""

        self.mem = mem
        pygame.init()
        info = pygame.display.Info()
        self.screen = pygame.display.set_mode((info.current_w, info.current_h), pygame.NOFRAME | pygame.SRCALPHA)
        pygame.display.set_caption("ESP Overlay")
        self.clock = pygame.time.Clock()

        hwnd = pygame.display.get_wm_info()["window"]
        ctypes.windll.user32.SetWindowLongW(hwnd, -20, ctypes.windll.user32.GetWindowLongW(hwnd, -20) | 0x80000 | 0x20)
        ctypes.windll.user32.SetLayeredWindowAttributes(hwnd, 0, 255, 1)
        logger.info("ESP overlay initialised")

    def draw_skeleton(self, bones, color=(255, 0, 0)) -> None:
        """Draw a list of bone pairs to the screen.

        The original proof-of-concept script renders each bone as a tiny red dot
        with its index printed above it.  ``bones`` is expected to contain
        ``(start, end)`` tuples where ``start`` and ``end`` are 3D coordinates.
        """

        for idx, (start, end) in enumerate(bones):
            start_pos = world_to_screen(
                self.view_matrix, start, self.width, self.height
            )
            end_pos = world_to_screen(
                self.view_matrix, end, self.width, self.height
            )
            if start_pos and end_pos:
                # A line where start and end are identical produces a small dot.
                pygame.draw.line(self.screen, color, start_pos, end_pos, 2)
                font = pygame.font.Font(None, 18)
                text = font.render(str(idx), True, (255, 255, 255))
                self.screen.blit(text, (start_pos[0], start_pos[1] - 10))

    @property
    def width(self) -> int:
        return self.screen.get_width()

    @property
    def height(self) -> int:
        return self.screen.get_height()

    def update_view_matrix(self) -> None:
        raw = self.mem.pm.read_bytes(self.mem.client_base + self.mem.offsets.view_matrix, 16 * 4)
        self.view_matrix = np.frombuffer(raw, dtype=np.float32).reshape(4, 4)

    def run(self) -> None:
        """Main overlay loop."""

        logger.info("ESP loop started")
        running = True
        while running:
            self.screen.fill((0, 0, 0, 0))
            self.update_view_matrix()
            for i in range(1, 16):
                try:
                    data = self.mem.read_entity(i)
                except Exception:
                    logger.debug("Failed to read entity %d", i)
                    continue
                bone_array = self.mem.read_longlong(
                    data["node"] + mo.SKELETON_BASE + mo.BONE_ARRAY
                )
                bones = []
                for b in range(0, 64):
                    start = (
                        self.mem.read_float(bone_array + b * mo.BONE_STEP),
                        self.mem.read_float(bone_array + b * mo.BONE_STEP + 4),
                        self.mem.read_float(bone_array + b * mo.BONE_STEP + 8),
                    )
                    bones.append((start, start))
                logger.debug("Drawing skeleton for entity %d", i)
                self.draw_skeleton(bones)

            pygame.display.flip()
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            time.sleep(0.001)
        logger.info("ESP loop stopped")


def main(argv: list[str] | None = None) -> None:
    """Run the ESP overlay entry point.

    Parameters
    ----------
    argv:
        Optional command line arguments.  Providing ``--debug`` enables
        verbose logging output.
    """

    parser = argparse.ArgumentParser(description="Deadlock ESP overlay")
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
    esp = ESP(mem)
    esp.run()


if __name__ == "__main__":
    main()
