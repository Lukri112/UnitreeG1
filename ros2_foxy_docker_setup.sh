#!/bin/bash

set -e

CONTAINER_NAME="ros2_foxy_dev"
IMAGE_NAME="osrf/ros:foxy-desktop"

check_docker_installed() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "[INFO] Docker nicht gefunden -> Installation wird gestartet"
    sudo apt update
    sudo apt install -y docker.io
    sudo systemctl enable --now docker
    sudo usermod -aG docker "$USER"

    echo "[WARN] Du wurdest zur Docker-Gruppe hinzugefügt."
    echo "[WARN] Bitte jetzt neu anmelden oder den Rechner neu starten."
    echo "[WARN] Danach das Skript erneut OHNE sudo ausführen."
    exit 0
  else
    echo "[OK] Docker ist bereits installiert"
  fi
}

check_docker_access() {
  if ! docker ps >/dev/null 2>&1; then
    echo "[FEHLER] Kein Zugriff auf Docker."
    echo "[HINWEIS] Falls du gerade erst mit 'sudo usermod -aG docker \$USER' zur Docker-Gruppe hinzugefügt wurdest,"
    echo "          musst du dich neu anmelden oder den Rechner neu starten."
    echo "          Danach das Skript bitte erneut ohne sudo ausführen."
    exit 1
  fi
}

check_nvidia_container_toolkit() {
  if ! dpkg -s nvidia-container-toolkit >/dev/null 2>&1; then
    echo "[FEHLER] Das NVIDIA Container Toolkit ist nicht installiert."
    echo "[HINWEIS] Bitte installiere zuerst 'nvidia-container-toolkit' auf dem Host,"
    echo "          konfiguriere Docker mit 'sudo nvidia-ctk runtime configure --runtime=docker'"
    echo "          und starte Docker danach neu."
    exit 1
  fi

  if ! command -v nvidia-ctk >/dev/null 2>&1; then
    echo "[FEHLER] 'nvidia-ctk' wurde nicht gefunden, obwohl das NVIDIA Container Toolkit installiert sein sollte."
    echo "[HINWEIS] Bitte prüfe die Installation des NVIDIA Container Toolkits."
    exit 1
  fi

  if ! docker run --rm --gpus all ubuntu:22.04 nvidia-smi >/dev/null 2>&1; then
    echo "[FEHLER] Docker kann aktuell nicht mit GPU-Unterstützung starten."
    echo "[HINWEIS] Bitte prüfe:"
    echo "          1. NVIDIA-Treiber auf dem Host (nvidia-smi)"
    echo "          2. NVIDIA Container Toolkit"
    echo "          3. Docker Runtime-Konfiguration"
    echo "          Danach das Skript erneut starten."
    exit 1
  fi

  echo "[OK] NVIDIA Container Toolkit ist verfügbar"
}

check_docker_installed
check_docker_access
check_nvidia_container_toolkit

mkdir -p "$HOME/Downloads"
mkdir -p "$HOME/unitree_ws"

if [ "$(docker ps -a -q -f name=^/${CONTAINER_NAME}$)" ]; then
  echo "[INFO] Container existiert bereits"

  if [ "$(docker ps -q -f name=^/${CONTAINER_NAME}$)" ]; then
    echo "[INFO] Container läuft bereits -> attach"
    docker attach "$CONTAINER_NAME"
  else
    echo "[INFO] Starte bestehenden Container"
    docker start -ai "$CONTAINER_NAME"
  fi
else
  echo "[INFO] Erstelle neuen Container auf Basis von $IMAGE_NAME"

  docker run -it \
    --name "$CONTAINER_NAME" \
    --gpus all \
    --network host \
    --privileged \
    -v "$HOME/Downloads:/root/Downloads" \
    -v "$HOME/unitree_ws:/root/unitree_ws" \
    "$IMAGE_NAME"
fi