# Unitree G1 29DOF – klare Referenz für Joint-Reihenfolge, Training und Deployment

## 1) Kanonische 29-DOF-Joint-Reihenfolge

Diese Reihenfolge solltest du für den **Unitree G1 EDU 29DOF** als **Master-Reihenfolge** behandeln und in:
- Training
- Observation-Aufbau
- Action-Ausgabe
- ONNX-Export-Checks
- `deploy.yaml`
- `config.yaml`
- Runtime-Mapping

immer konsistent halten.

```text
1.  left_hip_pitch_joint
2.  left_hip_roll_joint
3.  left_hip_yaw_joint
4.  left_knee_joint
5.  left_ankle_pitch_joint
6.  left_ankle_roll_joint
7.  right_hip_pitch_joint
8.  right_hip_roll_joint
9.  right_hip_yaw_joint
10. right_knee_joint
11. right_ankle_pitch_joint
12. right_ankle_roll_joint
13. waist_yaw_joint
14. waist_roll_joint
15. waist_pitch_joint
16. left_shoulder_pitch_joint
17. left_shoulder_roll_joint
18. left_shoulder_yaw_joint
19. left_elbow_joint
20. left_wrist_roll_joint
21. left_wrist_pitch_joint
22. left_wrist_yaw_joint
23. right_shoulder_pitch_joint
24. right_shoulder_roll_joint
25. right_shoulder_yaw_joint
26. right_elbow_joint
27. right_wrist_roll_joint
28. right_wrist_pitch_joint
29. right_wrist_yaw_joint
```

---

## 2) Wo die Joint-Reihenfolge im Repo praktisch relevant ist

### A. Explizite 29er Referenzliste
**Datei**
```text
scripts/csv_to_npz.py
```

**Bedeutung**
- Enthält die klarste und vollständig ausgeschriebene **29er Joint-Liste**
- Sehr gute Referenz für alle eigenen Checks
- Besonders wichtig für Motion-/Dataset-Konvertierung und zum Gegenprüfen deiner Trainings-/Deploy-Reihenfolge

---

### B. Roboterdefinition für Training
**Datei**
```text
src/assets/robots/unitree_g1/g1_constants.py
```

**Bedeutung**
- Verweist auf das MJCF/XML des Roboters
- Definiert die Aktuatorgruppen per Joint-Regex
- Definiert Initial-/Nominalposen wie `HOME_KEYFRAME`
- Baut daraus die G1-Roboterkonfiguration für das Training

**Wichtig**
- Hier steht nicht die 29er Reihenfolge als einfache Liste wie in `csv_to_npz.py`
- Aber diese Datei ist die zentrale Quelle dafür, **welche G1-Joints/Aktuatoren** im Training überhaupt benutzt werden

---

### C. G1-Task-Konfiguration für Velocity-Training
**Dateien**
```text
src/tasks/velocity/velocity_env_cfg.py
src/tasks/velocity/config/g1/env_cfgs.py
src/tasks/velocity/config/g1/__init__.py
```

**Bedeutung**
- `velocity_env_cfg.py` definiert die allgemeinen **Observations** und **Actions**
- `config/g1/env_cfgs.py` hängt die G1-Robot-Config ein und setzt G1-spezifische Parameter
- `config/g1/__init__.py` registriert die Tasks wie:
  - `Unitree-G1-Flat`
  - `Unitree-G1-Rough`

---

### D. Deployment-Konfiguration auf dem realen Roboter
**Dateien**
```text
deploy/robots/g1/config/policy/velocity/v0/params/deploy.yaml
deploy/robots/g1/config/config.yaml
```

**Bedeutung**
- `deploy.yaml` definiert:
  - `joint_ids_map`
  - `default_joint_pos`
  - Action-`scale`
  - Action-`offset`
  - Observation-Blöcke
- `config.yaml` definiert u. a. den `FixStand`-Zustand mit 29 Gelenkwerten

