"""Small system/network probes for runtime status and dashboard."""
import os
import socket
import subprocess
import time


_BOOT_TIME = time.time()


def run_command(args, timeout=3):
    try:
        output = subprocess.check_output(args, stderr=subprocess.DEVNULL, timeout=timeout)
        return output.decode("utf-8", errors="replace")
    except Exception:
        return ""


def parse_ip_br_addr(output):
    result = {"eth0_ip": None, "wlan0_ip": None}
    for raw_line in output.splitlines():
        parts = raw_line.split()
        if len(parts) < 3:
            continue
        iface = parts[0]
        ipv4 = None
        for token in parts[2:]:
            if "." in token and "/" in token:
                ipv4 = token.split("/", 1)[0]
                break
        if iface == "eth0":
            result["eth0_ip"] = ipv4
        elif iface == "wlan0":
            result["wlan0_ip"] = ipv4
    return result


def read_network_status(command_runner=None):
    command_runner = command_runner or run_command
    status = parse_ip_br_addr(command_runner(["ip", "-br", "addr", "show"]))
    ssid = command_runner(["iwgetid", "-r"]).strip()
    status["ssid"] = ssid or None
    return status


def read_cpu_temp_c():
    temps = []
    thermal_root = "/sys/devices/virtual/thermal"
    try:
        for name in os.listdir(thermal_root):
            path = os.path.join(thermal_root, name, "temp")
            if not os.path.exists(path):
                continue
            with open(path, "r") as fh:
                raw = fh.read().strip()
            if raw:
                temps.append(float(raw) / 1000.0)
    except Exception:
        return None
    return max(temps) if temps else None


def read_memory_percent():
    try:
        values = {}
        with open("/proc/meminfo", "r") as fh:
            for line in fh:
                key, value = line.split(":", 1)
                values[key] = float(value.strip().split()[0])
        total = values.get("MemTotal")
        available = values.get("MemAvailable")
        if not total or available is None:
            return None
        return round((total - available) * 100.0 / total, 1)
    except Exception:
        return None


def read_system_status():
    return {
        "hostname": socket.gethostname(),
        "uptime_seconds": int(time.time() - _BOOT_TIME),
        "cpu_temp_c": read_cpu_temp_c(),
        "ram_percent": read_memory_percent(),
    }
