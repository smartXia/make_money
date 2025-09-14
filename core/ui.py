import re
import time
from typing import Optional, Tuple

from .adb_utils import adb_shell


def parse_bounds(bounds_str: str) -> Tuple[int, int, int, int]:
    m = re.findall(r"\[(\d+),(\d+)\]", bounds_str)
    if len(m) == 2:
        (x1, y1), (x2, y2) = [(int(a), int(b)) for a, b in m]
        return x1, y1, x2, y2
    return 0, 0, 0, 0


def dump_ui_xml(serial: str, retries: int = 3) -> str:
    last_err = ""
    for _ in range(max(1, retries)):
        try:
            adb_shell(serial, "uiautomator dump --compressed /sdcard/uidump.xml", timeout=25)
            code, out, err = adb_shell(serial, "cat /sdcard/uidump.xml", timeout=10)
            if code == 0 and out.strip().startswith("<?xml"):
                return out
            last_err = err or out
        except Exception as e:
            last_err = str(e)
        time.sleep(0.8)
    raise RuntimeError(f"dump xml 失败: {last_err}")


