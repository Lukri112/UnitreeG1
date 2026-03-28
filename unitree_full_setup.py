#!/usr/bin/env python3
import argparse
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

HOME = Path.home()
UNITREE_ROOT = HOME / "unitree_ros2"
WS_ROOT = UNITREE_ROOT / "cyclonedds_ws"
SRC_DIR = WS_ROOT / "src"
SDK2_DIR = HOME / "unitree_sdk2"
SDK2_PY_DIR = HOME / "unitree_sdk2_python"

CYCLONEDDS_SRC_DIR = SRC_DIR / "cyclonedds"
RMW_CYCLONEDDS_DIR = SRC_DIR / "rmw_cyclonedds"
CYCLONEDDS_BUILD_DIR = CYCLONEDDS_SRC_DIR / "build"
CYCLONEDDS_INSTALL_DIR = WS_ROOT / "install"

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
BLUE = "\033[0;34m"
NC = "\033[0m"


def info(msg: str) -> None:
    print(f"{BLUE}[INFO]{NC} {msg}")


def ok(msg: str) -> None:
    print(f"{GREEN}[OK]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{NC} {msg}")


def fail(msg: str) -> None:
    print(f"{RED}[FAIL]{NC} {msg}")


class SetupError(RuntimeError):
    pass


def run(cmd: List[str], *, cwd: Optional[Path] = None, env: Optional[Dict[str, str]] = None,
        check: bool = True, capture: bool = False, sudo: bool = False) -> subprocess.CompletedProcess:
    full_cmd = list(cmd)
    if sudo and (not full_cmd or full_cmd[0] != "sudo"):
        full_cmd = ["sudo"] + full_cmd

    print()
    print(f"$ {' '.join(full_cmd)}")
    result = subprocess.run(
        full_cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        capture_output=capture,
        check=False,
    )
    if capture:
        if result.stdout:
            print(result.stdout.strip())
        if result.stderr:
            print(result.stderr.strip(), file=sys.stderr)
    if check and result.returncode != 0:
        raise SetupError(f"Befehl fehlgeschlagen ({result.returncode}): {' '.join(full_cmd)}")
    return result


def require_root_tools() -> None:
    for tool in ["git", "cmake", "python3", "pip3", "sudo", "ip"]:
        if shutil.which(tool) is None:
            raise SetupError(f"Benötigtes Tool fehlt im PATH: {tool}")


