from __future__ import annotations

"""Simplistic ESP (Extra Sensory Perception) overlay using pygame."""

import ctypes
import time

import numpy as np
import pygame

from .helpers import world_to_screen
from .memory import DeadlockMemory


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

    def draw_skeleton(self, bones, color=(255, 0, 0)) -> None:
        """Draw a list of bone pairs to the screen."""

        for start, end in bones:
            start_pos = world_to_screen(self.view_matrix, start, self.width, self.height)
            end_pos = world_to_screen(self.view_matrix, end, self.width, self.height)
            if start_pos and end_pos:
                pygame.draw.line(self.screen, color, start_pos, end_pos, 2)

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

        running = True
        while running:
            self.screen.fill((0, 0, 0, 0))
            self.update_view_matrix()
            for i in range(1, 16):
                try:
                    data = self.mem.read_entity(i)
                except Exception:
                    continue
                bone_array = self.mem.read_longlong(data["node"] + 0x170 + 0x80)
                bones = []
                for b in range(0, 15):
                    start = (
                        self.mem.read_float(bone_array + b * 32),
                        self.mem.read_float(bone_array + b * 32 + 4),
                        self.mem.read_float(bone_array + b * 32 + 8),
                    )
                    bones.append((start, start))
                self.draw_skeleton(bones)

            pygame.display.flip()
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
            time.sleep(0.001)


def main() -> None:
    mem = DeadlockMemory()
    esp = ESP(mem)
    esp.run()


if __name__ == "__main__":
    main()
