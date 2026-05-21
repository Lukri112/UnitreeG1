# ROS-2-Foxy UDP Velocity Logger für Unitree G1

Diese README beschreibt die aktualisierte ROS-2-Foxy-Node `g1_velocity_udp_logger_node.py` für standardisierte Crouch-Walking-Versuche mit dem Unitree G1 EDU 29-DOF.

Die Node erfüllt drei Aufgaben gleichzeitig:

```text
1. Velocity-Kommando als /cmd_vel publizieren
2. Dasselbe Kommando per UDP an den gepatchten g1_controller senden
3. IMU- und optional Odometrie-/Motion-State-Daten als CSV aufzeichnen
```

Damit entsteht pro Versuch ein reproduzierbarer Datensatz aus Soll-Kommando, gemessener IMU-Stabilität, optionaler Odometrie und automatisch berechneten Summary-Metriken.

---

## Workflow

```text
ROS-2-Foxy-Node
  ├─ publiziert /cmd_vel zur Nachvollziehbarkeit
  ├─ sendet UDP-Paket [vx, vy, yaw_rate]
  ├─ liest IMU-Daten
  ├─ liest optional Motion-State/Odometrie
  └─ schreibt Raw-CSV und Summary-CSV
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

Dort wird die bestehende `velocity_commands`-Observation um einen UDP-Override erweitert. Frische UDP-Kommandos haben Priorität; ohne frisches UDP-Paket fällt der Controller wieder auf das originale Joystick-/Wirelesscontroller-Verhalten zurück.

---

## Datei

```text
g1_velocity_udp_logger_node.py
```

Die aktuelle Version unterstützt:

```text
IMU:
  - sensor_msgs/msg/Imu
  - unitree_hg/msg/IMUState

Odometrie / Motion State:
  - nav_msgs/msg/Odometry
  - unitree_go/msg/SportModeState
```

Für den realen Unitree-G1-Test ist in der aktuellen Konfiguration besonders wichtig:

```text
imu_mode   = unitree_hg
imu_topic  = /secondary_imu
odom_mode  = unitree_go
odom_topic = /odommodestate
```

---

## UDP-Format

Standard:

```text
UDP-IP:   127.0.0.1
UDP-Port: 5005
Paket:    3x float32 = [vx, vy, yaw_rate]
```

Python-seitig wird das Paket so erzeugt:

```python
packet = struct.pack("fff", vx, vy, yaw_rate)
sock.sendto(packet, ("127.0.0.1", 5005))
```

Wichtig:

```text
127.0.0.1 ist nur korrekt, wenn Node und g1_ctrl auf demselben Rechner laufen.
```

Wenn die Node auf einem anderen Rechner läuft als der Controller, muss `udp_ip` auf die IP-Adresse des Rechners gesetzt werden, auf dem `g1_ctrl` den UDP-Port öffnet.

---

## Standardisiertes Versuchsprofil

Für die Crouch-Walking-Auswertung wird ein kombiniertes Translations-/Rotationsprofil verwendet:

```text
vx        = ±0.30 m/s
vy        =  0.00 m/s
yaw_rate  =  0.50 rad/s
duration  = 10.0 s
rate      = 50 Hz
```

Dieses Profil kombiniert Vorwärts- oder Rückwärtsbewegung mit Rotation und belastet die Policy stärker als reines Geradeausgehen.

Die verwendeten Kommandowerte bleiben innerhalb der typischen `deploy.yaml`-Grenzen:

```text
lin_vel_x: [-0.5, 1.0]
lin_vel_y: [-0.5, 0.5]
ang_vel_z: [-1.0, 1.0]
```

---

## Voraussetzungen

ROS 2 Foxy unter Ubuntu 20.04 verwendet Python 3.8. Die Node daher mit dem System-Python starten, nicht mit Conda-Python.

```bash
conda deactivate
source /opt/ros/foxy/setup.bash
source ~/unitree_ros2/setup.sh
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

Falls `python3` nicht auf `/usr/bin/python3` zeigt, explizit starten mit:

```bash
/usr/bin/python3 g1_velocity_udp_logger_node.py ...
```

---