**Wichtig**
- Diese 29er Vektoren müssen dieselbe Reihenfolge verwenden wie Training und Runtime
- Schon ein einziger vertauschter Joint kann die Policy unbrauchbar machen

---

### E. Runtime-Mapping von Robot-State zu Observation und Action zurück auf Motoren
**Dateien**
```text
deploy/include/unitree_articulation.h
deploy/robots/g1/src/State_RLBase.cpp
```

**Bedeutung**
- `unitree_articulation.h` liest `joint_pos` und `joint_vel` über `joint_ids_map`
- `State_RLBase.cpp` schreibt `action[i]` wieder über `joint_ids_map[i]` auf die Motor-Kommandos

**Folge**
- Die Runtime geht strikt davon aus, dass:
  - Observation-Joint-Reihenfolge stimmt
  - Action-Reihenfolge stimmt
  - `joint_ids_map` dazu passt

---

## 3) Wo Observations im Training definiert werden

**Datei**
```text
src/tasks/velocity/velocity_env_cfg.py
```

### Actor-Observation-Terme
```text
base_ang_vel
projected_gravity
command
phase
joint_pos
joint_vel
actions
height_scan
```

### Inhaltlich bedeutet das
- `base_ang_vel` → IMU-Winkelgeschwindigkeit
- `projected_gravity` → projizierte Gravitation im Körperrahmen
- `command` → Geschwindigkeitskommando
- `phase` → Gangphase
- `joint_pos` → relative Gelenkpositionen
- `joint_vel` → relative Gelenkgeschwindigkeiten
- `actions` → letzte Aktion
- `height_scan` → Terrain-Scan

### Für G1 Flat
**Datei**
```text
src/tasks/velocity/config/g1/env_cfgs.py
```

Dort wird für Flat Terrain `height_scan` entfernt.  
Damit bleiben für den flachen G1-Velocity-Task effektiv die propriozeptiven Beobachtungen übrig.

---

## 4) Wo Actions im Training definiert werden

**Datei**
```text
src/tasks/velocity/velocity_env_cfg.py
```

Dort wird die Action als Joint-Positions-Action angelegt.

**G1-spezifische Anpassung**
```text
src/tasks/velocity/config/g1/env_cfgs.py
```

Dort wird die G1-Action-Skalierung gesetzt.

### Wichtig
Die Trainings-Action ist also aufgeteilt in:
- allgemeine Action-Definition im Basis-Velocity-Task
- G1-spezifische Skalierung im G1-Task

---

## 5) Wo Observations im Deployment definiert werden

**Datei**
```text
deploy/robots/g1/config/policy/velocity/v0/params/deploy.yaml
```

### Dort definierte Observation-Blöcke
```text
base_ang_vel
projected_gravity
velocity_commands
gait_phase
joint_pos_rel
joint_vel_rel
last_action
```

### Wichtig
Die Namen sind leicht anders als im Training:
- `command` ↔ `velocity_commands`
- `phase` ↔ `gait_phase`
- `joint_pos` ↔ `joint_pos_rel`
- `joint_vel` ↔ `joint_vel_rel`
- `actions` ↔ `last_action`

Inhaltlich sind das aber dieselben Typen von Blöcken.

---

## 6) Wo Actions im Deployment definiert werden

**Datei**
```text
deploy/robots/g1/config/policy/velocity/v0/params/deploy.yaml
```

### Action-Block
```text
actions:
  JointPositionAction:
```

### Relevante Parameter
```text
joint_names
scale
offset
joint_ids
```

Zusätzlich wichtig:
```text
joint_ids_map
default_joint_pos
```

---

## 7) Welche Dateien du für neues Training unbedingt zusammen als Set behandeln solltest

### Minimales Pflicht-Set für G1 29DOF

