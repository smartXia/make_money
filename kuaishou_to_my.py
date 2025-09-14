import re
import sys
import time
import random
import subprocess
import argparse
import json
import os
from typing import Optional, Tuple
try:
    from scripts.task_func.task_look_video import run as run_task_look_video
    from scripts.task_func.task_ad_look_video import run as run_task_ad_look_video
    from scripts.core.adb_utils import auto_connect_device, adb_connect, adb_shell, is_app_running, force_stop_app
    from scripts.core.ui import dump_ui_xml, get_screen_size, find_earn_from_xml, close_popup_if_present, handle_network_retry
    from scripts.core.actions import tap, launch_app
except ModuleNotFoundError:
    # 兼容直接运行脚本：python scripts/kuaishou_to_my.py
    import os as _os, sys as _sys
    _sys.path.append(_os.path.dirname(_os.path.dirname(__file__)))
    from scripts.task_func.task_look_video import run as run_task_look_video
    from scripts.task_func.task_ad_look_video import run as run_task_ad_look_video
    from scripts.core.adb_utils import auto_connect_device, adb_connect, adb_shell, is_app_running, force_stop_app
    from scripts.core.ui import dump_ui_xml, get_screen_size, find_earn_from_xml, close_popup_if_present, handle_network_retry
    from scripts.core.actions import tap, launch_app


TARGET_SERIAL = "192.168.2.12:5001"
PKG = "com.kuaishou.nebula"


def main() -> int:
    parser = argparse.ArgumentParser(description="Kuaishou auto runner")
    parser.add_argument("--serial", dest="serial", default=None, help="ADB 设备地址，如 192.168.2.12:5001。缺省则使用脚本内默认值")
    parser.add_argument("--stay-min", dest="stay_min", type=float, default=10.0, help="每条视频随机停留的最短秒数，默认 3.0")
    parser.add_argument("--stay-max", dest="stay_max", type=float, default=20.0, help="每条视频随机停留的最长秒数，默认 20.0")
    parser.add_argument("--like-threshold", dest="like_threshold", type=float, default=45.0, help="当停留秒数大于等于该阈值时尝试点赞，默认 15.0")
    args = parser.parse_args()

    serial = args.serial or TARGET_SERIAL
    stay_min = max(0.5, float(args.stay_min))
    stay_max = max(stay_min, float(args.stay_max))
    like_threshold = max(0.0, float(args.like_threshold))
    try:
        # 1) 自动连接设备（优先USB，其次TCP）
        serial = auto_connect_device(args.serial or TARGET_SERIAL)

        # 2) 启动前检查并停止已运行实例
        if is_app_running(serial, PKG):
            force_stop_app(serial, PKG)
        # 再启动快手极速版
        launch_app(serial, PKG)

        # 3) dump 页面，定位底部"去赚钱"文字并点击
        w, h = get_screen_size(serial)
        xml = dump_ui_xml(serial)
        pos = find_earn_from_xml(xml, h)
        if not pos:
            print("未找到'去赚钱'相关文字（底部区域）。")
            return 2
        x, y = pos
        print(f"点击'去赚钱'坐标: ({x},{y})")
        tap(serial, x, y)
        print("已点击'去赚钱'。")

        # 4) 如有弹窗则尝试自动关闭（点击后先等待 3 秒）
        time.sleep(3.0)
        closed = close_popup_if_present(serial, w, h, retries=3, interval=0.8)
        if closed:
            print("已自动关闭弹窗。")
        else:
            print("未检测到可关闭的弹窗。")

        # 5) 处理断网重试弹窗
        handle_network_retry(serial, w, h)

        # 6) 优先执行广告视频任务，若未找到则执行普通看视频任务
        print("尝试执行广告视频任务...")
        if not run_task_ad_look_video(serial, w, h, stay_min, stay_max, like_threshold):
            print("未找到广告视频任务，尝试执行普通看视频任务...")
            run_task_look_video(serial, w, h, stay_min, stay_max, like_threshold)
        return 0
    except Exception as e:
        print("执行失败:", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())