## Parameterübersicht

| Parameter | Bedeutung | Typischer Wert |
|---|---:|---|
| `trial_id` | Versuchsnummer | `1` |
| `vx` | Sollgeschwindigkeit x-Richtung in m/s | `0.30` oder `-0.30` |
| `vy` | Sollgeschwindigkeit y-Richtung in m/s | `0.00` |
| `yaw_rate` | Soll-Gierrate in rad/s | `0.50` |
| `duration` | aktive Versuchsdauer in s | `10.0` |
| `publish_rate` | Publikationsrate in Hz | `50.0` |
| `cmd_topic` | ROS-Topic für Twist-Kommando | `/cmd_vel` |
| `udp_ip` | Ziel-IP für UDP | `127.0.0.1` |
| `udp_port` | Ziel-Port für UDP | `5005` |
| `imu_mode` | IMU-Nachrichtentyp | `unitree_hg` oder `sensor_msgs` |
| `imu_topic` | IMU-Topic | `/secondary_imu` |
| `enable_odom` | Odometrie/Motion-State aktivieren | `true` oder `false` |
| `odom_mode` | Odometrie-/Motion-State-Typ | `unitree_go` oder `nav_msgs` |
| `odom_topic` | Odometrie-/Motion-State-Topic | `/odommodestate` |
| `csv_path` | Ausgabe der Raw-CSV | `g1_trial_001.csv` |
| `write_summary_csv` | Summary-CSV schreiben | `true` |
| `summary_csv_path` | optionaler Summary-Dateiname | automatisch aus `csv_path` |
| `send_zero_after_duration_s` | Dauer für Nullkommando nach Versuch | `1.0` |
| `passive_mode_triggered` | manuelle Passive-Mode-Markierung | `false` |
| `fall_detected_manual` | manuelle Fall-Markierung | `false` |
| `operator_note` | Freitextnotiz zum Versuch | `""` |

---

## Realer Unitree G1

Für den realen Unitree G1 wird in der aktuellen Konfiguration `/secondary_imu` als `unitree_hg/msg/IMUState` und `/odommodestate` als `unitree_go/msg/SportModeState` verwendet.

Vor dem Versuch prüfen:

```bash
ros2 topic list
ros2 topic type /secondary_imu
ros2 topic type /odommodestate
```

Erwartete Typen:

```text
/secondary_imu   → unitree_hg/msg/IMUState
/odommodestate   → unitree_go/msg/SportModeState
```

### Startbefehl Realversuch

```bash
conda deactivate
source /opt/ros/foxy/setup.bash
source ~/unitree_ros2/setup.sh

cd ~/unitree_rl_mjlab/scripts/metrics

python3 g1_velocity_udp_logger_node.py \
  --ros-args \
  -p trial_id:=1 \
  -p vx:=-0.30 \
  -p vy:=0.00 \
  -p yaw_rate:=0.50 \
  -p duration:=10.0 \
  -p publish_rate:=50.0 \
  -p udp_ip:=127.0.0.1 \
  -p udp_port:=5005 \
  -p imu_mode:=unitree_hg \
  -p imu_topic:=/secondary_imu \
  -p enable_odom:=true \
  -p odom_mode:=unitree_go \
  -p odom_topic:=/odommodestate \
  -p csv_path:=g1_trial_001.csv
```

Für weitere Trials nur `trial_id` und `csv_path` anpassen:

```text
trial_id:=2
csv_path:=g1_trial_002.csv
```

Optional kann die Richtung mit `vx:=0.30` statt `vx:=-0.30` geändert werden, sofern dies zum Versuchsplan passt.

---

## MuJoCo-Simulation

In der aktuellen MuJoCo-Konfiguration wird kein vollständiges Odometrie-Topic für diese Auswertung verwendet. Deshalb wird in der Simulation standardmäßig nur IMU-basiert geloggt:

```text
enable_odom = false
```

Typische Simulations-Topics:

```text
/lowcmd
/lowstate
/secondary_imu
/sportmodestate
/wirelesscontroller
```

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
conda deactivate
source /opt/ros/foxy/setup.bash
source ~/unitree_ros2/setup_local.sh

