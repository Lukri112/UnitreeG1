**Problemstellung**
Es sollte geprüft werden, ob zwei ONNX-Policies zu der realen Deploy-Konfiguration eines **Unitree G1 Edu mit 29DOF** passen und ob die neue eigene Policy mit dem offiziellen G1-Deploy-Setup kompatibel ist.

**Vorgehensweise**
Es wurden:

* die hochgeladene `deploy.yaml` analysiert,
* beide ONNX-Policies hinsichtlich **Ein- und Ausgangsdimensionen** verglichen,
* die **Observation- und Action-Struktur** abgeglichen,
* sowie der offizielle **Deploy-Code aus dem Unitree-GitHub-Repo** geprüft, um die tatsächliche Zuordnung von `obs[98]` und `actions[29]` nachzuvollziehen.

**Ergebnis / Lösung**
Es wurde festgestellt, dass beide Policies **formal kompatibel** sind:

* **98 Beobachtungen** werden als Eingabe erwartet,
* **29 Aktionen** werden ausgegeben.

Außerdem wurde bestätigt, dass die `deploy.yaml` dazu passt:

* 29 Gelenke sind definiert,
* 29 Skalierungswerte sind vorhanden,
* 29 Offsets sind enthalten,
* und die Observationen ergeben in Summe genau **98 Eingangsgrößen**.

Zusätzlich wurde im offiziellen Unitree-Deploy-Code bestätigt, dass genau dieses Schema verwendet wird. Dadurch konnte die Repo-Policy als passende Referenz eingeordnet werden.

Für die neue eigene Policy wurde daraus abgeleitet, dass sie **sehr wahrscheinlich als Drop-in-Ersatz verwendet werden kann**, sofern sie mit derselben Beobachtungs- und Aktionsreihenfolge trainiert und exportiert wurde wie die Referenz-Policy.

**Restunsicherheit**
Sicher bestätigt wurde die **strukturelle Kompatibilität**. Nicht vollständig bewiesen werden konnte allein, ob die neue Policy auch **semantisch exakt dieselbe Reihenfolge** von Gelenken, Observationen und Actions verwendet wie das originale Training- und Export-Setup.

**Praktisches Fazit**
Das Problem konnte **weitgehend gelöst** werden.
Es wurde gezeigt, dass die neue Policy **strukturell und deploy-seitig** zum realen G1-29DOF-Setup passt. Vor dem Einsatz auf echter Hardware sollte lediglich noch ein kurzer **PT-/ONNX- oder Runtime-Abgleich** durchgeführt werden, damit auch die letzte semantische Sicherheit gegeben ist.


## Problemstellung
Es sollte geklärt werden, worin sich zwei ONNX-Policies unterscheiden und wie beide auf einem Roboter deployt werden können. Dabei standen insbesondere die Anzahl der Inputs und Outputs, die unterschiedlichen Beobachtungsräume aus MJLab und IsaacLab sowie die dafür notwendige RobotState- und Adapter-Struktur im Mittelpunkt.

## Vorgehensweise
Zunächst wurden beide Policies technisch verglichen. Dabei wurde festgestellt, dass beide Modelle jeweils **1 Input** und **1 Output** besitzen. Der Input heißt in beiden Fällen `obs`, der Output `actions`. Die Unterschiede wurden vor allem in der Größe des Input-Vektors erkannt:  
- die **MJLab-Policy** verwendet **98 Input-Features**  
- die **IsaacLab-Policy** verwendet **480 Input-Features**  

Der Output ist bei beiden Policies gleich aufgebaut:  
- **29 Output-Werte** (`actions`)  

Anschließend wurde beschrieben, dass für den Robotereinsatz ein gemeinsamer **RobotState** benötigt wird, der die relevanten Sensordaten und Zustände des Roboters bündelt, zum Beispiel Gelenkpositionen, Gelenkgeschwindigkeiten, IMU-Daten, Basisorientierung, Kommandos und gegebenenfalls Kontaktinformationen. Aus diesem gemeinsamen RobotState sollten dann über zwei getrennte **Observations-Adapter** die jeweils passenden Eingaben für die beiden Policies erzeugt werden.

