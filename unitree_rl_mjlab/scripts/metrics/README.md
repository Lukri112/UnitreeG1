# ROS-2-Foxy-UDP-Velocity-Logger für den Unitree G1

Diese README beschreibt die ROS-2-Foxy-Node zur standardisierten Vorgabe und Aufzeichnung von Velocity-Kommandos für die Crouch-Walking-Versuche mit dem Unitree G1 EDU 29-DOF.

Die Node ist für den folgenden Workflow vorgesehen:

```text
ROS-2-Foxy-Node
    publiziert /cmd_vel zur Nachvollziehbarkeit
    sendet UDP-Velocity-Command [vx, vy, yaw_rate]
        ↓
gepatchter g1_controller / observations.h
        ↓
velocity_commands-Observation
        ↓
ONNX Crouch-Walking Policy
        ↓
lowcmd / Unitree G1 oder MuJoCo-Simulation
```

Die zugehörige Änderung auf Controller-Seite befindet sich in:

```text
unitree_rl_mjlab/deploy/include/isaaclab/envs/mdp/observations/observations.h
```

Dort wurde die bestehende `velocity_commands`-Observation um einen UDP-Override erweitert. Wenn ein frisches UDP-Kommando verfügbar ist, wird dieses als Policy-Command verwendet. Wenn kein frisches UDP-Paket verfügbar ist, bleibt das originale Joystick-/Wirelesscontroller-Verhalten aktiv.

---

## Datei

```text
g1_velocity_udp_logger_node.py
```

Die Node übernimmt folgende Aufgaben:

```text
1. Publiziert das Sollkommando auf /cmd_vel.
2. Sendet dasselbe Kommando per UDP an den g1_controller.
3. Abonniert IMU-Daten.
4. Abonniert optional Odometrie-Daten.
5. Speichert alle Rohdaten in eine CSV-Datei.
6. Speichert zusammengefasste Versuchsmesswerte in eine Summary-CSV-Datei.
```

Die Node unterstützt zwei IMU-Nachrichtentypen:

```text
sensor_msgs/msg/Imu
unitree_hg/msg/IMUState
```

Der Typ `unitree_hg/msg/IMUState` wird in der MuJoCo-Simulation verwendet, da dort `/secondary_imu` in diesem Format veröffentlicht wird.

---

## UDP-Kommandoformat

Der Controller lauscht standardmäßig auf:

```text
UDP-IP:    127.0.0.1
UDP-Port:  5005
```

Das UDP-Paket besteht aus drei `float32`-Werten:

```text
[vx, vy, yaw_rate]
```

Bedeutung:

```text
vx        Vorwärts-/Rückwärtsgeschwindigkeit [m/s]
vy        laterale Geschwindigkeit [m/s]
yaw_rate  Giergeschwindigkeit [rad/s]
```

Python-Beispiel:

```python
packet = struct.pack("fff", vx, vy, yaw_rate)
sock.sendto(packet, ("127.0.0.1", 5005))
```

Wenn die ROS-2-Node und der `g1_controller` auf demselben Rechner laufen, wird `127.0.0.1` verwendet. Wenn der Controller auf einem anderen Rechner läuft, muss stattdessen dessen IP-Adresse verwendet werden.

---

## Finales Versuchsprofil

Für die standardisierten Crouch-Walking-Versuche wurde folgendes Profil gewählt:

```text
vx        = 0.30 m/s
vy        = 0.00 m/s
yaw_rate  = 0.50 rad/s
duration  = 10.0 s
rate      = 50 Hz
```

Dieses Profil kombiniert eine Vorwärtsbewegung mit einer Rotationsvorgabe. Es ist dadurch aussagekräftiger als ein rein geradliniger Test und bleibt gleichzeitig innerhalb der in der `deploy.yaml` definierten Command-Grenzen:

```text
lin_vel_x: [-0.5, 1.0]
lin_vel_y: [-0.5, 0.5]
ang_vel_z: [-1.0, 1.0]
```

---

## Voraussetzungen

Die Node ist für ROS 2 Foxy ausgelegt.