cd ~/unitree_rl_mjlab/scripts/metrics

python3 g1_velocity_udp_logger_node.py \
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

---

## Odometrie-Modi

### `unitree_go`

Verwendung für den realen Unitree G1 mit `/odommodestate`:

```bash
-p enable_odom:=true \
-p odom_mode:=unitree_go \
-p odom_topic:=/odommodestate
```

Dabei werden aus `unitree_go/msg/SportModeState` unter anderem folgende Werte geloggt:

```text
position[0]      → odom_x_m
position[1]      → odom_y_m
position[2]      → odom_z_m_base_height
velocity[0]      → odom_vx_mps
velocity[1]      → odom_vy_mps
yaw_speed        → odom_yaw_rate_radps
imu_state.rpy[2] → odom_yaw_rad
mode             → odom_unitree_mode
error_code       → odom_error_code
```

### `nav_msgs`

Verwendung für ROS-native Odometrie:

```bash
-p enable_odom:=true \
-p odom_mode:=nav_msgs \
-p odom_topic:=/odom
```

Dabei muss das Topic den Typ `nav_msgs/msg/Odometry` besitzen.

---

## CSV-Ausgaben

Pro Versuch entstehen standardmäßig zwei Dateien.

### Raw-CSV

Beispiele:

```text
g1_trial_001.csv
sim_trial_001.csv
```

Wichtige Spalten:

```text
trial_id
time_s
phase
vx_cmd_mps
vy_cmd_mps
yaw_rate_cmd_radps
udp_sent

imu_mode
imu_topic
imu_msg_count
imu_age_s
imu_roll_rad
imu_pitch_rad
imu_yaw_rad
imu_ang_vel_x_radps
imu_ang_vel_y_radps
imu_ang_vel_z_radps
imu_lin_acc_x_mps2
imu_lin_acc_y_mps2
imu_lin_acc_z_mps2
imu_lin_acc_norm_mps2
imu_temperature

odom_enabled
odom_mode
odom_topic
odom_msg_count
odom_age_s
odom_x_m
odom_y_m
odom_z_m_base_height
odom_yaw_rad
odom_vx_mps
odom_vy_mps
odom_yaw_rate_radps
odom_unitree_mode
odom_error_code

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
g1_trial_001_summary.csv
sim_trial_001_summary.csv
```

Wichtige Summary-Metriken:

```text
successful_trial
runtime_actual_s
sample_count_active

imu_yaw_rate_mean_radps
imu_yaw_rate_std_radps
imu_yaw_rate_rmse_radps
imu_roll_abs_max_rad
imu_pitch_abs_max_rad
imu_acc_norm_mean_mps2
imu_acc_norm_std_mps2

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

passive_mode_triggered_manual
fall_detected
fall_threshold_exceeded
operator_note
```

In der Simulation sind odometriebasierte Werte `NaN`, solange `enable_odom:=false` verwendet wird oder kein passendes Odometrie-/Motion-State-Topic vorhanden ist.

---

## Bewertungsmetriken

Die Node ist auf die Bewertung der Crouch-Walking-Policy ausgelegt.

Messbar in Simulation und Realversuch:

```text
- Laufdauer
- Erfolgsstatus
- UDP-Sendestatus
- Yaw-Rate-Tracking über IMU gyroscope.z
- Roll-/Pitch-Stabilität
- IMU-Beschleunigungsnorm
- Fallindikator über Roll-/Pitch-Grenzwerte
```

Zusätzlich messbar im Realversuch mit `/odommodestate`:

