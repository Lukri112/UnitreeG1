# UDP-basierte Velocity-Command-Schnittstelle für den Unitree G1 Controller

Dieses Dokument beschreibt die Erweiterung der `velocity_commands`-Observation im MJLab-/Unitree-G1-Deployment. Ziel der Änderung ist es, standardisierte Geschwindigkeitskommandos für Sim2Sim- und Sim-to-Real-Experimente vorgeben zu können, ohne den bestehenden Unitree-/MJLab-Controller grundlegend umzubauen.

Die Änderung betrifft die Datei:

```text
unitree_rl_mjlab/deploy/include/isaaclab/envs/mdp/observations/observations.h
```

Die `deploy.yaml` der Policy bleibt unverändert. Insbesondere bleibt die Observation weiterhin:

```yaml
observations:
  velocity_commands:
    params: {command_name: base_velocity}
    clip: null
    scale: [1.0, 1.0, 1.0]
    history_length: 1
```

---

## Motivation

Für die experimentelle Bewertung der Crouch-Walking-Policy sollen identische Geschwindigkeitskommandos in MuJoCo-Simulation und auf dem realen Unitree G1 EDU 29-DOF verwendet werden.

Das standardisierte Versuchsprofil lautet:

```text
vx        = 0.30 m/s
vy        = 0.00 m/s
yaw_rate  = 0.50 rad/s
duration  = 10.0 s
rate      = 50 Hz
```

Die in der Deployment-Konfiguration definierten Command-Grenzen bleiben gültig:

```yaml
lin_vel_x: [-0.5, 1.0]
lin_vel_y: [-0.5, 0.5]
ang_vel_z: [-1.0, 1.0]
```

Damit liegt das gewählte Versuchsprofil innerhalb der zulässigen Bereiche.

---

## Warum UDP statt direktem ROS2-Subscriber im C++-Controller?

Ein direkter Einbau von `rclcpp` und `geometry_msgs` in den `g1_controller` kann zu Konflikten zwischen der vom Unitree SDK verwendeten DDS-/CycloneDDS-Installation und der ROS2-Foxy-DDS-Infrastruktur führen.

Deshalb wurde der Controller nicht zu einer ROS2-Node umgebaut. Stattdessen wird eine einfache UDP-Schnittstelle verwendet:

```text
ROS2-Foxy-Node
    publisht optional /cmd_vel
    sendet zusätzlich UDP-Paket [vx, vy, yaw_rate]
        ↓
g1_controller
    empfängt UDP-Paket auf Port 5005
    überschreibt damit velocity_commands
        ↓
ONNX Policy
        ↓
lowcmd / Motorbefehle
```

Der Vorteil ist, dass der bestehende Unitree-/DDS-Controller weitgehend unverändert bleibt und keine zusätzliche ROS2-Abhängigkeit im C++-Controller benötigt wird.

---

## Funktionsweise der Änderung

Die originale `velocity_commands`-Observation liest die Geschwindigkeitsvorgabe aus dem Joystick-/Wirelesscontroller-Zustand:

```cpp
obs[0] = std::clamp(joystick->ly(),  ...);
obs[1] = std::clamp(-joystick->lx(), ...);
obs[2] = std::clamp(-joystick->rx(), ...);
```

Die Erweiterung fügt davor einen UDP-Override ein.

Die neue Priorität lautet:

```text
1. Frisches UDP-Paket vorhanden:
       velocity_commands = [vx, vy, yaw_rate] aus UDP

2. Kein frisches UDP-Paket vorhanden:
       originales Joystick-Verhalten

3. UDP-Socket kann nicht geöffnet werden:
       originales Joystick-Verhalten
```

Dadurch bleibt der Controller ohne aktiven UDP-Sender vollständig kompatibel mit dem ursprünglichen Verhalten.

---

## UDP-Paketformat

Der Controller lauscht auf:

```text
UDP-Port: 5005
```

Das Paket besteht aus drei `float32`-Werten in dieser Reihenfolge:

```text
[vx, vy, yaw_rate]
```

Bedeutung:

```text
vx        Vorwärts-/Rückwärtsgeschwindigkeit [m/s]
vy        laterale Geschwindigkeit [m/s]
yaw_rate  Giergeschwindigkeit [rad/s]
```

Beispiel:

```python
packet = struct.pack("fff", 0.30, 0.00, 0.50)
sock.sendto(packet, ("127.0.0.1", 5005))
```

---

## Timeout-Verhalten

Ein UDP-Kommando wird nur verwendet, wenn es höchstens `0.5 s` alt ist:

```cpp
constexpr double UDP_CMD_TIMEOUT_S = 0.5;
```

