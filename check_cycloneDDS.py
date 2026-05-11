#!/usr/bin/env python3
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
RED = "\033[0;31m"
NC = "\033[0m"


def ok(msg: str) -> None:
    print(f"{GREEN}[OK]{NC} {msg}")


def warn(msg: str) -> None:
    print(f"{YELLOW}[WARN]{NC} {msg}")


def fail(msg: str) -> None:
    print(f"{RED}[FAIL]{NC} {msg}")


def run_command(cmd, cwd=None):
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def command_exists(cmd: str) -> bool:
    return shutil.which(cmd) is not None


def split_env_paths(var_name: str):
    value = os.environ.get(var_name, "")
    if not value:
        return []
    return [Path(p).expanduser() for p in value.split(":") if p.strip()]


def candidate_prefixes():
    home = Path.home()
    prefixes = [
        home / "cyclonedds" / "install",
        Path("/opt/ros/foxy"),
        Path("/usr/local"),
        Path("/usr"),
    ]

    for var in ["CMAKE_PREFIX_PATH", "AMENT_PREFIX_PATH", "COLCON_PREFIX_PATH"]:
        for p in split_env_paths(var):
            if p not in prefixes:
                prefixes.append(p)

    deduped = []
    seen = set()
    for p in prefixes:
        s = str(p)
        if s not in seen:
            seen.add(s)
            deduped.append(p)
    return deduped


def config_candidates(prefix: Path):
    return [
        prefix / "lib/cmake/CycloneDDS/CycloneDDSConfig.cmake",
        prefix / "lib/x86_64-linux-gnu/cmake/CycloneDDS/CycloneDDSConfig.cmake",
        prefix / "share/CycloneDDS/cmake/CycloneDDSConfig.cmake",
    ]


def find_cyclonedds_prefix():
    for prefix in candidate_prefixes():
        for candidate in config_candidates(prefix):
            if candidate.is_file():
                return prefix, candidate
    return None, None


def find_first_existing(paths):
    for p in paths:
        if p.is_file():
            return p
    return None


def test_cmake_can_find_cyclonedds(prefix: Path):
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)

        (tmpdir / "CMakeLists.txt").write_text(
            """cmake_minimum_required(VERSION 3.10)
project(test_cyclonedds_find)
find_package(CycloneDDS REQUIRED)
add_executable(test_dds main.cpp)
target_link_libraries(test_dds CycloneDDS::ddsc)
""",
            encoding="utf-8",
        )

        (tmpdir / "main.cpp").write_text(
            """#include <iostream>
int main() {
    std::cout << "CycloneDDS test" << std::endl;
    return 0;
}
""",
            encoding="utf-8",
        )

        env = os.environ.copy()
        old_cpp = env.get("CMAKE_PREFIX_PATH", "")
        env["CMAKE_PREFIX_PATH"] = f"{prefix}:{old_cpp}" if old_cpp else str(prefix)

        returncode, stdout, stderr = run_command(
            [
                "cmake",
                "-S",
                str(tmpdir),
                "-B",
                str(tmpdir / "build"),
                f"-DCMAKE_PREFIX_PATH={env['CMAKE_PREFIX_PATH']}",
            ]
        )
        return returncode == 0, stdout, stderr, env["CMAKE_PREFIX_PATH"]


