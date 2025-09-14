import subprocess
import re
from typing import Tuple, List, Optional


def run(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    p = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="ignore",
        timeout=timeout,
    )
    stdout = (p.stdout or "").strip()
    stderr = (p.stderr or "").strip()
    return p.returncode, stdout, stderr


def get_connected_devices() -> List[str]:
    """获取所有已连接的设备列表"""
    code, out, _ = run(["adb", "devices"])
    if code != 0:
        return []
    
    devices = []
    for line in out.splitlines():
        if "\tdevice" in line:
            device = line.split("\t")[0].strip()
            if device:
                devices.append(device)
    return devices


def is_usb_device(device: str) -> bool:
    """判断是否为USB设备（非IP地址格式）"""
    # USB设备通常是设备ID格式，不包含IP地址
    return not re.match(r'^\d+\.\d+\.\d+\.\d+:\d+$', device)


def auto_connect_device(preferred_serial: Optional[str] = None) -> str:
    """
    自动连接设备，优先使用指定设备，否则自动选择最佳设备
    
    优先级：
    1. 指定的设备（如果已连接）
    2. USB设备（优先）
    3. 第一个可用的TCP设备
    """
    devices = get_connected_devices()
    
    if not devices:
        raise RuntimeError("未找到任何已连接的ADB设备")
    
    # 如果指定了设备且已连接，直接使用
    if preferred_serial and preferred_serial in devices:
        print(f"使用指定设备: {preferred_serial}")
        return preferred_serial
    
    # 分离USB和TCP设备
    usb_devices = [d for d in devices if is_usb_device(d)]
    tcp_devices = [d for d in devices if not is_usb_device(d)]
    
    # 优先选择USB设备
    if usb_devices:
        selected = usb_devices[0]
        print(f"自动选择USB设备: {selected}")
        return selected
    
    # 其次选择TCP设备
    if tcp_devices:
        selected = tcp_devices[0]
        print(f"自动选择TCP设备: {selected}")
        return selected
    
    # 如果都没有，使用第一个设备
    selected = devices[0]
    print(f"使用可用设备: {selected}")
    return selected


def adb_connect(serial: str) -> None:
    """连接指定设备（如果未连接则尝试连接）"""
    devices = get_connected_devices()
    
    # 如果设备已连接，直接返回
    if serial in devices:
        print(f"设备已连接: {serial}")
        return
    
    # 尝试连接设备
    print(f"尝试连接设备: {serial}")
    code, out, err = run(["adb", "connect", serial])
    if code != 0:
        raise RuntimeError(f"adb connect 失败: {err or out}")
    
    # 验证连接
    devices = get_connected_devices()
    if serial not in devices:
        raise RuntimeError(f"设备连接失败，未出现在 adb devices 列表")
    
    print(f"已连接设备: {serial}")


def adb_shell(serial: str, cmd: str, timeout: int = 10) -> tuple[int, str, str]:
    return run(["adb", "-s", serial, "shell", *cmd.split()], timeout=timeout)


def is_app_running(serial: str, pkg: str) -> bool:
    code, out, _ = adb_shell(serial, f"pidof {pkg}")
    if code == 0 and out.strip():
        return True
    code, out, _ = adb_shell(serial, f"ps -A | grep {pkg}")
    if code == 0 and any(pkg in line for line in out.splitlines()):
        return True
    return False


def force_stop_app(serial: str, pkg: str) -> None:
    print(f"检测到 {pkg} 运行中，执行强制停止...")
    adb_shell(serial, f"am force-stop {pkg}")

