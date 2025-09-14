import os
import sys
import threading
import queue
import subprocess
import time
import shutil
import tkinter as tk
import tkinter.scrolledtext as st


def resolve_script_path() -> str | None:
    # 优先：源码路径（开发态）
    dev_path = os.path.join(os.path.dirname(__file__), "kuaishou_to_my.py")
    if os.path.isfile(dev_path):
        return dev_path
    # PyInstaller 一体化打包后，资源会被解压到 sys._MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cand_mei = os.path.join(meipass, "kuaishou_to_my.py")
        if os.path.isfile(cand_mei):
            return cand_mei
    # 冻结后：exe 同目录/scripts 下
    exe_dir = os.path.dirname(sys.executable)
    cand1 = os.path.join(exe_dir, "scripts", "kuaishou_to_my.py")
    if os.path.isfile(cand1):
        return cand1
    # 冻结后：exe 同目录
    cand2 = os.path.join(exe_dir, "kuaishou_to_my.py")
    if os.path.isfile(cand2):
        return cand2
    return None

SCRIPT_PATH = resolve_script_path()
CURRENT_PROC: subprocess.Popen | None = None


def resolve_python_cmd() -> list[str]:
    # 在打包后的 exe 中，sys.executable 指向当前 GUI，可导致递归启动。
    # 优先寻找系统 python，再退回到 sys.executable（开发环境）。
    if getattr(sys, "frozen", False):
        # 尝试 python、py
        for exe in ("python", "py"):
            if shutil.which(exe):
                return [exe]
        # 实在找不到，回退空（由上层处理）。
        return []
    # 非冻结，直接使用当前解释器
    return [sys.executable]


def run_script(output_queue: "queue.Queue[str]", serial_value: str | None, stay_min: float | None, stay_max: float | None, like_threshold: float | None) -> None:
    # 使用当前 Python 解释器启动原脚本，并实时读取输出
    global CURRENT_PROC
    py_cmd = resolve_python_cmd()
    if SCRIPT_PATH is None:
        output_queue.put("未找到 kuaishou_to_my.py。请将该文件放在 exe 同目录或其 scripts 子目录下。")
        output_queue.put("__ENABLE_START__")
        return
    if not py_cmd:
        output_queue.put("未找到可用的 Python 解释器，请确保已安装并在 PATH 中。")
        output_queue.put("__ENABLE_START__")
        return
    cmd = [*py_cmd, SCRIPT_PATH]
    if serial_value:
        cmd += ["--serial", serial_value]
    if stay_min is not None:
        cmd += ["--stay-min", str(stay_min)]
    if stay_max is not None:
        cmd += ["--stay-max", str(stay_max)]
    if like_threshold is not None:
        cmd += ["--like-threshold", str(like_threshold)]
    # 打印启动命令
    output_queue.put("[启动] " + " ".join(cmd))
    # Windows 下抑制控制台弹窗 + 强制子进程无缓冲输出
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    # 强制子进程以 UTF-8 输出，避免中文乱码
    env["PYTHONIOENCODING"] = "utf-8"
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=creationflags,
            bufsize=1,
            env=env,
        )
    except Exception as e:
        output_queue.put(f"[启动失败] {e}")
        output_queue.put("__ENABLE_START__")
        return
    CURRENT_PROC = proc
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            output_queue.put(line.rstrip("\n"))
    finally:
        code = proc.wait()
        CURRENT_PROC = None
        output_queue.put(f"[进程已退出] 退出码: {code}")
        output_queue.put("__ENABLE_START__")


def pump_logs(text_widget: st.ScrolledText, output_queue: "queue.Queue[str]", start_button: tk.Button, stop_button: tk.Button) -> None:
    # 将队列中的日志刷到文本框
    try:
        while True:
            line = output_queue.get_nowait()
            if line == "__ENABLE_START__":
                start_button.config(state=tk.NORMAL)
                stop_button.config(state=tk.DISABLED)
            else:
                text_widget.insert(tk.END, line + "\n")
                text_widget.see(tk.END)
    except Exception:
        pass
    text_widget.after(100, pump_logs, text_widget, output_queue, start_button, stop_button)