Wenn länger als `0.5 s` kein gültiges UDP-Paket empfangen wurde, fällt die `velocity_commands`-Observation automatisch auf das originale Joystick-Verhalten zurück.

Dadurch wird verhindert, dass ein alter Geschwindigkeitsbefehl dauerhaft aktiv bleibt, falls die sendende Node beendet wird oder abstürzt.

---

## Test in MuJoCo / Sim2Sim

### 1. MuJoCo starten

```bash
cd ~/unitree_rl_mjlab
./simulate/build/unitree_mujoco
```

### 2. Controller starten

```bash
cd ~/unitree_rl_mjlab/deploy/robots/g1/build
./g1_ctrl --network=lo
```

Beim ersten Aufruf der `velocity_commands`-Observation sollte eine Meldung erscheinen:

```text
[velocity_commands] UDP override listening on port 5005.
```

### 3. UDP-Testkommando senden

```bash
python3 - << 'EOF'
import socket
import struct
import time

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

vx = 0.30
vy = 0.00
yaw_rate = 0.50

duration = 10.0
rate = 50.0
dt = 1.0 / rate

for _ in range(int(duration * rate)):
    packet = struct.pack("fff", vx, vy, yaw_rate)
    sock.sendto(packet, ("127.0.0.1", 5005))
    time.sleep(dt)

# Optional: 1 s Nullkommando senden
for _ in range(int(1.0 * rate)):
    packet = struct.pack("fff", 0.0, 0.0, 0.0)
    sock.sendto(packet, ("127.0.0.1", 5005))
    time.sleep(dt)
EOF
```

---

## Empfohlenes standardisiertes Versuchsprofil

Für die finale Bewertung wurde folgendes Profil gewählt:

```text
vx        = 0.30 m/s
vy        = 0.00 m/s
yaw_rate  = 0.50 rad/s
duration  = 10.0 s
rate      = 50 Hz
```

Dieses Profil erzeugt eine kombinierte Belastung aus Vorwärtsbewegung und Rotation. Es ist aussagekräftiger als ein rein geradliniger Test und bleibt gleichzeitig innerhalb der in `deploy.yaml` definierten Command-Grenzen.

---

## Erwartetes Verhalten

Ohne UDP-Sender:

```text
velocity_commands = originales Joystick-/Wirelesscontroller-Verhalten
```

Mit aktivem UDP-Sender:

```text
velocity_commands = UDP-Kommandos
```

Nach Stoppen des UDP-Senders:

```text
nach spätestens 0.5 s Rückfall auf Joystick-Verhalten
```

---

## Build-Hinweis

Für diese Änderung sind keine zusätzlichen ROS2-C++-Abhängigkeiten erforderlich.

Die `CMakeLists.txt` des `g1_controller` soll daher keine zusätzlichen Einträge wie diese enthalten:

```cmake
find_package(rclcpp REQUIRED)
find_package(geometry_msgs REQUIRED)
ament_target_dependencies(...)
```

Der normale Build bleibt:

```bash
cd ~/unitree_rl_mjlab/deploy/robots/g1
rm -rf build
mkdir build
cd build
cmake ..
make -j$(nproc)
```

---

## Wissenschaftliche Einordnung

Die UDP-Erweiterung dient der standardisierten Vorgabe von Geschwindigkeitskommandos während der Sim2Sim- und Sim-to-Real-Versuche. Sie verändert nicht die Struktur der Policy-Observation und nicht die Dimension des Actor-Inputs.

Die Policy erhält weiterhin die gleiche 98-dimensionale Beobachtung:

```text
base_ang_vel        3
projected_gravity   3
velocity_commands   3
gait_phase           2
joint_pos_rel       29
joint_vel_rel       29
last_action         29
----------------------
Summe               98
```

Nur die Quelle der drei `velocity_commands`-Werte wird bei aktivem UDP-Sender temporär überschrieben. Dadurch können reproduzierbare Kommandoprofile verwendet werden, ohne die trainierte ONNX-Policy oder die `deploy.yaml` zu verändern.

---

## Kurzfassung

```text
Datei:
    observations.h

Geänderte Funktion:
    REGISTER_OBSERVATION(velocity_commands)

Neue Funktion:
    UDP-Override für [vx, vy, yaw_rate]

Port:
    5005

Paket:
    3x float32 = vx, vy, yaw_rate

Fallback:
    originales Joystick-Verhalten

Timeout:
    0.5 s

Finales Testprofil:
    vx = 0.30 m/s
    vy = 0.00 m/s
    yaw_rate = 0.50 rad/s
    duration = 10 s
    rate = 50 Hz
```