```text
- vx-Tracking
- vy-Tracking
- yaw_rate-Tracking über Motion State
- Base-Height-Mittelwert
- Base-Height-Standardabweichung
- Base-Height-Minimum und -Maximum
- Unitree mode
- Unitree error_code
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

## Erfolgslogik

Ein Versuch wird in der Summary-CSV als erfolgreich markiert, wenn:

```text
1. die aktive Versuchsdauer vollständig erreicht wurde,
2. kein Passive-Mode manuell markiert wurde,
3. kein manueller Fall markiert wurde,
4. keine Roll-/Pitch-Fallgrenze überschritten wurde.
```

Die relevanten Felder sind:

```text
successful_trial
passive_mode_triggered_manual
fall_detected
fall_threshold_exceeded
```

---

## Manuelle Annotationen

Für Ereignisse, die nicht zuverlässig automatisch erkennbar sind, können manuelle Parameter gesetzt werden:

```text
passive_mode_triggered
fall_detected_manual
operator_note
```

Beispiel:

```bash
-p passive_mode_triggered:=true \
-p operator_note:="passive mode without recorded fall"
```

Diese Angaben werden in der Summary-CSV gespeichert und sind besonders wichtig für die wissenschaftliche Auswertung der Realversuche.

---

## Sicherheit

Nach der aktiven Versuchsdauer sendet die Node standardmäßig 1 s lang Nullkommandos:

```text
send_zero_after_duration_s = 1.0
```

Das betrifft sowohl `/cmd_vel` als auch UDP.

Zusätzlich sollte der Controller-seitige UDP-Override ein Timeout besitzen. Ohne frisches UDP-Paket soll der Controller auf das originale Joystick-/Wirelesscontroller-Verhalten zurückfallen.

---

## Troubleshooting

### `rclpy._rclpy` fehlt

Ursache ist fast immer eine falsche Python-Version, häufig Conda-Python statt ROS-2-Foxy-System-Python.

```bash
conda deactivate
source /opt/ros/foxy/setup.bash
/usr/bin/python3 g1_velocity_udp_logger_node.py ...
```

---

### `unitree_hg` oder `unitree_go` kann nicht importiert werden

Dann ist die Unitree-ROS-2-Umgebung nicht korrekt geladen.

Realroboter:

```bash
source /opt/ros/foxy/setup.bash
source ~/unitree_ros2/setup.sh
```

Lokale Simulation:

```bash
source /opt/ros/foxy/setup.bash
source ~/unitree_ros2/setup_local.sh
```

Danach erneut prüfen:

```bash
ros2 interface show unitree_hg/msg/IMUState
ros2 interface show unitree_go/msg/SportModeState
```

---

### Keine IMU-Daten

Topic-Typ prüfen:

```bash
ros2 topic type /secondary_imu
```

Dann passenden Modus wählen:

```bash
-p imu_mode:=unitree_hg
```

oder:

```bash
-p imu_mode:=sensor_msgs
```

---

### Keine Odometrie im Realversuch

Topic prüfen:

```bash
ros2 topic type /odommodestate
```

Für den aktuellen Unitree-G1-Workflow verwenden:

```bash
-p enable_odom:=true \
-p odom_mode:=unitree_go \
-p odom_topic:=/odommodestate
```

---

### Keine Odometrie in MuJoCo

Für die aktuelle Simulationsauswertung ist das normal. Deshalb:

```bash
-p enable_odom:=false
```

Die odometriebasierten CSV-Felder bleiben dann `NaN`.

---

### UDP wirkt nicht

Prüfen, ob der Controller den UDP-Override aktiviert hat:

```text
[velocity_commands] UDP override listening on port 5005.
```

Dann prüfen:

```text
udp_ip   = 127.0.0.1
udp_port = 5005
```

`127.0.0.1` nur verwenden, wenn Node und `g1_ctrl` auf demselben Rechner laufen.

---

## Hinweis für die Masterarbeit

Die MuJoCo-Sim2Sim-Stufe liefert in dieser Konfiguration quantitative IMU-Metriken, insbesondere Yaw-Rate-Tracking über `imu_ang_vel_z_radps` sowie Roll-/Pitch-Stabilität. Translatorische Geschwindigkeit und Base Height werden erst dann quantitativ bewertet, wenn ein passendes Odometrie- oder Motion-State-Topic verfügbar ist.

Für den realen Unitree-G1-Versuch liefert `/odommodestate` zusätzliche quantitative Werte für Velocity-Tracking und Base-Height-Stabilität. Dadurch eignet sich der Realversuch für die vollständige Sim-to-Real-Auswertung, während MuJoCo primär als funktionaler Deployment- und Plausibilitätscheck der Policy-Kette dient.