Ebenso wurde berücksichtigt, dass nicht nur die Inputs, sondern auch die Interpretation der Outputs policy-spezifisch behandelt werden muss. Daher wurde zusätzlich die Verwendung separater **Action-Adapter** empfohlen.

## Lösung
Als Lösung wurde empfohlen, beide Policies nicht in ein gemeinsames Beobachtungsformat zu überführen, sondern sie als zwei getrennte Controller-Profile mit gemeinsamer Runtime auf dem Roboter zu deployen.

Dafür sollte folgende Struktur verwendet werden:
- ein gemeinsamer **RobotState** als zentrale Zustandsrepräsentation des Roboters
- ein **ObsAdapter** für die MJLab-Policy mit **98 Inputs**
- ein **ObsAdapter** für die IsaacLab-Policy mit **480 Inputs**
- je ein passender **ActionAdapter** für die Ausgabe von **29 Actions**
- ein gemeinsames **Safety-Layer** zur Absicherung auf dem Roboter
- eine gemeinsame Inferenzschicht, zum Beispiel über **ONNX Runtime**

Dadurch kann jede Policy mit ihrer ursprünglichen Beobachtungsstruktur, ihrer eigenen Input-Aufbereitung und ihrer passenden Output-Interpretation sicher und korrekt auf dem Roboter ausgeführt werden.


# Zusammenfassung

## Problemstellung
Es wurde ein MJLab-Checkpoint für den Unitree G1 trainiert, bei dem ein **Crouch-Walk** erlernt wurde.  
Beim Testen des exportierten `policy.onnx` in MuJoCo sim2sim fiel der Roboter jedoch nur um und zeigte Zuckbewegungen, obwohl erwartet wurde, dass Training und Deployment übereinstimmen.  
Es sollte geklärt werden, ob die Ursache in einer falschen Joint-Reihenfolge, einem fehlerhaften ONNX-Export, einem Controller-Mismatch oder in einer nicht passenden Deploy-Konfiguration liegt. 

## Wichtige technische Eckdaten
- Es wurde eine **Policy mit 29 Actions** verwendet. :contentReference[oaicite:1]{index=1}
- Die Actor-Observation bestand aus **98 Werten**. Zusammensetzung:
  - `base_ang_vel`: 3
  - `projected_gravity`: 3
  - `velocity_commands`: 3
  - `gait_phase`: 2
  - `joint_pos_rel`: 29
  - `joint_vel_rel`: 29
  - `last_action`: 29  
  Summe: **98 Inputs**. 
- Es wurde mit `step_dt = 0.02` gearbeitet, also mit **50 Hz**. :contentReference[oaicite:3]{index=3}
- Es wurde eine `JointPositionAction` mit **29-D Output**, `scale` und `offset` verwendet. :contentReference[oaicite:4]{index=4}

## Vorgehensweise
Zuerst wurde geprüft, ob ein allgemeiner Fehler in der sim2sim-Bridge oder in der Joint-Reihenfolge vorliegt.  
Dazu wurden Controller-Dateien, `deploy.yaml`, die MuJoCo-Actuator-Reihenfolge, die Sensor-Reihenfolge und das Training-Environment untersucht. 

Anschließend wurde in MuJoCo die Szeneninformation ausgegeben.  
Dabei wurde festgestellt, dass:
- **29 Actuators** vorhanden sind,
- die Reihenfolge der Actuators und Sensoren konsistent ist,
- keine zusätzliche Remapping-Logik im Controller verwendet wird,
- die Sensorblöcke für Position, Geschwindigkeit und Torque sauber in derselben Reihenfolge angeordnet sind. 

