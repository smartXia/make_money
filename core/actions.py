from typing import Optional, Tuple
from .adb_utils import adb_shell


def tap(serial: str, x: int, y: int) -> None:
    code, out, err = adb_shell(serial, f"input tap {x} {y}")
    if code != 0:
        raise RuntimeError(f"点击失败: {err or out}")


def swipe_to_next_video(serial: str, screen_w: int, screen_h: int) -> None:
    x = screen_w // 2
    y1 = int(screen_h * 0.7)
    y2 = int(screen_h * 0.3)
    adb_shell(serial, f"input swipe {x} {y1} {x} {y2} 500")

