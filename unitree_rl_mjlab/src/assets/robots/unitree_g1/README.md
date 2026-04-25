# G1 Robot-Configs erklärt, ganz einfach

In diesem Ordner steht, **wie der G1 als Robotermodell beschrieben wird**.

## Wichtige Dateien

### `g1_constants.py`
Das ist die normale G1-Basisbeschreibung.

Sie enthält zum Beispiel:
- MJCF / XML Referenz
- Aktuatoren
- Startpose
- Kollisions-Setup
- Action-Scale

Einfach gesagt:
Das ist der normale G1.

### `g1_constants_crouch.py`
Das ist die wichtige Datei für **Crouch Walking**.

Sie ist fast wie die normale G1-Datei, aber mit einer anderen Startpose:
- tiefere Hüfte
- stärker gebeugte Knie
- angepasste Sprunggelenke

Einfach gesagt:
Der Roboter startet hier schon in einer **tieferen Hocke**.

Das ist wichtig, weil die Policy dann nicht erst lernen muss,
von einer hohen Standardpose in die Crouch-Pose zu kommen.

### `g1_23dof_constants.py`
Eine andere G1-Variante mit anderer Freiheitsgrad-Zahl.
Für den normalen 29-DoF Crouch-Weg ist sie nicht die Hauptdatei.

## Warum dieser Ordner wichtig ist

Wenn die Policy crouch walking lernen soll, reicht es nicht,
nur den Reward anzupassen.

Oft muss auch klar sein:
- in welcher Pose der Roboter startet,
- welche Gelenke wie skaliert werden,
- welche Aktuatoren verwendet werden,
- welche Kollisionen aktiv sind.

Genau das wird hier festgelegt.

## Wichtig für Crouch Walking

`g1_constants_crouch.py` sorgt vor allem dafür, dass:
- die Startpose tief ist,
- die Knie deutlich gebeugt sind,
- die Haltung zu einer crouch policy passt.

Das hilft dem Training sehr.

## Kurz gesagt

- `g1_constants.py` = normaler G1
- `g1_constants_crouch.py` = G1 für Crouch Training

Wenn du wissen willst, warum der Roboter in der Simulation schon "tief" aussieht,
liegt die Antwort meistens hier.
