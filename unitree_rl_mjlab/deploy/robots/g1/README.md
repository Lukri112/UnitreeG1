# G1 Deploy-Controller erklärt, ganz einfach

Dieser Ordner ist für den **Controller auf der Roboterseite**.

Hier geht es nicht mehr um Training, sondern darum,
die fertige Policy wirklich laufen zu lassen.

## Was dieser Ordner macht

Einfach gesagt:
- lädt eine exportierte ONNX-Policy,
- liest den Roboterzustand,
- baut die richtigen Beobachtungen,
- führt die Policy aus,
- schickt Gelenk-Sollwerte an den Roboter.

## Wichtige Dateien

### `main.cpp`
Das ist der Einstiegspunkt des G1-Controllers.

Es:
- verbindet sich mit dem Roboter,
- prüft den Robotertyp,
- startet die FSM,
- hält dann den Controller am Laufen.

Wichtige praktische Änderung hier:
- `mode_machine` wird explizit auf `6` gesetzt,
- weil dein Roboter genau diesen Wert meldet.

Einfach gesagt:
Ohne diese Anpassung hätte der Typ-Check scheitern können.

### `config/config.yaml`
Hier steht, welche Zustände es im Controller gibt.

Wichtige Zustände:
- `VelocityWalk`
- `VelocityCrouch`
- `Mimic_Dance1_subject2`

Ganz wichtig:
- `VelocityWalk` nutzt `config/policy/velocity/v0`
- `VelocityCrouch` nutzt `config/policy/velocity/v1`

Einfach gesagt:
Hier wird festgelegt, welche Policy in welchem Modus benutzt wird.

### `src/State_RLBase.cpp`
Das ist die wichtigste Datei für normales RL-Deploy.

Sie:
- lädt `deploy.yaml`
- lädt `policy.onnx`
- erstellt die RL-Umgebung auf Controller-Seite
- berechnet Aktionen
- schreibt die Aktionen als Gelenk-Sollwerte in `lowcmd`

Einfach gesagt:
Diese Datei ist die Brücke zwischen ONNX-Policy und echtem Roboter.

## Wichtige Änderungen für zuverlässiges Deploy

### 1. Observation-Name für Deploy passt
Im Training wurde die Observation so aufgebaut, dass Deploy sauber passt.
Im Controller wird das passende `deploy.yaml` geladen.

Das ist wichtig, weil:
- Reihenfolge der Beobachtungen stimmen muss
- Namen und Bedeutung zusammenpassen müssen
- sonst bekommt die Policy die falschen Eingaben

### 2. Getrennte Policies für Walk und Crouch
Im Controller gibt es zwei getrennte Pfade:
- `v0` für normales Walking
- `v1` für Crouch Walking

Das ist sinnvoll, weil beide andere Default-Posen und anderes Verhalten haben.

### 3. Keyboard-Beispiel für Commands
In `State_RLBase.cpp` gibt es ein registriertes Beispiel für Tastatur-Kommandos.
Das ist hilfreich für Tests und zum Verstehen der Command-Eingabe.

### 4. Sicherheitscheck bei schlechter Orientierung
Der Controller prüft auch auf schlechte Orientierung.
Wenn der Roboter zu stark kippt, kann auf einen sicheren Zustand gewechselt werden.

Das hilft, kaputte Situationen zu vermeiden.

## Welche Dateien die Policy wirklich braucht

Für einen RL-Zustand braucht der Controller vor allem:
- `params/deploy.yaml`
- `exported/policy.onnx`

Beides liegt unter dem jeweiligen Policy-Ordner, z. B.:
- `config/policy/velocity/v0/...`
- `config/policy/velocity/v1/...`

## Kurz gesagt

Wenn `scripts/train.py` die Policy lernt,
dann sorgt dieser Ordner dafür,
dass die fertige Policy auf dem echten G1 auch wirklich läuft.
