# ROS-2-Foxy UDP Velocity Logger für Unitree G1

Diese Node dient zur standardisierten Vorgabe und Aufzeichnung von Velocity-Kommandos für Crouch-Walking-Versuche mit dem Unitree G1 EDU 29-DOF.

Workflow:

```text
ROS-2-Foxy-Node
  ├─ publiziert /cmd_vel zur Nachvollziehbarkeit
  ├─ sendet UDP [vx, vy, yaw_rate]
  ↓
gepatchter g1_controller / observations.h
  ↓
velocity_commands-Observation
  ↓
ONNX Crouch-Walking-Policy
  ↓
lowcmd → MuJoCo oder realer Unitree G1
```

Die Controller-seitige Änderung befindet sich in:

```text
unitree_rl_mjlab/deploy/include/isaaclab/envs/mdp/observations/observations.h
```

Dort wird die bestehende `velocity_commands`-Observation um einen UDP-Override erweitert: frische UDP-Kommandos haben Priorität, andernfalls bleibt das originale Joystick-/Wirelesscontroller-Verhalten aktiv.

---

## Datei

```text
g1_velocity_udp_logger_node.py
```

Funktionen:

```text
1. /cmd_vel publizieren
2. UDP-Kommando an g1_controller senden
3. IMU-Daten loggen
4. optional Odometrie loggen
5. Rohdaten-CSV schreiben
6. Summary-CSV mit Metriken schreiben
```

Unterstützte IMU-Typen:

```text
sensor_msgs/msg/Imu
unitree_hg/msg/IMUState
```

In der MuJoCo-Simulation ist `/secondary_imu` typischerweise `unitree_hg/msg/IMUState`.

---

## UDP-Format

Standard:

```text
UDP-IP:   127.0.0.1
UDP-Port: 5005
Paket:    3x float32 = [vx, vy, yaw_rate]
```

Beispiel:

```python
packet = struct.pack("fff", vx, vy, yaw_rate)
sock.sendto(packet, ("127.0.0.1", 5005))
```

`127.0.0.1` ist nur korrekt, wenn Node und `g1_ctrl` auf demselben Rechner laufen.

---

## Standardisiertes Versuchsprofil

```text
vx        = 0.30 m/s
vy        = 0.00 m/s
yaw_rate  = 0.50 rad/s
duration  = 10.0 s
rate      = 50 Hz
```

Dieses Profil kombiniert Vorwärtsbewegung und Rotation und bleibt innerhalb der `deploy.yaml`-Grenzen:

```text
lin_vel_x: [-0.5, 1.0]
lin_vel_y: [-0.5, 0.5]
ang_vel_z: [-1.0, 1.0]
```

---

## Voraussetzungen

ROS 2 Foxy unter Ubuntu 20.04 verwendet Python 3.8. Die Node daher mit System-Python starten, nicht mit Conda-Python:

```bash
conda deactivate
source /opt/ros/foxy/setup.bash
/usr/bin/python3 g1_velocity_udp_logger_node.py ...
```

Prüfen:

```bash
which python3
python3 --version
```

Erwartet:

```text
/usr/bin/python3
Python 3.8.x
```

---

## Simulation

Typische Simulations-Topics:

```text
/lowcmd
/lowstate
/secondary_imu
/sportmodestate
/wirelesscontroller
```

In der aktuellen MuJoCo-Simulation wird kein Odometrie-Topic veröffentlicht. Deshalb `enable_odom:=false` verwenden.

### Start

Terminal 1:

```bash
cd ~/unitree_rl_mjlab
./simulate/build/unitree_mujoco
```

Terminal 2:

```bash
source /opt/ros/foxy/setup.bash
source ~/unitree_ros2/setup_local.sh

cd ~/unitree_rl_mjlab/deploy/robots/g1/build
./g1_ctrl --network=lo
```

Terminal 3:

```bash
source /opt/ros/foxy/setup.bash
source ~/unitree_ros2/setup_local.sh

cd ~/unitree_rl_mjlab/scripts/metrics

/usr/bin/python3 g1_velocity_udp_logger_node.py \
  --ros-args \
  -p trial_id:=1 \
  -p vx:=0.30 \
  -p vy:=0.00 \
  -p yaw_rate:=0.50 \
  -p duration:=10.0 \
  -p publish_rate:=50.0 \
  -p udp_ip:=127.0.0.1 \
  -p udp_port:=5005 \
  -p imu_mode:=unitree_hg \
  -p imu_topic:=/secondary_imu \
  -p enable_odom:=false \
  -p csv_path:=sim_trial_001.csv
```

Erwartete Controller-Meldung:

```text
[velocity_commands] UDP override listening on port 5005.
```

### In der Simulation messbar

```text
Yaw-Rate-Tracking über IMU gyroscope.z
Roll-/Pitch-Stabilität
IMU-Beschleunigungsnorm
Fall-/Kippindikator über Roll/Pitch
UDP-Status
Laufzeit
```

Nicht messbar ohne Odometrie:

```text
vx_actual
vy_actual
Base Height
x/y-Position
zurückgelegte Distanz
```

Diese Werte bleiben in der Simulations-CSV als `NaN`.

---

## Realer Unitree G1

Relevante Topics können sein:

```text
/dog_imu_raw
/dog_odom
/secondary_imu
/lowstate
/sportmodestate
```

Vorher prüfen:

```bash
ros2 topic type /dog_imu_raw
ros2 topic type /dog_odom
```

Wenn `/dog_imu_raw` `sensor_msgs/msg/Imu` ist:

