import re
import time
import random
from typing import Optional, Tuple

from scripts.core.ui import dump_ui_xml, parse_bounds
from scripts.core.actions import tap, swipe_to_next_video


def find_watch_from_xml(xml_text: str, screen_h: int) -> Optional[Tuple[int, int]]:
    exact_keywords = ["去观看"]
    fuzzy_keywords = ["观看", "看视频", "去看"]
    exact_candidates: list[Tuple[int, int, int]] = []
    fuzzy_candidates: list[Tuple[int, int, int]] = []
    for node in re.finditer(r"<node [^>]+>", xml_text):
        tag = node.group(0)
        text = re.search(r"text=\"(.*?)\"", tag)
        desc = re.search(r"content-desc=\"(.*?)\"", tag)
        bounds = re.search(r"bounds=\"(.*?)\"", tag)
        label = ((text.group(1) if text else "") + (desc.group(1) if desc else "")).strip()
        b = bounds.group(1) if bounds else ""
        if not b:
            continue
        x1, y1, x2, y2 = parse_bounds(b)
        area = max(1, (x2 - x1) * (y2 - y1))
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        if any(label == k for k in exact_keywords):
            exact_candidates.append((area, cx, cy))
            continue
        if any(k in label for k in fuzzy_keywords):
            fuzzy_candidates.append((area, cx, cy))
    if exact_candidates:
        exact_candidates.sort(reverse=True)
        _, cx, cy = exact_candidates[0]
        return cx, cy
    if fuzzy_candidates:
        fuzzy_candidates.sort(reverse=True)
        _, cx, cy = fuzzy_candidates[0]
        return cx, cy
    return None


def find_like_button_from_xml(xml_text: str, screen_w: int, screen_h: int) -> Optional[Tuple[int, int]]:
    keywords = ["点赞", "喜欢", "赞", "like", "Like"]
    id_keywords = ["like", "thumb", "praise", "favourite", "favorite"]
    by_kw: list[Tuple[int, int, int]] = []
    by_pos: list[Tuple[int, int, int]] = []
    for node in re.finditer(r"<node [^>]+>", xml_text):
        tag = node.group(0)
        rid = re.search(r"resource-id=\"(.*?)\"", tag)
        klass = re.search(r"class=\"(.*?)\"", tag)
        text = re.search(r"text=\"(.*?)\"", tag)
        desc = re.search(r"content-desc=\"(.*?)\"", tag)
        bounds = re.search(r"bounds=\"(.*?)\"", tag)
        if not bounds:
            continue
        x1, y1, x2, y2 = parse_bounds(bounds.group(1))
        cx, cy = (x1 + x2) // 2, (y1 + y2) // 2
        area = max(1, (x2 - x1) * (y2 - y1))
        label = ((text.group(1) if text else "") + (desc.group(1) if desc else ""))
        rid_val = rid.group(1) if rid else ""
        if any(k in label for k in keywords) or any(k in rid_val for k in id_keywords):
            by_kw.append((area, cx, cy))
        if cx >= int(screen_w * 0.80) and cx <= int(screen_w * 0.98) and cy >= int(screen_h * 0.35) and cy <= int(screen_h * 0.75):
            if area <= int(screen_w * screen_h * 0.12):
                by_pos.append((area, cx, cy))
    if by_kw:
        by_kw.sort()
        _, cx, cy = by_kw[0]
        return cx, cy
    if by_pos:
        by_pos.sort()
        _, cx, cy = by_pos[0]
        return cx, cy
    return None


def run(serial: str, screen_w: int, screen_h: int, stay_min: float, stay_max: float, like_threshold: float) -> None:
    # 在‘去赚钱’页中查找“去观看”，点击进入视频页
    for attempt in range(3):
        xml = dump_ui_xml(serial)
        watch_pos = find_watch_from_xml(xml, screen_h)
        if watch_pos:
            wx, wy = watch_pos
            print(f"点击‘去观看’坐标: ({wx},{wy})")
            tap(serial, wx, wy)
            print("已点击‘去观看’，进入视频播放页面...")
            time.sleep(1.0)
            break
        time.sleep(0.8)
    else:
        print("未找到‘去观看’，请检查页面元素或关键词。")
        return

    # 无限循环：随机停留 + 点赞 + 下滑
    while True:
        stay = random.uniform(stay_min, stay_max)
        print(f"本视频随机停留时间: {stay:.1f} 秒")
        time.sleep(stay)
        if stay >= like_threshold:
            print(f"停留超过 {like_threshold:.1f} 秒，尝试点赞…")
            xml_like = dump_ui_xml(serial)
            pos_like = find_like_button_from_xml(xml_like, screen_w, screen_h)
            if pos_like:
                lx, ly = pos_like
                print(f"点击点赞坐标: ({lx},{ly})")
                tap(serial, lx, ly)
            else:
                print("未找到点赞按钮，跳过点赞。")
        print("时间到，开始滑动到下一个视频…")
        swipe_to_next_video(serial, screen_w, screen_h)

