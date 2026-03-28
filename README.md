# Unitree G1

Dieses Repository dient als Ausgangspunkt für Inhalte, Code und Notizen rund um den **Unitree G1 Edu+**.

Der **Unitree G1 Edu+** ist ein humanoider Forschungs- und Entwicklungsroboter von Unitree Robotics. Er ist für Anwendungen in Forschung, Embodied AI, Bewegungssteuerung, Mensch-Roboter-Interaktion sowie algorithmische Entwicklung im Bereich humanoider Robotik interessant.

## Offizielle Ressourcen

- Unitree Robotics GitHub: <https://github.com/unitreerobotics>

## Hinweis

Dieses Repository ist aktuell bewusst schlank gehalten und kann später um Dokumentation, Setup-Anleitungen, SDK-Hinweise, Experimente oder Beispielcode erweitert werden.

## Setup

### Ubuntu 20.04:
  
  1.Download and run unitree_full_setup.py


### Ubuntu 22.04 / 24.04:
  1.Download and unitree_full_setup.py
  2.Download and run ros2_foxy_docker_setup.sh
  3.Inside the Docker Containe change to Downloads
    cd root/Downloads
  4.Install necessary tools 
    apt update
    apt upgrade
    apt install -y python3-pip sudo iproute2 git cmake
  5.Run python3 unitree_full_setup.py
  6.
    
