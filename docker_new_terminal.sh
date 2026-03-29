#!/bin/bash

echo "[INFO] Prüfe DISPLAY im Container..."
echo "$DISPLAY"

echo "[INFO] Prüfe X11-Socket..."
ls /tmp/.X11-unix || true

if [ -z "$DISPLAY" ] || [ ! -d /tmp/.X11-unix ]; then
  echo
  echo "[FEHLER] Im Docker-Container wurde kein funktionierendes Display/X11 gefunden."
  echo "[HINWEIS] Bitte führe auf dem HOST-Terminal diese Befehle aus:"
  echo
  echo "  xhost +SI:localuser:root"
  echo "  echo \$DISPLAY"
  echo "  xhost"
  echo
  echo "[HINWEIS] Starte danach den Container bzw. dieses Skript erneut."
  exit 1
fi

alias ls='/bin/ls --color=auto'
alias ll='/bin/ls -alF'

echo
echo "[INFO] Prüfe NVIDIA/OpenGL..."
if command -v glxinfo >/dev/null 2>&1; then
  glxinfo | grep "OpenGL renderer" || true
  glxinfo | grep "OpenGL vendor" || true
else
  echo "[WARN] glxinfo wurde nicht gefunden."
  echo "[HINWEIS] Installiere es im Container bei Bedarf mit:"
  echo "          apt update && apt install -y mesa-utils"
fi

echo
echo "[INFO] Source ROS/Foxy + CycloneDDS + Unitree setup..."
source /opt/ros/foxy/setup.bash
source ~/unitree_ros2/cyclonedds_ws/install/setup.bash
source ~/unitree_ros2/setup_local.sh
export CYCLONEDDS_HOME=~/unitree_ros2/cyclonedds_ws/install

echo
echo "[INFO] Setze MuJoCo-Pfade..."
export LD_LIBRARY_PATH=/root/.mujoco/mujoco-3.3.6/build/lib:/root/.mujoco/mujoco-3.3.6/lib:$LD_LIBRARY_PATH    
export LIBRARY_PATH=/root/.mujoco/mujoco-3.3.6/build/lib:/root/.mujoco/mujoco-3.3.6/lib:$LIBRARY_PATH
export CPATH=/root/.mujoco/mujoco-3.3.6/include:/root/.mujoco/mujoco-3.3.6/simulate:$CPATH

echo
echo "[OK] Umgebung wurde gesetzt."
echo "[INFO] DISPLAY=$DISPLAY"
echo "[INFO] LD_LIBRARY_PATH=$LD_LIBRARY_PATH"
echo "[INFO] LIBRARY_PATH=$LIBRARY_PATH"
echo "[INFO] CPATH=$CPATH"