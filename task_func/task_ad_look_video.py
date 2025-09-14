import re
from typing import Optional, Tuple

from scripts.core.ui import dump_ui_xml, parse_bounds
from scripts.core.actions import tap, swipe_to_next_video


def _row_overlap(b1: str, b2: str) -> bool:
    x1, y1, x2, y2 = parse_bounds(b1)
    a1, b1y, a2, b2y = parse_bounds(b2)
    h1 = max(1, y2 - y1)
    overlap = max(0, min(y2, b2y) - max(y1, b1y))
    return overlap >= int(h1 * 0.4)


def find_task_row_bounds(xml_text: str, keyword: str) -> Optional[str]:
    # 优先匹配 keyword（刷广告视频赚金币），找不到再兼容“刷广告视频赚收益”
    for node in re.finditer(r"<node [^>]+>", xml_text):
        tag = node.group(0)
        text = re.search(r"text=\"(.*?)\"", tag)
        desc = re.search(r"content-desc=\"(.*?)\"", tag)
        bounds = re.search(r"bounds=\"(.*?)\"", tag)
        label = ((text.group(1) if text else "") + (desc.group(1) if desc else "")).strip()
        if ((keyword in label) or ("刷广告" in label)) and bounds:
            return bounds.group(1)
    return None


def find_watch_button_in_row(xml_text: str, row_bounds: str) -> Optional[Tuple[int, int]]:
    # 仅精确匹配“领福利”按钮
    primary_kw = ["领福利"]
    primary: list[Tuple[int, int, int, int]] = []  # (score, cx, cy, x_right)
    for node in re.finditer(r"<node [^>]+>", xml_text):
        tag = node.group(0)
        text = re.search(r"text=\"(.*?)\"", tag)
        desc = re.search(r"content-desc=\"(.*?)\"", tag)
        bounds = re.search(r"bounds=\"(.*?)\"", tag)
        if not bounds:
            continue
        b2 = bounds.group(1)
        if not _row_overlap(row_bounds, b2):
            continue
        label = ((text.group(1) if text else "") + (desc.group(1) if desc else "")).strip()
        x1, y1, x2, y2 = parse_bounds(b2)
        area = max(1, (x2 - x1) * (y2 - y1))
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        # 简单过滤：面积不能过小
        if area <= 50:
            continue
        # 按“更靠右+面积更大”打分，偏向行尾按钮
        score = (x2) * 10 + area
        if any(label == k for k in primary_kw):
            primary.append((score, cx, cy, x2))
            continue
    if primary:
        primary.sort(reverse=True)
        _, cx, cy, _ = primary[0]
        return cx, cy
    return None


def run(serial: str, screen_w: int, screen_h: int, stay_min: float = 3.0, stay_max: float = 20.0, like_threshold: float = 15.0) -> bool:
    # 仅执行：找到“刷广告”行 -> 同行精确“领福利” -> 点击
    for attempt in range(10):  # 最多翻 10 页
        xml = dump_ui_xml(serial)
        row_bounds = find_task_row_bounds(xml, "刷广告视频赚金币")
        if row_bounds:
            pos = find_watch_button_in_row(xml, row_bounds)
            if pos:
                x, y = pos
                if x <= 0 or y <= 0:
                    print("检测到按钮坐标异常，放弃点击。")
                    return False
                print(f"点击‘领福利’坐标: ({x},{y})")
                tap(serial, x, y)
                print("已点击‘领福利’（广告视频任务）。")
                # return True
        # 未找到行或按钮，向下滑继续找
        print("未找到‘刷广告’行或‘领福利’按钮，向下滑一页继续寻找…")
        swipe_to_next_video(serial, screen_w, screen_h)
        import time as _t
        _t.sleep(0.8)
    print("未找到‘刷广告’行或‘领福利’按钮（已翻多页）")
    # return False
    # 进入广告视频后，沿用通用观看逻辑：随机停留并下滑
    import time, random
    while True:
        stay = random.uniform(stay_min, stay_max)
        print(f"[广告] 本视频随机停留时间: {stay:.1f} 秒")
        time.sleep(stay)
        if stay >= like_threshold:
            print(f"[广告] 停留超过 {like_threshold:.1f} 秒（广告视频不点赞，直接滑动）")
        print("[广告] 时间到，开始滑动到下一个视频…")
        swipe_to_next_video(serial, screen_w, screen_h)
    # 正常不会返回
    # return True