def main():
    print("=== CycloneDDS / Unitree Installationscheck (Ubuntu 20.04) ===\n")

    print("0) Sichtbare Prefixe ...")
    for p in candidate_prefixes():
        print(f"   - {p}")
    print()

    print("1) Suche CycloneDDS-Installation ...")
    cyclone_prefix, cyclone_config = find_cyclonedds_prefix()

    if cyclone_prefix and cyclone_config:
        ok(f"CycloneDDSConfig.cmake gefunden: {cyclone_config}")
    else:
        fail("Keine CycloneDDS-CMake-Installation gefunden.")
        print("      Gesucht wurde u. a. in:")
        for p in candidate_prefixes():
            print(f"      - {p}")
    print()

    print("2) Prüfe wichtige CycloneDDS-Dateien ...")
    if cyclone_prefix:
        lib_path = find_first_existing(
            [
                cyclone_prefix / "lib/libddsc.so",
                cyclone_prefix / "lib/x86_64-linux-gnu/libddsc.so",
                cyclone_prefix / "lib/libddsc.dylib",
            ]
        )
        if lib_path:
            ok(f"Bibliothek gefunden: {lib_path}")
        else:
            warn("libddsc.so nicht gefunden. Installation könnte unvollständig sein.")

        header_path = find_first_existing(
            [
                cyclone_prefix / "include/ddsc/dds.h",
                cyclone_prefix / "include/cyclonedds/ddsc/dds.h",
            ]
        )
        if header_path:
            ok(f"Header gefunden: {header_path}")
        else:
            warn("DDS-Header nicht gefunden. Installation könnte unvollständig sein.")
    print()

    print("3) Prüfe, ob CMake CycloneDDS finden kann ...")
    if cyclone_prefix:
        if not command_exists("cmake"):
            fail("cmake ist nicht installiert oder nicht im PATH.")
        else:
            success, stdout, stderr, used_prefix_path = test_cmake_can_find_cyclonedds(cyclone_prefix)
            if success:
                ok(f"CMake findet CycloneDDS mit CMAKE_PREFIX_PATH={used_prefix_path}")
            else:
                fail("CMake kann CycloneDDS nicht finden.")
                if stdout:
                    print("      stdout:")
                    for line in stdout.splitlines():
                        print(f"      {line}")
                if stderr:
                    print("      stderr:")
                    for line in stderr.splitlines():
                        print(f"      {line}")
    else:
        warn("CMake-Test übersprungen, weil keine CycloneDDS-Installation erkannt wurde.")
    print()

    print("4) Prüfe unitree_sdk2_python-relevante Variablen ...")
    cyclonedds_home = os.environ.get("CYCLONEDDS_HOME")
    if cyclonedds_home:
        ok(f"CYCLONEDDS_HOME ist gesetzt: {cyclonedds_home}")
    else:
        warn("CYCLONEDDS_HOME ist nicht gesetzt.")
        print("      Für unitree_sdk2_python oft sinnvoll:")
        print("      export CYCLONEDDS_HOME=$HOME/cyclonedds/install")
    print()

    print("5) Prüfe ROS 2 / unitree_ros2-relevante Umgebung ...")
    if command_exists("ros2"):
        ok("ros2 CLI gefunden.")
    else:
        warn("ros2 CLI nicht gefunden.")

    ros_distro = os.environ.get("ROS_DISTRO")
    if ros_distro:
        ok(f"ROS_DISTRO ist gesetzt: {ros_distro}")
    else:
        warn("ROS_DISTRO ist nicht gesetzt.")

    rmw_impl = os.environ.get("RMW_IMPLEMENTATION")
    if rmw_impl == "rmw_cyclonedds_cpp":
        ok("RMW_IMPLEMENTATION ist korrekt gesetzt: rmw_cyclonedds_cpp")
    elif rmw_impl:
        warn(f"RMW_IMPLEMENTATION ist gesetzt, aber nicht korrekt: {rmw_impl}")
    else:
        warn("RMW_IMPLEMENTATION ist nicht gesetzt.")
    print()

    print("6) Prüfe rmw_cyclonedds_cpp Paket ...")
    if command_exists("ros2"):
        rc, out, err = run_command(["ros2", "pkg", "list"])
        if rc == 0 and "rmw_cyclonedds_cpp" in out.splitlines():
            ok("ROS 2 Paket rmw_cyclonedds_cpp gefunden.")
        else:
            warn("ROS 2 Paket rmw_cyclonedds_cpp nicht gefunden.")
            if err:
                print(f"      {err}")
    else:
        warn("Paketprüfung übersprungen, ros2 CLI fehlt.")
    print()

    print("7) Prüfe CYCLONEDDS_URI ...")
    cyclonedds_uri = os.environ.get("CYCLONEDDS_URI")
    if cyclonedds_uri:
        ok("CYCLONEDDS_URI ist gesetzt.")
        print(f"      {cyclonedds_uri}")
        if "wlo" in cyclonedds_uri or "wlan" in cyclonedds_uri:
            warn("Es scheint eine WLAN-Schnittstelle verwendet zu werden. Für Unitree ist meist Ethernet sinnvoller.")
    else:
        warn("CYCLONEDDS_URI ist nicht gesetzt.")
    print()

    print("=== Zusammenfassung ===")
    if cyclone_prefix:
        print(f"- CycloneDDS-Installationsprefix: {cyclone_prefix}")
        print("- ROS-2-Seite: grundsätzlich plausibel")
    else:
        print("- ROS-2-Seite: wahrscheinlich OK")
        print("- Standalone-CMake für unitree_sdk2: aktuell nicht nachweisbar")
        print("- Empfehlung: /opt/ros/foxy prüfen oder CycloneDDS separat nach ~/cyclonedds/install bauen")

    print("\nDirekttests:")
    print("  find /opt/ros/foxy /usr /usr/local ~/cyclonedds -name 'CycloneDDSConfig.cmake' 2>/dev/null")
    print("  cd ~/unitree_sdk2 && mkdir -p build && cd build && cmake .. -DCMAKE_PREFIX_PATH=/opt/ros/foxy")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAbgebrochen.")
        sys.exit(130)