def assert_ubuntu_2004() -> None:
    os_release = {}
    with open("/etc/os-release", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os_release[k] = v.strip('"')

    if os_release.get("ID") != "ubuntu" or os_release.get("VERSION_ID") != "20.04":
        raise SetupError(
            f"Dieses Skript ist für Ubuntu 20.04 gedacht. Gefunden: {os_release.get('ID')} {os_release.get('VERSION_ID')}"
        )
    ok("Ubuntu 20.04 erkannt")


def apt_install_base() -> None:
    info("Aktiviere Universe und installiere Grundpakete")
    run(["apt", "install", "-y", "software-properties-common"], sudo=True)
    run(["add-apt-repository", "-y", "universe"], sudo=True)
    run(["apt", "update"], sudo=True)
    run([
        "apt", "install", "-y",
        "curl", "gnupg2", "lsb-release", "ca-certificates",
        "git", "cmake", "g++", "build-essential", "make",
        "python3-pip", "python3-venv", "python3-colcon-common-extensions", "python3-rosdep",
        "libyaml-cpp-dev", "libeigen3-dev", "libboost-all-dev", "libspdlog-dev", "libfmt-dev",
        "net-tools", "iproute2", "pkg-config"
    ], sudo=True)


def ensure_ros_repo() -> None:
    info("Konfiguriere ROS-2-APT-Repository für Foxy")
    keyring = Path("/usr/share/keyrings/ros-archive-keyring.gpg")
    repo_file = Path("/etc/apt/sources.list.d/ros2.list")

    if not keyring.exists():
        run([
            "curl", "-sSL",
            "https://raw.githubusercontent.com/ros/rosdistro/master/ros.key",
            "-o", str(keyring)
        ], sudo=True)
        ok("ROS-GPG-Key installiert")
    else:
        ok("ROS-GPG-Key bereits vorhanden")

    repo_line = (
        "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] "
        "http://packages.ros.org/ros2/ubuntu $(. /etc/os-release && echo $UBUNTU_CODENAME) main"
    )
    if not repo_file.exists() or repo_line not in repo_file.read_text(encoding="utf-8", errors="ignore"):
        shell_cmd = f'echo "{repo_line}" | sudo tee /etc/apt/sources.list.d/ros2.list > /dev/null'
        run(["bash", "-lc", shell_cmd])
        ok("ROS-APT-Quelle eingetragen")
    else:
        ok("ROS-APT-Quelle bereits vorhanden")

    run(["apt", "update"], sudo=True)


def install_ros_foxy() -> None:
    info("Installiere ROS 2 Foxy und Unitree-relevante ROS-Pakete")
    run([
        "apt", "install", "-y",
        "ros-foxy-desktop", "python3-argcomplete",
        "ros-foxy-rmw-cyclonedds-cpp",
        "ros-foxy-rosidl-generator-dds-idl"
    ], sudo=True)


def init_rosdep() -> None:
    info("Initialisiere rosdep")
    res = subprocess.run(["bash", "-lc", "test -f /etc/ros/rosdep/sources.list.d/20-default.list"], check=False)
    if res.returncode != 0:
        run(["rosdep", "init"], sudo=True)
    else:
        ok("rosdep bereits initialisiert")
    run(["rosdep", "update"])


def git_clone_or_update(url: str, dst: Path, branch: Optional[str] = None) -> None:
    if dst.exists():
        info(f"Aktualisiere vorhandenes Repo: {dst}")
        run(["git", "fetch", "--all", "--tags"], cwd=dst)
        if branch:
            run(["git", "checkout", branch], cwd=dst)
            pull_result = run(["git", "pull", "--ff-only", "origin", branch], cwd=dst, check=False)
            if pull_result.returncode != 0:
                warn(f"Konnte '{branch}' nicht per git pull aktualisieren, verwende den aktuell ausgecheckten Stand in {dst}")
        else:
            run(["git", "pull", "--ff-only"], cwd=dst)
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        clone_cmd = ["git", "clone"]
        if branch:
            clone_cmd += ["-b", branch]
        clone_cmd += [url, str(dst)]
        info(f"Klone Repo: {url} -> {dst}")
        run(clone_cmd)


def prepare_repositories() -> None:
    info("Klonen/Aktualisieren der Unitree- und CycloneDDS-Repositories")
    git_clone_or_update("https://github.com/unitreerobotics/unitree_ros2.git", UNITREE_ROOT)
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    git_clone_or_update("https://github.com/eclipse-cyclonedds/cyclonedds.git", CYCLONEDDS_SRC_DIR, branch="releases/0.10.x")
    git_clone_or_update("https://github.com/unitreerobotics/unitree_sdk2.git", SDK2_DIR)
    git_clone_or_update("https://github.com/unitreerobotics/unitree_sdk2_python.git", SDK2_PY_DIR)

    if RMW_CYCLONEDDS_DIR.exists():
        warn(f"Entferne lokales rmw_cyclonedds-Repo, damit das installierte ROS-Paket verwendet wird: {RMW_CYCLONEDDS_DIR}")
        shutil.rmtree(RMW_CYCLONEDDS_DIR)


def clean_env_for_cyclone_build() -> Dict[str, str]:
    env = os.environ.copy()
    for key in [
        "AMENT_PREFIX_PATH", "COLCON_PREFIX_PATH", "CMAKE_PREFIX_PATH", "RMW_IMPLEMENTATION",
        "CYCLONEDDS_URI", "ROS_VERSION", "ROS_PYTHON_VERSION", "ROS_DISTRO", "ROS_LOCALHOST_ONLY",
        "ROS_DOMAIN_ID", "PYTHONPATH"
    ]:
        env.pop(key, None)
    return env


def build_cyclonedds_overlay() -> None:
    info("Baue CycloneDDS 0.10.x standalone im Unitree-Workspace ohne gesourcte ROS-Umgebung")

    env = clean_env_for_cyclone_build()
    env.setdefault("LD_LIBRARY_PATH", "/opt/ros/foxy/lib")

    CYCLONEDDS_BUILD_DIR.mkdir(parents=True, exist_ok=True)
    CYCLONEDDS_INSTALL_DIR.mkdir(parents=True, exist_ok=True)

    checkout_tag = run(["git", "checkout", "0.10.2"], cwd=CYCLONEDDS_SRC_DIR, check=False)
    if checkout_tag.returncode == 0:
        ok("CycloneDDS auf Tag 0.10.2 ausgecheckt")
    else:
        warn("Tag 0.10.2 nicht ausgecheckt; verwende den aktuellen releases/0.10.x-Stand")

    if (CYCLONEDDS_BUILD_DIR / "CMakeCache.txt").exists():
        info("Entferne alten CycloneDDS-CMakeCache")
        (CYCLONEDDS_BUILD_DIR / "CMakeCache.txt").unlink()

    run([
        "cmake",
        "-S", str(CYCLONEDDS_SRC_DIR),
        "-B", str(CYCLONEDDS_BUILD_DIR),
        f"-DCMAKE_INSTALL_PREFIX={CYCLONEDDS_INSTALL_DIR}",
        "-DCMAKE_BUILD_TYPE=Release",
        "-DBUILD_DDSPERF=OFF",
        "-DBUILD_TESTING=OFF"
    ], env=env)

    run([
        "cmake",
        "--build", str(CYCLONEDDS_BUILD_DIR),
        "--parallel", str(os.cpu_count() or 4)
    ], env=env)

    run([
        "cmake",
        "--install", str(CYCLONEDDS_BUILD_DIR)
    ], env=env)


def ros_env() -> Dict[str, str]:
    env = os.environ.copy()
    env["RMW_IMPLEMENTATION"] = "rmw_cyclonedds_cpp"
    env["CYCLONEDDS_HOME"] = str(CYCLONEDDS_INSTALL_DIR)
    env["CMAKE_PREFIX_PATH"] = f"{CYCLONEDDS_INSTALL_DIR}:{env.get('CMAKE_PREFIX_PATH', '')}".rstrip(":")
    env["LD_LIBRARY_PATH"] = f"{CYCLONEDDS_INSTALL_DIR / 'lib'}:{env.get('LD_LIBRARY_PATH', '')}".rstrip(":")
    env["PATH"] = f"{CYCLONEDDS_INSTALL_DIR / 'bin'}:{env.get('PATH', '')}".rstrip(":")
    env["PKG_CONFIG_PATH"] = f"{CYCLONEDDS_INSTALL_DIR / 'lib' / 'pkgconfig'}:{env.get('PKG_CONFIG_PATH', '')}".rstrip(":")
    return env


def build_unitree_ros2_workspace() -> None:
    info("Baue das Unitree ROS 2 Workspace mit gesourctem ROS Foxy")
    cmd = (
        "source /opt/ros/foxy/setup.bash && "
        "colcon build --packages-select unitree_api unitree_go unitree_hg"
    )
    run(["bash", "-lc", cmd], cwd=WS_ROOT, env=ros_env())


def build_and_install_sdk2() -> None:
    info("Baue und installiere unitree_sdk2")
    build_dir = SDK2_DIR / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    env = ros_env()
    cmake_prefix = env["CMAKE_PREFIX_PATH"]
    run(["cmake", "..", f"-DCMAKE_PREFIX_PATH={cmake_prefix}"], cwd=build_dir, env=env)
    run(["make", f"-j{os.cpu_count() or 4}"], cwd=build_dir, env=env)
    run(["make", "install"], cwd=build_dir, env=env, sudo=True)


def install_sdk2_python() -> None:
    info("Installiere unitree_sdk2_python im Editable-Modus")
    env = ros_env()
    env["CYCLONEDDS_HOME"] = str(CYCLONEDDS_INSTALL_DIR)
    env["CMAKE_PREFIX_PATH"] = f"{CYCLONEDDS_INSTALL_DIR}:{env.get('CMAKE_PREFIX_PATH', '')}".rstrip(":")
    run(["python3", "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"], env=env)
    run(["python3", "-m", "pip", "install", "-e", "."], cwd=SDK2_PY_DIR, env=env)


def detect_ethernet_interface() -> Optional[str]:
    sys_class_net = Path("/sys/class/net")
    candidates = []
    if sys_class_net.exists():
        for iface in sorted(sys_class_net.iterdir()):
            name = iface.name
            if name == "lo":
                continue
            if (iface / "wireless").exists() or name.startswith("wl"):
                continue
            try:
                operstate = (iface / "operstate").read_text(encoding="utf-8").strip()
            except Exception:
                operstate = "unknown"
            candidates.append((0 if operstate == "up" else 1, name))
    if candidates:
        candidates.sort()
        return candidates[0][1]
    return None


def write_setup_scripts(iface: str, configure_network: bool) -> None:
    info("Erzeuge setup.sh / setup_local.sh / setup_default.sh")
    UNITREE_ROOT.mkdir(parents=True, exist_ok=True)

    setup_sh = UNITREE_ROOT / "setup.sh"
    setup_local = UNITREE_ROOT / "setup_local.sh"
    setup_default = UNITREE_ROOT / "setup_default.sh"

    setup_sh.write_text(
        f"#!/bin/bash\n"
        f"echo \"Setup unitree ros2 environment\"\n"
        f"source /opt/ros/foxy/setup.bash\n"
        f"export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp\n"
        f"export CYCLONEDDS_HOME=$HOME/unitree_ros2/cyclonedds_ws/install\n"
        f"export CMAKE_PREFIX_PATH=$HOME/unitree_ros2/cyclonedds_ws/install:$CMAKE_PREFIX_PATH\n"
        f"export LD_LIBRARY_PATH=$HOME/unitree_ros2/cyclonedds_ws/install/lib:$LD_LIBRARY_PATH\n"
        f"export PATH=$HOME/unitree_ros2/cyclonedds_ws/install/bin:$PATH\n"
        f"export PKG_CONFIG_PATH=$HOME/unitree_ros2/cyclonedds_ws/install/lib/pkgconfig:$PKG_CONFIG_PATH\n"
        f"export CYCLONEDDS_URI='<CycloneDDS><Domain><General><Interfaces><NetworkInterface name=\"{iface}\" priority=\"default\" multicast=\"default\" /></Interfaces></General></Domain></CycloneDDS>'\n",
        encoding="utf-8"
    )
    setup_local.write_text(
        "#!/bin/bash\n"
        "echo \"Setup unitree ros2 local environment\"\n"
        "source /opt/ros/foxy/setup.bash\n"
        "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp\n"
        "export CYCLONEDDS_HOME=$HOME/unitree_ros2/cyclonedds_ws/install\n"
        "export CMAKE_PREFIX_PATH=$HOME/unitree_ros2/cyclonedds_ws/install:$CMAKE_PREFIX_PATH\n"
        "export LD_LIBRARY_PATH=$HOME/unitree_ros2/cyclonedds_ws/install/lib:$LD_LIBRARY_PATH\n"
        "export PATH=$HOME/unitree_ros2/cyclonedds_ws/install/bin:$PATH\n"
        "export PKG_CONFIG_PATH=$HOME/unitree_ros2/cyclonedds_ws/install/lib/pkgconfig:$PKG_CONFIG_PATH\n"
        "export CYCLONEDDS_URI='<CycloneDDS><Domain><General><Interfaces><NetworkInterface name=\"lo\" priority=\"default\" multicast=\"default\" /></Interfaces></General></Domain></CycloneDDS>'\n",
        encoding="utf-8"
    )
    setup_default.write_text(
        "#!/bin/bash\n"
        "echo \"Setup unitree ros2 default environment\"\n"
        "source /opt/ros/foxy/setup.bash\n"
        "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp\n"
        "export CYCLONEDDS_HOME=$HOME/unitree_ros2/cyclonedds_ws/install\n"
        "export CMAKE_PREFIX_PATH=$HOME/unitree_ros2/cyclonedds_ws/install:$CMAKE_PREFIX_PATH\n"
        "export LD_LIBRARY_PATH=$HOME/unitree_ros2/cyclonedds_ws/install/lib:$LD_LIBRARY_PATH\n"
        "export PATH=$HOME/unitree_ros2/cyclonedds_ws/install/bin:$PATH\n"
        "export PKG_CONFIG_PATH=$HOME/unitree_ros2/cyclonedds_ws/install/lib/pkgconfig:$PKG_CONFIG_PATH\n"
        "unset CYCLONEDDS_URI\n",
        encoding="utf-8"
    )

    for path in [setup_sh, setup_local, setup_default]:
        path.chmod(0o755)
        ok(f"Erstellt: {path}")

    if configure_network:
        configure_robot_interface(iface)


def configure_robot_interface(iface: str) -> None:
    if shutil.which("nmcli") is None:
        warn("nmcli nicht gefunden; Netzwerkkonfiguration wird übersprungen")
        return

    info(f"Konfiguriere {iface} auf 192.168.123.99/24 via NetworkManager")
    rc = subprocess.run(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show"], capture_output=True, text=True, check=False)
    connection_name = None
    if rc.returncode == 0:
        for line in rc.stdout.splitlines():
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[1] == iface:
                connection_name = parts[0]
                break

    if not connection_name:
        connection_name = f"unitree-{iface}"
        run(["nmcli", "connection", "add", "type", "ethernet", "ifname", iface, "con-name", connection_name], sudo=True)

    run(["nmcli", "connection", "modify", connection_name,
         "ipv4.addresses", "192.168.123.99/24",
         "ipv4.method", "manual",
         "ipv6.method", "ignore"], sudo=True)
    run(["nmcli", "connection", "up", connection_name], sudo=True)
    ok(f"{iface} auf 192.168.123.99/24 gesetzt")


def append_bashrc_block(iface: str) -> None:
    bashrc = HOME / ".bashrc"
    block = (
        "\n# >>> unitree_ros2 setup >>>\n"
        "# Standardmäßig NICHT automatisch sourcen, damit CycloneDDS-Builds sauber bleiben.\n"
        "# Bei Bedarf manuell ausführen:\n"
        "# source ~/unitree_ros2/setup.sh\n"
        f"export UNITREE_ROBOT_IFACE={iface}\n"
        "# <<< unitree_ros2 setup <<<\n"
    )
    content = bashrc.read_text(encoding="utf-8", errors="ignore") if bashrc.exists() else ""
    if "# >>> unitree_ros2 setup >>>" not in content:
        with open(bashrc, "a", encoding="utf-8") as f:
            f.write(block)
        ok("~/.bashrc um Unitree-Hinweis erweitert")
    else:
        ok("~/.bashrc enthält bereits einen Unitree-Block")


def final_checks(iface: str) -> None:
    info("Führe Abschlusschecks aus")
    run(["bash", "-lc", f"source {UNITREE_ROOT / 'setup.sh'} && ros2 pkg list | grep -E 'rmw_cyclonedds_cpp|unitree_.*' || true"])
    run(["bash", "-lc", f"source {UNITREE_ROOT / 'setup.sh'} && python3 -c \"import os; print('CYCLONEDDS_HOME=' + os.environ.get('CYCLONEDDS_HOME', ''))\" "])
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.2)
        sock.connect(("192.168.123.161", 80))
        local_ip = sock.getsockname()[0]
        sock.close()
        info(f"Aktuelle lokale Route Richtung 192.168.123.161 nutzt IP {local_ip}")
    except OSError:
        warn("Robot-IP 192.168.123.161 aktuell nicht erreichbar oder keine Route vorhanden")
    ok(f"Setup-Skripte bereit. Für Roboterbetrieb: source {UNITREE_ROOT / 'setup.sh'}")
    ok(f"Erkanntes Interface: {iface}")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Komplettes Setup für Unitree ROS2 + SDK2 + SDK2 Python auf Ubuntu 20.04")
    p.add_argument("--iface", help="Ethernet-Interface für den Roboter, z. B. enp3s0. Standard: Auto-Erkennung")
    p.add_argument("--configure-network", action="store_true", help="Setzt das Interface per nmcli auf 192.168.123.99/24")
    p.add_argument("--skip-apt", action="store_true", help="Überspringt APT-/ROS-Installation")
    p.add_argument("--skip-sdk2-install", action="store_true", help="Überspringt 'make install' für unitree_sdk2")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    require_root_tools()
    assert_ubuntu_2004()

    iface = args.iface or detect_ethernet_interface()
    if not iface:
        raise SetupError("Kein Ethernet-Interface automatisch gefunden. Bitte mit --iface z. B. enp3s0 angeben.")
    info(f"Verwende Netzwerkinterface: {iface}")

    if not args.skip_apt:
        apt_install_base()
        ensure_ros_repo()
        install_ros_foxy()
        init_rosdep()
    else:
        warn("APT-/ROS-Schritte wurden übersprungen")

    prepare_repositories()
    build_cyclonedds_overlay()
    build_unitree_ros2_workspace()
    if not args.skip_sdk2_install:
        build_and_install_sdk2()
    else:
        warn("unitree_sdk2 make install wurde übersprungen")
    install_sdk2_python()
    write_setup_scripts(iface, args.configure_network)
    append_bashrc_block(iface)
    final_checks(iface)

    print("\nFertig.")
    print(f"Zum Starten der Unitree-Umgebung: source {UNITREE_ROOT / 'setup.sh'}")
    print("Zum lokalen Testen ohne Roboter: source ~/unitree_ros2/setup_local.sh")
    print("Zum Kommunikationstest mit Roboter: ros2 topic list")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        raise SystemExit(130)
    except SetupError as e:
        fail(str(e))
        raise SystemExit(1)