Danach wurde das Training-Environment analysiert.  
Dabei wurde bestätigt, dass:
- die Observation-Struktur des Trainings mit dem Deploy-Format kompatibel ist,
- `gait_phase`, `joint_pos_rel`, `joint_vel_rel` und `last_action` im Training vorhanden sind,
- die Policy also grundsätzlich auf dieselbe Input-Struktur ausgelegt wurde. 

Zum Schluss wurde die Datei `g1_constants_crouch.py` geprüft, mit der die Crouch-Position im Training definiert wurde. Dabei wurde erkannt, dass die trainierte Nominalpose deutlich tiefer war als die Pose im aktuellen `deploy.yaml`. 

## Erkenntnisse
Es konnte ausgeschlossen werden, dass die Hauptursache in der Joint-Reihenfolge oder in der allgemeinen MuJoCo-Bridge liegt, weil:
- dieselbe Simulationsumgebung mit einer anderen Policy stabil funktionierte,
- die Joint- und Sensor-Reihenfolge konsistent war,
- Controller und Sensordaten linear und korrekt verarbeitet wurden. 

Als Hauptursache wurde ein **Mismatch zwischen trainierter Crouch-Nominalpose und Deploy-Konfiguration** identifiziert.

### Trainierte Crouch-Pose
Im Training wurde mit einer tiefen Haltung gearbeitet:
- `hip_pitch = -0.77`
- `knee = 1.32`
- `ankle_pitch = -0.68`
- `left_shoulder_pitch = 0.2`
- `left_shoulder_roll = 0.2`
- `right_shoulder_pitch = 0.2`
- `right_shoulder_roll = -0.2`
- `elbow = 0.6`
- Base-Höhe `z = 0.65` :contentReference[oaicite:10]{index=10}

### Deploy-Pose vorher
Im `deploy.yaml` war dagegen eine deutlich aufrechtere Pose eingetragen:
- `hip_pitch = -0.1`
- `knee = 0.3`
- `ankle_pitch = -0.2`
- Arme in anderer Ruhehaltung. :contentReference[oaicite:11]{index=11}

Dadurch wurde die Policy direkt mit einem Zustand gestartet, der nicht der trainierten Verteilung entsprach.  
Insbesondere wurde dadurch `joint_pos_rel` bereits beim Start falsch relativ zur erwarteten Crouch-Pose berechnet. 

## Lösung
Als Lösung wurde empfohlen, im `deploy.yaml` die Einträge
- `default_joint_pos`
- `actions.JointPositionAction.offset`

an die trainierte Crouch-Pose anzupassen. 

### Verwendete 29er-Reihenfolge
Die Reihenfolge wurde als korrekt bestätigt:
1. linkes Bein (6)
2. rechtes Bein (6)
3. Waist (3)
4. linker Arm (7)
5. rechter Arm (7) 

### Eingetragene Crouch-Werte
Folgende Werte wurden zum Ersetzen empfohlen:
- `default_joint_pos` = Crouch-Pose
- `offset` = dieselbe Crouch-Pose  
mit:
- Beine: `[-0.77, 0, 0, 1.32, -0.68, 0]`
- Waist: `[0, 0, 0]`
- linker Arm: `[0.2, 0.2, 0, 0.6, 0, 0, 0]`
- rechter Arm: `[0.2, -0.2, 0, 0.6, 0, 0, 0]` 

## Endergebnis
Das Problem wurde nicht durch eine falsche Joint-Reihenfolge verursacht, sondern durch einen **Mismatch zwischen trainierter Crouch-Initialpose und der im Deployment verwendeten Standardpose**.  
Die Lösung bestand darin, die Deploy-Konfiguration auf die im Training verwendete Crouch-Nominalpose umzustellen, damit die 98-dimensionalen Robot States und die 29-dimensionalen Action-Outputs wieder zur trainierten Policy passen. 