Wichtig: ROS 2 Foxy unter Ubuntu 20.04 verwendet Python 3.8. Die Node sollte daher mit dem System-Python gestartet werden, nicht mit einer Conda-Python-Version.

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

Falls Conda aktiv ist:

```bash
conda deactivate
```

Alternativ direkt mit System-Python starten:

```bash
/usr/bin/python3 g1_velocity_udp_logger_node.py
```

---

## Nutzung in der MuJoCo-Simulation

In der aktuellen MuJoCo-Simulation sind typischerweise folgende Topics verfügbar:

```text
/lowcmd
/lowstate
/secondary_imu
/sportmodestate
/wirelesscontroller
```

In dieser Simulationskonfiguration wird kein Odometrie-Topic veröffentlicht. Deshalb muss Odometrie-Logging in der Simulation deaktiviert werden.

### 1. MuJoCo starten

```bash
cd ~/unitree_rl_mjlab
./simulate/build/unitree_mujoco
```

### 2. g1_controller starten

In einem zweiten Terminal:

```bash
source /opt/ros/foxy/setup.bash
source ~/unitree_ros2/setup_local.sh

cd ~/unitree_rl_mjlab/deploy/robots/g1/build
./g1_ctrl --network=lo
```

Wenn der UDP-Override korrekt aktiv ist, sollte beim Start beziehungsweise beim ersten Aufruf der Observation folgende Meldung erscheinen:

```text
[velocity_commands] UDP override listening on port 5005.
```

### 3. Logger-Node starten

In einem dritten Terminal:

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

### Messbare Größen in der Simulation

In der Simulation können mit dieser Node folgende Größen ausgewertet werden:

```text
Yaw-Rate-Tracking über IMU gyroscope.z
Roll-/Pitch-Stabilität
IMU-Beschleunigungsnorm
Fall-/Kippindikator über Roll-/Pitch-Grenzen
UDP-Sendestatus
Laufzeit des Versuchs
```

Da aktuell kein Odometrie-Topic verfügbar ist, können in der Simulation folgende Größen nicht direkt gemessen werden:

```text
tatsächliche vx
tatsächliche vy
Base Height
x/y-Position
zurückgelegte Distanz
```

Diese Felder bleiben in der Simulations-CSV und Summary-CSV als `NaN` erhalten.

---

## Nutzung am realen Unitree G1

Am realen Roboter sind typischerweise zusätzliche Topics verfügbar, unter anderem:

```text
/dog_imu_raw
/dog_odom
/secondary_imu
/lowstate
/sportmodestate
```

Vor dem Start sollte der Nachrichtentyp geprüft werden:

```bash
ros2 topic type /dog_imu_raw
ros2 topic type /dog_odom
```

Wenn `/dog_imu_raw` den Typ `sensor_msgs/msg/Imu` verwendet:

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

Wenn das verwendete IMU-Topic den Typ `unitree_hg/msg/IMUState` verwendet, wird stattdessen gesetzt:

```bash
-p imu_mode:=unitree_hg
```

---

## Ausgabedateien

Pro Versuch erzeugt die Node zwei CSV-Dateien.

### Rohdaten-CSV

Beispiele:

```text
sim_trial_001.csv
real_trial_001.csv
```

Diese Datei enthält eine Zeile pro Messzeitpunkt. Wichtige Spalten sind:

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

Beispiele:

```text
sim_trial_001_summary.csv
real_trial_001_summary.csv
```

Diese Datei enthält zusammengefasste Versuchsmesswerte:

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

In der Simulation sind odometriebasierte Werte erwartungsgemäß `NaN`, solange kein Odometrie-Publisher vorhanden ist.

---

## Bewertungsmetriken

Die Node ist auf die Auswertung der Crouch-Walking-Policy ausgelegt. Relevante Metriken sind:

```text
Erfolgsstatus
Laufdauer
Passive-Mode-Markierung
Fallindikator
Yaw-Rate-Tracking
Velocity-Tracking, falls Odometrie verfügbar ist
Base-Height-Stabilität, falls Odometrie verfügbar ist
Roll-/Pitch-Stabilität
IMU-Beschleunigungsniveau
```