def start_run(start_button: tk.Button, stop_button: tk.Button, text_widget: st.ScrolledText, serial_entry: tk.Entry, stay_min_entry: tk.Entry, stay_max_entry: tk.Entry, like_entry: tk.Entry) -> None:
    start_button.config(state=tk.DISABLED)
    stop_button.config(state=tk.NORMAL)
    q: "queue.Queue[str]" = queue.Queue()
    serial_value = serial_entry.get().strip()
    if serial_value == "":
        serial_value = None
    def parse_float(entry: tk.Entry) -> float | None:
        s = entry.get().strip()
        if s == "":
            return None
        try:
            return float(s)
        except Exception:
            return None
    stay_min = parse_float(stay_min_entry)
    stay_max = parse_float(stay_max_entry)
    like_threshold = parse_float(like_entry)
    t = threading.Thread(target=run_script, args=(q, serial_value, stay_min, stay_max, like_threshold), daemon=True)
    t.start()
    pump_logs(text_widget, q, start_button, stop_button)


def stop_run(start_button: tk.Button, stop_button: tk.Button, text_widget: st.ScrolledText) -> None:
    global CURRENT_PROC
    if CURRENT_PROC is None:
        return
    text_widget.insert(tk.END, "请求停止运行…\n")
    text_widget.see(tk.END)
    try:
        CURRENT_PROC.terminate()
        for _ in range(20):  # 等待最多2秒
            if CURRENT_PROC.poll() is not None:
                break
            time.sleep(0.1)
        if CURRENT_PROC.poll() is None:
            CURRENT_PROC.kill()
    except Exception as _:
        pass


def main() -> None:
    root = tk.Tk()
    root.title("快手自动刷视频 - 日志窗口")
    root.geometry("900x600")

    top_frame = tk.Frame(root)
    top_frame.pack(fill=tk.X, padx=8, pady=6)

    tk.Label(top_frame, text="ADB 地址:").pack(side=tk.LEFT)
    serial_entry = tk.Entry(top_frame, width=22)
    serial_entry.pack(side=tk.LEFT, padx=(4, 12))

    tk.Label(top_frame, text="停留最短(s):").pack(side=tk.LEFT)
    stay_min_entry = tk.Entry(top_frame, width=8)
    stay_min_entry.insert(0, "3")
    stay_min_entry.pack(side=tk.LEFT, padx=(4, 8))

    tk.Label(top_frame, text="停留最长(s):").pack(side=tk.LEFT)
    stay_max_entry = tk.Entry(top_frame, width=8)
    stay_max_entry.insert(0, "20")
    stay_max_entry.pack(side=tk.LEFT, padx=(4, 8))

    tk.Label(top_frame, text="点赞阈值(s):").pack(side=tk.LEFT)
    like_entry = tk.Entry(top_frame, width=8)
    like_entry.insert(0, "15")
    like_entry.pack(side=tk.LEFT, padx=(4, 8))
    start_btn = tk.Button(top_frame, text="开始运行", width=12)
    start_btn.pack(side=tk.LEFT)
    stop_btn = tk.Button(top_frame, text="停止运行", width=12, state=tk.DISABLED)
    stop_btn.pack(side=tk.LEFT, padx=(8, 0))

    text = st.ScrolledText(root, width=120, height=34)
    text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

    start_btn.configure(command=lambda: start_run(start_btn, stop_btn, text, serial_entry, stay_min_entry, stay_max_entry, like_entry))
    stop_btn.configure(command=lambda: stop_run(start_btn, stop_btn, text))

    # 初始提示
    text.insert(tk.END, "点击‘开始运行’以启动脚本并在此窗口查看日志。ADB 地址留空则使用脚本默认值。\n")
    text.see(tk.END)

    root.mainloop()


if __name__ == "__main__":
    main()


