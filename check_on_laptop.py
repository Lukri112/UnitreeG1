#!/usr/bin/env python3
"""
Unitree G1 ROS2 Foxy Environment Checker

Ziel:
- Prüft, ob dein PC so eingerichtet ist, dass du die ROS2-Nodes / Topics
  eines Unitree G1 mit dem offiziellen unitree_ros2-Setup auslesen kannst.
- Fokus: ROS2 Foxy + CycloneDDS + Unitree unitree_ros2 Repo

Getestete Idee laut offiziellem Repo:
- /opt/ros/foxy/setup.bash vorhanden
- ros-foxy-rmw-cyclonedds-cpp installiert
- ros-foxy-rosidl-generator-dds-idl installiert
- libyaml-cpp-dev installiert
- unitree_ros2 vorhanden
- cyclonedds_ws gebaut
- setup.sh vorhanden und enthält:
  - source /opt/ros/foxy/setup.bash
  - export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
  - export CYCLONEDDS_URI=...
- Netzwerkinterface hat statische IP 192.168.123.222/24
- Optional: Runtime-Test via "source setup.sh && ros2 topic list"
- Optional: prüft, ob das G1-Beispiel read_low_state_hg gebaut wurde
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shlex
import shutil
import socket
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


EXPECTED_IP = "192.168.123.222"
EXPECTED_PREFIXLEN = "24"
EXPECTED_MASK = "255.255.255.0"
REQUIRED_APT_PACKAGES = [
    "ros-foxy-rmw-cyclonedds-cpp",
    "ros-foxy-rosidl-generator-dds-idl",
    "libyaml-cpp-dev",
]
OPTIONAL_TOOLS = [
    "ros2",
    "colcon",
    "git",
    "ip",
]
IMPORTANT_RUNTIME_TOPICS = [
    # G1-spezifische Topics können je nach Firmware/Stack variieren.
    # Wir prüfen daher primär, ob überhaupt Topics sichtbar werden.
    # Diese beiden sind nützlich als weiche Hinweise:
    "/sportmodestate",   # eher im offiziellen README als Testtopic gezeigt
    "/wirelesscontroller",
]


@dataclass
class CheckResult:
    ok: bool
    title: str
    details: str
    fix: Optional[str] = None


@dataclass
class Report:
    results: List[CheckResult] = field(default_factory=list)

    def add(self, ok: bool, title: str, details: str, fix: Optional[str] = None) -> None:
        self.results.append(CheckResult(ok=ok, title=title, details=details, fix=fix))

    @property
    def failed(self) -> List[CheckResult]:
        return [r for r in self.results if not r.ok]

    @property
    def passed(self) -> List[CheckResult]:
        return [r for r in self.results if r.ok]

    def exit_code(self) -> int:
        return 0 if not self.failed else 1

    def print(self) -> None:
        print("=" * 78)
        print("Unitree G1 ROS2 Foxy Setup Check")
        print("=" * 78)
        print()

        for r in self.results:
            prefix = "OK  " if r.ok else "FAIL"
            print(f"[{prefix}] {r.title}")
            print(f"      {r.details}")
            if r.fix:
                print(f"      Fix: {r.fix}")
            print()

        print("-" * 78)
        print(f"Bestanden: {len(self.passed)}")
        print(f"Fehler:    {len(self.failed)}")
        print("-" * 78)

        if self.failed:
            print("\nZusammenfassung: Dein Setup ist NOCH NICHT vollständig korrekt.")
            print("Behebe zuerst die FAIL-Punkte oben.")
        else:
            print("\nZusammenfassung: Dein Setup sieht korrekt aus.")
            print("Du solltest die Unitree-G1-ROS2-Nodes/Topics auslesen können.")


def run_cmd(cmd: List[str], shell: bool = False, timeout: int = 20) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(
            cmd if not shell else " ".join(shlex.quote(x) for x in cmd),
            shell=shell,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except subprocess.TimeoutExpired:
        return 124, "", "Command timed out"
    except Exception as e:
        return 1, "", str(e)


def run_bash(command: str, timeout: int = 20) -> Tuple[int, str, str]:
    return run_cmd(["bash", "-lc", command], timeout=timeout)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def dpkg_installed(pkg: str) -> bool:
    code, out, _ = run_cmd(["dpkg-query", "-W", "-f=${Status}", pkg])
    return code == 0 and "install ok installed" in out


def get_ubuntu_version() -> Optional[str]:
    os_release = Path("/etc/os-release")
    if not os_release.exists():
        return None
    data = os_release.read_text(encoding="utf-8", errors="ignore")
    match = re.search(r'^VERSION_ID="?([^"\n]+)"?', data, re.MULTILINE)
    return match.group(1) if match else None


def get_iface_ipv4(iface: str) -> Tuple[Optional[str], Optional[str]]:
    code, out, _ = run_cmd(["ip", "-4", "addr", "show", "dev", iface])
    if code != 0:
        return None, None

    # Beispiel: inet 192.168.123.99/24 brd ...
    match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", out)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def parse_interface_from_setup(setup_path: Path) -> Optional[str]:
    text = setup_path.read_text(encoding="utf-8", errors="ignore")
    # sucht name="enp3s0"
    match = re.search(r'NetworkInterface\s+name="([^"]+)"', text)
    return match.group(1) if match else None


def file_contains(path: Path, needle: str) -> bool:
    if not path.exists():
        return False
    try:
        return needle in path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False


def topic_list_via_setup(setup_path: Path, timeout: int = 15) -> Tuple[int, List[str], str]:
    cmd = f"source {shlex.quote(str(setup_path))} >/dev/null 2>&1 && ros2 topic list"
    code, out, err = run_bash(cmd, timeout=timeout)
    topics = [line.strip() for line in out.splitlines() if line.strip()]
    return code, topics, err


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prüft dein Unitree G1 ROS2 Foxy Setup"
    )
    parser.add_argument(
        "--repo",
        default=str(Path.home() / "unitree_ros2"),
        help="Pfad zum unitree_ros2 Repo (Default: ~/unitree_ros2)",
    )
    parser.add_argument(
        "--iface",
        default=None,
        help="Ethernet-Interface zum Roboter, z. B. enp3s0. "
             "Wenn nicht gesetzt, wird versucht, es aus setup.sh zu lesen.",
    )
    parser.add_argument(
        "--runtime-test",
        action="store_true",
        help="Führt einen Runtime-Test mit 'source setup.sh && ros2 topic list' aus.",
    )
    parser.add_argument(
        "--strict-ubuntu-20",
        action="store_true",
        help="Schlägt fehl, wenn das OS nicht Ubuntu 20.04 ist. "
             "Nützlich, wenn du Foxy strikt auf Focal erzwingen willst.",
    )
    args = parser.parse_args()

    report = Report()
    repo = Path(args.repo).expanduser().resolve()
    setup_sh = repo / "setup.sh"
    setup_local_sh = repo / "setup_local.sh"
    cyclonedds_ws = repo / "cyclonedds_ws"
    cyclonedds_install_setup = cyclonedds_ws / "install" / "setup.bash"
    example_dir = repo / "example"
    example_bin = example_dir / "install" / "unitree_ros2_example" / "bin" / "read_low_state_hg"

    # 1) OS prüfen
    system = platform.system()
    ubuntu_version = get_ubuntu_version()
    if system != "Linux":
        report.add(
            False,
            "Betriebssystem",
            f"Gefunden: {system}",
            "Nutze Ubuntu Linux für das offizielle Unitree-ROS2-Foxy-Setup.",
        )
    else:
        details = f"Linux erkannt"
        if ubuntu_version:
            details += f", Ubuntu-Version: {ubuntu_version}"
        if args.strict_ubuntu_20 and ubuntu_version != "20.04":
            report.add(
                False,
                "Ubuntu-Version",
                details,
                "Für ROS2 Foxy ist Ubuntu 20.04 der saubere Standard. "
                "Nutze Ubuntu 20.04/Focal oder prüfe bewusst dein abweichendes Setup.",
            )
        else:
            report.add(True, "Betriebssystem", details)

    # 2) Tools prüfen
    for tool in OPTIONAL_TOOLS:
        ok = command_exists(tool)
        report.add(
            ok,
            f"Tool vorhanden: {tool}",
            f"{tool} {'gefunden' if ok else 'nicht gefunden'}",
            None if ok else f"Installiere '{tool}' und stelle sicher, dass es im PATH liegt.",
        )

    # 3) ROS2 Foxy prüfen
    foxy_setup = Path("/opt/ros/foxy/setup.bash")
    report.add(
        foxy_setup.exists(),
        "ROS2 Foxy installiert",
        f"{foxy_setup} {'vorhanden' if foxy_setup.exists() else 'nicht vorhanden'}",
        None if foxy_setup.exists() else "Installiere ROS2 Foxy, sodass /opt/ros/foxy/setup.bash existiert.",
    )

    # 4) APT-Pakete prüfen
    for pkg in REQUIRED_APT_PACKAGES:
        ok = dpkg_installed(pkg)
        report.add(
            ok,
            f"Paket installiert: {pkg}",
            f"{pkg} {'installiert' if ok else 'nicht installiert'}",
            None if ok else f"sudo apt install {pkg}",
        )

    # 5) Repo-Struktur prüfen
    report.add(
        repo.exists(),
        "unitree_ros2 Repo",
        f"Repo-Pfad: {repo}",
        None if repo.exists() else f"Clone das Repo nach {repo}",
    )

    if repo.exists():
        report.add(
            cyclonedds_ws.exists(),
            "cyclonedds_ws vorhanden",
            f"{cyclonedds_ws} {'gefunden' if cyclonedds_ws.exists() else 'fehlt'}",
            None if cyclonedds_ws.exists() else "Prüfe, ob du das richtige unitree_ros2 Repo geklont hast.",
        )
        report.add(
            example_dir.exists(),
            "example Workspace vorhanden",
            f"{example_dir} {'gefunden' if example_dir.exists() else 'fehlt'}",
            None if example_dir.exists() else "Prüfe, ob dein Repo vollständig ist.",
        )
        report.add(
            setup_sh.exists(),
            "setup.sh vorhanden",
            f"{setup_sh} {'gefunden' if setup_sh.exists() else 'fehlt'}",
            None if setup_sh.exists() else "Lege setup.sh nach offiziellem Unitree-Schema an.",
        )

    # 6) cyclonedds Build prüfen
    report.add(
        cyclonedds_install_setup.exists(),
        "CycloneDDS/Workspace gebaut",
        f"{cyclonedds_install_setup} {'vorhanden' if cyclonedds_install_setup.exists() else 'fehlt'}",
        None if cyclonedds_install_setup.exists() else (
            f"Baue den Workspace: cd {shlex.quote(str(cyclonedds_ws))} && "
            "source /opt/ros/foxy/setup.bash && colcon build"
        ),
    )

    # 7) setup.sh Inhalt prüfen
    if setup_sh.exists():
        has_source_foxy = file_contains(setup_sh, "source /opt/ros/foxy/setup.bash")
        has_rmw = file_contains(setup_sh, "export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp")
        has_uri = file_contains(setup_sh, "export CYCLONEDDS_URI=")

        report.add(
            has_source_foxy,
            "setup.sh sourced ROS2 Foxy",
            "setup.sh enthält source /opt/ros/foxy/setup.bash" if has_source_foxy else
            "setup.sh enthält NICHT source /opt/ros/foxy/setup.bash",
            None if has_source_foxy else "Füge 'source /opt/ros/foxy/setup.bash' in setup.sh ein.",
        )
        report.add(
            has_rmw,
            "setup.sh setzt RMW_IMPLEMENTATION",
            "rmw_cyclonedds_cpp gesetzt" if has_rmw else "rmw_cyclonedds_cpp NICHT gesetzt",
            None if has_rmw else "Füge 'export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp' ein.",
        )
        report.add(
            has_uri,
            "setup.sh setzt CYCLONEDDS_URI",
            "CYCLONEDDS_URI vorhanden" if has_uri else "CYCLONEDDS_URI fehlt",
            None if has_uri else "Füge CYCLONEDDS_URI mit deinem Robot-Netzwerkinterface ein.",
        )
    else:
        has_source_foxy = has_rmw = has_uri = False

    # 8) Interface bestimmen
    iface = args.iface
    if not iface and setup_sh.exists():
        iface = parse_interface_from_setup(setup_sh)

    if iface:
        report.add(True, "Ethernet-Interface bestimmt", f"Verwende Interface: {iface}")
        ip_addr, prefix = get_iface_ipv4(iface)
        if ip_addr is None:
            report.add(
                False,
                "IPv4 auf Interface",
                f"Konnte keine IPv4-Adresse auf {iface} finden oder Interface existiert nicht nicht.",
                f"Prüfe den Interface-Namen mit 'ip link' und setze die statische IP auf "
                f"{EXPECTED_IP}/{EXPECTED_PREFIXLEN}.",
            )
        else:
            ip_ok = (ip_addr == EXPECTED_IP and prefix == EXPECTED_PREFIXLEN)
            report.add(
                ip_ok,
                "Statische Robot-IP",
                f"{iface} hat {ip_addr}/{prefix}",
                None if ip_ok else (
                    f"Setze IPv4 manuell auf {EXPECTED_IP} mit Maske {EXPECTED_MASK} "
                    f"(Prefix /{EXPECTED_PREFIXLEN})."
                ),
            )
    else:
        report.add(
            False,
            "Ethernet-Interface",
            "Konnte kein Interface bestimmen.",
            "Gib --iface enp3s0 an oder trage dein Interface korrekt in setup.sh ein.",
        )

    # 9) Beispielbinary prüfen
    report.add(
        example_bin.exists(),
        "G1 Beispiel read_low_state_hg gebaut",
        f"{example_bin} {'gefunden' if example_bin.exists() else 'nicht gefunden'}",
        None if example_bin.exists() else (
            f"Baue die Beispiele: source {shlex.quote(str(setup_sh))} && "
            f"cd {shlex.quote(str(example_dir))} && colcon build"
        ) if setup_sh.exists() and example_dir.exists() else
        "Baue erst unitree_ros2/example erfolgreich.",
    )

    # 10) setup.sh tatsächlich sourcebar?
    if setup_sh.exists():
        code, _, err = run_bash(f"source {shlex.quote(str(setup_sh))}", timeout=10)
        report.add(
            code == 0,
            "setup.sh ausführbar/sourcebar",
            "setup.sh lässt sich sourcen" if code == 0 else f"Fehler beim Sourcen: {err}",
            None if code == 0 else "Prüfe Pfade in setup.sh und ob alle install/setup.bash-Dateien existieren.",
        )

    # 11) Optionaler Runtime-Test
    if args.runtime_test and setup_sh.exists():
        code, topics, err = topic_list_via_setup(setup_sh, timeout=20)
        if code != 0:
            report.add(
                False,
                "Runtime-Test: ros2 topic list",
                f"Fehlgeschlagen: {err or 'unbekannter Fehler'}",
                "Prüfe Ethernet-Verbindung zum G1, IP-Adresse, setup.sh, CycloneDDS und ob der Roboter erreichbar ist.",
            )
        else:
            if topics:
                report.add(
                    True,
                    "Runtime-Test: ros2 topic list",
                    f"{len(topics)} Topics gefunden, z. B.: {', '.join(topics[:5])}",
                )
            else:
                report.add(
                    False,
                    "Runtime-Test: ros2 topic list",
                    "Befehl lief, aber es wurden keine Topics gefunden.",
                    "Prüfe, ob der Roboter per Ethernet verbunden ist, eingeschaltet ist und ob dein DDS/Netzwerk korrekt steht.",
                )

            found_important = [t for t in IMPORTANT_RUNTIME_TOPICS if t in topics]
            if found_important:
                report.add(
                    True,
                    "Bekannte Unitree-Topics sichtbar",
                    f"Gefunden: {', '.join(found_important)}",
                )
            else:
                report.add(
                    True,
                    "Bekannte Unitree-Topics sichtbar",
                    "Keines der weichen Referenz-Topics wurde gefunden. "
                    "Das ist nicht zwingend ein Fehler, solange andere sinnvolle Unitree-Topics sichtbar sind.",
                )

    # 12) Zusatzhinweis: setup_local.sh
    if setup_local_sh.exists():
        report.add(
            True,
            "setup_local.sh vorhanden",
            f"{setup_local_sh} gefunden",
        )

    report.print()
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())