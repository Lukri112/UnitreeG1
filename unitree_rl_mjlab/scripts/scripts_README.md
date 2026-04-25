# Scripts erklärt, ganz einfach

Dieser Ordner enthält die Python-Skripte, mit denen du die Policy trainierst, testest und Hilfsaufgaben erledigst.

## Wichtige Dateien für Crouch Walking

### `train.py`
Das ist das Hauptskript zum Trainieren.

Einfach gesagt macht es diese Schritte:
1. Es lädt eine Task, zum Beispiel `Unitree-G1-Flat-Crouch-Deploy`.
2. Es lädt die passende Umgebungsbeschreibung und die PPO-Einstellungen.
3. Es startet viele MuJoCo-Umgebungen parallel.
4. Es verbindet die Umgebung mit **RSL-RL**.
5. Es trainiert die Policy mit **PPO**.
6. Es speichert Checkpoints und exportiert auch `policy.onnx`.

Wenn du die Crouch-Walking-Policy neu trainieren willst, ist das meistens das richtige Skript.

### `train_resume.py`
Dieses Skript ist für Fortsetzen oder Fine-Tuning da.

Es kann:
- ein altes Training fortsetzen,
- einen alten Checkpoint laden,
- weitertrainieren,
- optional denselben W&B-Run sauber weiterverwenden.

Einfach gesagt:
`train.py` ist für normalen Start,
`train_resume.py` ist für "mach von hier weiter".

### `play.py`
Dieses Skript spielt eine trainierte Policy in MuJoCo ab.

Damit kannst du:
- prüfen, ob die Policy läuft,
- Videos aufnehmen,
- die Bewegung anschauen,
- einen bestimmten Checkpoint testen.

Es trainiert **nicht**. Es ist nur zum Testen und Anschauen.

## Weitere Dateien

### `list_envs.py`
Zeigt dir alle verfügbaren Tasks an.
Praktisch, wenn du kurz nachsehen willst, wie der Task-Name genau heißt.

### `csv_to_npz.py`
Wird für Mimic / Motion-Tracking benutzt.
Für normales Velocity- oder Crouch-Walking ist es nicht der Hauptweg.

### `visualize_terrain.py`
Zeigt Terrains an.
Hilfreich zum Verstehen oder Debuggen von Terrain-Setups.
Für Flat-Crouch-Training meist nicht zentral.

## Der einfache Trainingsfluss

Für Crouch Walking ist der übliche Ablauf:

1. Task wählen: `Unitree-G1-Flat-Crouch-Deploy`
2. `train.py` starten
3. PPO lernt in MuJoCo
4. Checkpoints werden gespeichert
5. `policy.onnx` wird exportiert
6. Diese ONNX-Policy kann später im Deploy-Controller genutzt werden

## Wichtigster Punkt

Die eigentliche Lernmethode ist hier:
- **PPO**
- über **RSL-RL**

Die Skripte in diesem Ordner kümmern sich hauptsächlich darum,
- die richtige Task zu laden,
- Training oder Test zu starten,
- Dateien zu speichern.