Die wichtigsten Fehlergrößen lauten:

```text
yaw_rate_error_imu  = yaw_rate_cmd - imu_angular_velocity_z
yaw_rate_error_odom = yaw_rate_cmd - odom_yaw_rate
vx_error_odom       = vx_cmd - odom_vx
vy_error_odom       = vy_cmd - odom_vy
```

Die RMSE-Werte werden ausschließlich über die aktive Kommando-Phase berechnet.

---

## Manuelle Annotationen

Nicht alle Ereignisse lassen sich automatisch aus IMU- oder Odometrie-Daten ableiten. Deshalb unterstützt die Node manuelle Markierungen:

```text
passive_mode_triggered
fall_detected_manual
operator_note
```

Beispiel für einen Versuch mit unerklärlicher Passive-Mode-Umschaltung ohne aufgezeichneten Sturz:

```bash
-p passive_mode_triggered:=true \
-p operator_note:="unexplained passive mode without recorded fall"
```

Diese Information wird in die Summary-CSV übernommen.

---

## Sicherheitsverhalten

Nach Ablauf der aktiven Versuchsdauer sendet die Node standardmäßig noch für eine Sekunde ein Nullkommando:

```text
send_zero_after_duration_s = 1.0
```

Dies gilt sowohl für `/cmd_vel` als auch für UDP.

Zusätzlich besitzt der Controller-seitige UDP-Override ein Timeout. Wenn kein frisches UDP-Paket empfangen wird, fällt der Controller automatisch auf das originale Joystick-/Wirelesscontroller-Verhalten zurück.

---

## Troubleshooting

### rclpy-Fehler

Wenn folgender Fehler erscheint:

```text
ModuleNotFoundError: No module named 'rclpy._rclpy'
```

wird die Node wahrscheinlich mit einer inkompatiblen Conda-Python-Version gestartet.

Lösung:

```bash
conda deactivate
source /opt/ros/foxy/setup.bash
/usr/bin/python3 g1_velocity_udp_logger_node.py ...
```

### Keine IMU-Daten in der CSV

Topic-Typ prüfen:

```bash
ros2 topic type /secondary_imu
ros2 topic type /dog_imu_raw
```

Wenn das Topic `unitree_hg/msg/IMUState` ist:

```bash
-p imu_mode:=unitree_hg
```

Wenn das Topic `sensor_msgs/msg/Imu` ist:

```bash
-p imu_mode:=sensor_msgs
```

### Keine Odometrie-Werte

In der aktuellen MuJoCo-Simulation wird kein Odometrie-Topic veröffentlicht. Deshalb in der Simulation verwenden:

```bash
-p enable_odom:=false
```

Am realen Roboter kann `/dog_odom` verwendet werden, sofern es als `nav_msgs/msg/Odometry` verfügbar ist.

### UDP-Kommando bewegt den Roboter nicht

Prüfen, ob der gepatchte `observations.h`-Code gebaut wurde und `g1_ctrl` folgende Meldung ausgibt:

```text
[velocity_commands] UDP override listening on port 5005.
```

Außerdem prüfen:

```text
udp_ip   = 127.0.0.1
udp_port = 5005
```

`127.0.0.1` ist nur korrekt, wenn Node und `g1_ctrl` auf demselben Rechner laufen.

---

## Hinweise für die Masterarbeit

Die MuJoCo-basierte Sim2Sim-Stufe liefert in dieser Konfiguration quantitative IMU-Metriken, insbesondere Yaw-Rate-Tracking sowie Roll-/Pitch-Stabilität. Eine vollständige Auswertung von translatorischer Geschwindigkeit und Base Height erfordert Odometrie und erfolgt daher auf dem realen Roboter über `/dog_odom`.

Die Sim2Sim-Stufe dient damit primär als funktionale Prüfung der Deployment-Kette. Die vollständige quantitative Bewertung von Velocity-Tracking, Base-Height-Stabilität, Erfolgsrate und Passive-Mode-Verhalten erfolgt in den standardisierten Realversuchen.