```bash
source /opt/ros/foxy/setup.bash
source ~/unitree_ros2/setup.sh

cd ~/unitree_rl_mjlab/scripts/metrics

/usr/bin/python3 g1_velocity_udp_logger_node.py \
  --ros-args \
  -p trial_id:=1 \
  -p vx:=0.30 \
  -p vy:=0.00 \
  -p yaw_rate:=0.50 \
  -p duration:=10.0 \
  -p publish_rate:=50.0 \
  -p udp_ip:=127.0.0.1 \
  -p udp_port:=5005 \
  -p imu_mode:=sensor_msgs \
  -p imu_topic:=/dog_imu_raw \
  -p enable_odom:=true \
  -p odom_topic:=/dog_odom \
  -p csv_path:=real_trial_001.csv
```

Wenn das IMU-Topic `unitree_hg/msg/IMUState` ist:

```bash
-p imu_mode:=unitree_hg
```

---

## CSV-Ausgaben

Pro Versuch entstehen zwei Dateien.

### Rohdaten-CSV

Beispiel:

```text
sim_trial_001.csv
real_trial_001.csv
```

Wichtige Spalten:

```text
time_s
phase
vx_cmd_mps
vy_cmd_mps
yaw_rate_cmd_radps
udp_sent

imu_roll_rad
imu_pitch_rad
imu_yaw_rad
imu_ang_vel_z_radps
imu_lin_acc_norm_mps2

odom_vx_mps
odom_vy_mps
odom_z_m_base_height
odom_yaw_rate_radps

vx_error_odom_mps
vy_error_odom_mps
yaw_rate_error_imu_radps
yaw_rate_error_odom_radps

fall_threshold_exceeded
passive_mode_triggered_manual
fall_detected_manual
```

### Summary-CSV

Beispiel:

```text
sim_trial_001_summary.csv
real_trial_001_summary.csv
```

Wichtige Metriken:

```text
successful_trial
runtime_actual_s
sample_count_active

imu_yaw_rate_mean_radps
imu_yaw_rate_std_radps
imu_yaw_rate_rmse_radps

odom_vx_mean_mps
odom_vy_mean_mps
odom_yaw_rate_mean_radps

odom_vx_rmse_mps
odom_vy_rmse_mps
odom_yaw_rate_rmse_radps

base_height_mean_m
base_height_std_m
base_height_min_m
base_height_max_m

imu_roll_abs_max_rad
imu_pitch_abs_max_rad
imu_acc_norm_mean_mps2
imu_acc_norm_std_mps2
```

In der Simulation sind odometriebasierte Werte `NaN`, solange kein Odometrie-Publisher vorhanden ist.

---

## Bewertungsmetriken

Die Node ist auf die Bewertung der Crouch-Walking-Policy ausgelegt:

```text
Erfolgsstatus
Laufdauer
Passive-Mode-Markierung
Fallindikator
Yaw-Rate-Tracking
Velocity-Tracking, falls Odometrie verfügbar
Base-Height-Stabilität, falls Odometrie verfügbar
Roll-/Pitch-Stabilität
IMU-Beschleunigungsniveau
```

Fehlergrößen:

```text
yaw_rate_error_imu  = yaw_rate_cmd - imu_angular_velocity_z
yaw_rate_error_odom = yaw_rate_cmd - odom_yaw_rate
vx_error_odom       = vx_cmd - odom_vx
vy_error_odom       = vy_cmd - odom_vy
```

RMSE-Werte werden nur über die aktive Kommando-Phase berechnet.

---

## Manuelle Annotationen

Für Ereignisse, die nicht zuverlässig automatisch erkannt werden:

```text
passive_mode_triggered
fall_detected_manual
operator_note
```

Beispiel:

```bash
-p passive_mode_triggered:=true \
-p operator_note:="unexplained passive mode without recorded fall"
```

---

## Sicherheit

Nach der aktiven Versuchsdauer sendet die Node standardmäßig 1 s lang Nullkommandos:

```text
send_zero_after_duration_s = 1.0
```

Dies gilt für `/cmd_vel` und UDP. Zusätzlich besitzt der Controller-seitige UDP-Override ein Timeout; ohne frisches UDP-Paket fällt der Controller auf das originale Joystick-/Wirelesscontroller-Verhalten zurück.

---

## Troubleshooting

### `rclpy._rclpy` fehlt

Ursache: falsche Python-Version, meist Conda.

```bash
conda deactivate
source /opt/ros/foxy/setup.bash
/usr/bin/python3 g1_velocity_udp_logger_node.py ...
```

### Keine IMU-Daten

Topic-Typ prüfen:

```bash
ros2 topic type /secondary_imu
ros2 topic type /dog_imu_raw
```

Dann passenden Modus wählen:

```bash
-p imu_mode:=unitree_hg
```

oder:

```bash
-p imu_mode:=sensor_msgs
```

### Keine Odometrie

Simulation:

```bash
-p enable_odom:=false
```

Realer Roboter:

```bash
-p enable_odom:=true
-p odom_topic:=/dog_odom
```

### UDP wirkt nicht

Prüfen:

```text
[velocity_commands] UDP override listening on port 5005.
udp_ip   = 127.0.0.1
udp_port = 5005
```

`127.0.0.1` nur verwenden, wenn Node und `g1_ctrl` auf demselben Rechner laufen.

---

## Hinweis für die Masterarbeit

Die MuJoCo-Sim2Sim-Stufe liefert in dieser Konfiguration quantitative IMU-Metriken, insbesondere Yaw-Rate-Tracking sowie Roll-/Pitch-Stabilität. Translatorische Geschwindigkeit und Base Height erfordern Odometrie und werden daher im Realversuch über `/dog_odom` ausgewertet.

Damit dient Sim2Sim primär der funktionalen Prüfung der Deployment-Kette, während die vollständige quantitative Bewertung in den Realversuchen erfolgt.
