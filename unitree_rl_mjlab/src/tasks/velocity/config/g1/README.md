# G1 Velocity Tasks erklärt, ganz einfach

In diesem Ordner steht, **welche G1-Tasks es gibt** und **wie sie gebaut werden**.

## Wichtige Dateien

### `__init__.py`
Hier werden die G1-Tasks registriert.

Aktuell wichtige Tasks sind:
- `Unitree-G1-Flat`
- `Unitree-G1-Rough`
- `Unitree-G1-Flat-Crouch-Deploy`
- `Unitree-G1-Flat-Deploy98`

Einfach gesagt:
Hier wird dem System gesagt,
"diese Tasks existieren und diese Konfigurationen gehören dazu".

### `rl_cfg.py`
Hier stehen die Lern-Einstellungen.

Wichtig:
- Es wird **PPO** benutzt
- nicht SAC
- über **RSL-RL**

Hier stehen zum Beispiel:
- Netzgrößen
- Lernrate
- PPO-Clipping
- Anzahl Updates
- Anzahl Schritte pro Umgebung

Einfach gesagt:
Diese Datei sagt, **wie gelernt wird**.

### `env_cfg.py` / `env_cfgs.py`
Diese Datei beschreibt die normale G1-Laufumgebung.

Darin wird festgelegt:
- was der Roboter sieht,
- welche Aktionen die Policy ausgibt,
- welche Rewards es gibt,
- welche Commands gegeben werden,
- wann ein Episode endet.

Einfach gesagt:
Diese Datei sagt, **was die Aufgabe ist**.

### `env_cfgs_deploy98.py`
Diese Datei baut eine spezielle Flat-Variante, deren **Actor-Observation genau zum Deploy-Format passt**.

Die wichtige Idee ist:
- die Beobachtungsreihenfolge muss genau stimmen,
- die Eingabedimension muss genau stimmen,
- damit die ONNX-Policy später sauber im Controller läuft.

Einfach gesagt:
Diese Datei macht die Policy **deploy-kompatibel**.

### `env_cfgs_crouch.py`
Das ist die wichtige Datei für **Crouch Walking**.

Hier werden wichtige Änderungen gemacht:
- crouch-spezifischer Roboter wird geladen,
- tiefe Startpose wird verwendet,
- Rewards werden auf Crouch Walking angepasst,
- Actor-Observation bleibt deploy-kompatibel.

Einfach gesagt:
Diese Datei macht aus normalem Walking ein **Crouch-Walking-Training**.

## Wie das Crouch-Training hier aufgebaut ist

Für `Unitree-G1-Flat-Crouch-Deploy` passiert logisch:

1. Nimm die normale Flat-G1-Umgebung
2. Ersetze die Standardpose durch eine crouch-Pose
3. Passe Rewards für tiefes Gehen an
4. Halte die Observation so, dass Deploy später passt
5. Trainiere dann mit PPO

## Wichtig zu verstehen

Es gibt hier zwei große Teile:

### Teil 1: Task-Definition
Das ist dieser Ordner.
Er sagt:
- was der Roboter beobachtet,
- was er tun darf,
- wofür er belohnt wird.

### Teil 2: Lernen
Das macht RSL-RL mit PPO.

Also:
- **dieser Ordner definiert die Aufgabe**
- **RSL-RL löst die Aufgabe**

## Kurzfassung

Wenn du verstehen willst,
**warum** der Roboter crouch walking lernt,
dann ist dieser Ordner einer der wichtigsten im ganzen Repo.
