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

check_display_access() {
  if [ -z "$DISPLAY" ]; then
    echo "[FEHLER] DISPLAY ist nicht gesetzt."
    echo "[HINWEIS] Bitte das Skript aus einer grafischen Sitzung heraus starten."
    exit 1
  fi

  if ! command -v xhost >/dev/null 2>&1; then
    echo "[FEHLER] xhost wurde nicht gefunden."
    echo "[HINWEIS] Bitte installiere x11-xserver-utils auf dem Host."
    exit 1
  fi

  echo "[INFO] Aktuelles DISPLAY:"
  echo "$DISPLAY"

  echo "[INFO] Aktuelle xhost-Freigaben:"
  xhost

  echo "[INFO] Erlaube root den Zugriff auf den X11-Server"
  xhost +SI:localuser:root >/dev/null
}

check_docker_installed
check_docker_access
check_nvidia_container_toolkit
check_display_access

mkdir -p "$HOME/Downloads"
mkdir -p "$HOME/unitree_ws"

if [ "$(docker ps -a -q -f name=^/${CONTAINER_NAME}$)" ]; then
  echo "[INFO] Container existiert bereits"
  echo "[HINWEIS] Falls du neue Mounts oder DISPLAY-Settings hinzugefügt hast, musst du den Container einmal löschen und neu erstellen:"
  echo "          docker rm -f $CONTAINER_NAME"

  if [ "$(docker ps -q -f name=^/${CONTAINER_NAME}$)" ]; then
    echo "[INFO] Container läuft bereits -> neue Shell"
    docker exec -it "$CONTAINER_NAME" bash
  else
    echo "[INFO] Starte bestehenden Container"
    docker start "$CONTAINER_NAME"
    docker exec -it "$CONTAINER_NAME" bash
  fi
else
  echo "[INFO] Erstelle neuen Container auf Basis von $IMAGE_NAME"

  docker run -it \
    --name "$CONTAINER_NAME" \
    --gpus all \
    --network host \
    --privileged \
    -e DISPLAY="$DISPLAY" \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -v "$HOME/Downloads:/root/Downloads" \
    -v "$HOME/unitree_ws:/root" \
    "$IMAGE_NAME"
fi