```text
scripts/csv_to_npz.py
src/assets/robots/unitree_g1/g1_constants.py
src/assets/robots/unitree_g1/xmls/g1.xml
src/tasks/velocity/velocity_env_cfg.py
src/tasks/velocity/config/g1/env_cfgs.py
src/tasks/velocity/config/g1/__init__.py
deploy/robots/g1/config/policy/velocity/v0/params/deploy.yaml
deploy/robots/g1/config/config.yaml
deploy/include/unitree_articulation.h
deploy/robots/g1/src/State_RLBase.cpp
```

### Zusätzlich relevant bei Motion-Imitation
```text
src/tasks/tracking/config/g1/env_cfgs.py
scripts/csv_to_npz.py
```

---

## 8) Harte Regeln, damit du keinen Joint-Mismatch trainierst

### Regel 1
Lege **eine zentrale Master-Liste der 29 Joints** an und verwende exakt diese Reihenfolge überall.

### Regel 2
Wenn du neue Observations hinzufügst, zum Beispiel RGBD:
- **erweitere nur den Observation-Vektor**
- **ändere nicht die 29er Joint-Reihenfolge**
- **ändere nicht die Reihenfolge der 29 Actions**, solange dieselben Motoren gesteuert werden sollen

### Regel 3
`default_joint_pos`, Action-`offset`, `FixStand.qs`, `joint_pos_rel`, `joint_vel_rel`, `last_action` und alle 29er Skalen müssen semantisch zur selben Reihenfolge passen.

### Regel 4
Vor jedem Export:
- prüfe Tensorform
- prüfe Observation-Reihenfolge
- prüfe Action-Reihenfolge
- prüfe Gelenknamen gegen die 29er Master-Liste

### Regel 5
Vor Realrobotik:
- erst MuJoCo / sim2sim testen
- dann Deployment
- nie direkt auf Hardware mit ungeprüftem Joint-Mapping

---

## 9) Empfohlene eigene Checkliste für jedes neue Policy-Training

### Vor dem Training
- 29er Master-Joint-Liste festlegen
- prüfen, dass Roboter-XML und Training-Entity dazu passen
- prüfen, dass Initialpose und Reward-Definition zur Aufgabe passen

### Während der Observation-Definition
- Reihenfolge aller propriozeptiven Joint-Features fest fixieren
- RGBD oder Vision nur zusätzlich einfügen, nicht die bestehenden Joint-Blöcke umsortieren

### Während der Action-Definition
- sicherstellen, dass `action[i]` immer dasselbe Gelenk meint wie im Deployment
- Scale und Offset dokumentieren

### Vor ONNX-Export
- Dummy-Input durchlaufen lassen
- prüfen, ob Output-Dimension 29 bleibt
- prüfen, ob Observation-Dimension exakt zur Runtime passt

### Vor Deployment
- `deploy.yaml` prüfen
- `config.yaml` prüfen
- `joint_ids_map` prüfen
- `default_joint_pos` und `offset` prüfen
- FixStand-Startpose prüfen

---

## 10) Praktische Empfehlung für dein eigenes RGBD-Manipulationsprojekt

Wenn du eine eigene Policy mit **RGBD-Daten des Unitree G1 EDU 29DOF** trainieren willst, dann ist die sichere Struktur:

### Beibehalten
- dieselben 29 Actions
- dieselbe Joint-Reihenfolge
- dieselbe Runtime-Zuordnung auf Motoren

### Erweitern
- Observation-Vektor um Vision-Features
- z. B. RGB-Encoder, Depth-Encoder oder fusionierte Features
- eigener Task für Manipulation statt reines Velocity-Walking

### Nicht verändern
- die semantische Zuordnung von `action[0..28]`
- die Bedeutung der Gelenkblöcke in `joint_pos_rel` und `joint_vel_rel`

---

## 11) Ein Satz als Merksatz

**Die Policy darf größer werden, aber die Bedeutung von Joint 0 bis Joint 28 darf sich zwischen Training, Export und Deployment niemals ändern.**
