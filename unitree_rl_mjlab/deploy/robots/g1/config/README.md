# G1 Controller-Konfiguration erklärt, ganz einfach

In diesem Ordner steht, **wie der G1-Controller organisiert ist**.

Der wichtigste Teil ist die FSM.
FSM bedeutet hier einfach:
Der Controller hat mehrere Zustände, und je nach Knopfdruck oder Situation wechselt er zwischen ihnen.

## Wichtige Datei

### `config.yaml`
Diese Datei beschreibt:
- welche Zustände es gibt,
- wie man zwischen ihnen wechselt,
- welche Policy oder welches Verhalten in welchem Zustand benutzt wird.

## Die wichtigsten Zustände

### `Passive`
Das ist der sichere Grundzustand.

Einfach gesagt:
- der Roboter macht nichts Intelligentes,
- er läuft keine RL-Policy,
- das ist ein sinnvoller Rückfallzustand.

### `FixStand`
Das ist ein stabiler Stand-Zustand.

Einfach gesagt:
- der Roboter geht in eine feste Pose,
- damit man sauber in andere Modi wechseln kann.

Das ist praktisch, weil RL oft nicht direkt aus jedem beliebigen Zustand gestartet werden soll.

### `VelocityWalk`
Das ist normales RL-Walking.

Hier nutzt der Controller:
- `config/policy/velocity/v0`

Also:
- normales Laufen,
- normale Pose,
- normale Walk-Policy.

### `VelocityCrouch`
Das ist RL-Crouch-Walking.

Hier nutzt der Controller:
- `config/policy/velocity/v1`

Also:
- tiefe Pose,
- crouch-spezifische Policy,
- eigener Modus im Controller.

### `Mimic_Dance1_subject2`
Das ist ein Motion-Imitation-Modus.

Er ist nicht für normales Velocity-Walking gedacht,
sondern für eine vorgegebene Referenzbewegung.

## Warum diese FSM-Struktur sinnvoll ist

Die Trennung ist gut, weil:
- normales Walking und Crouch Walking verschiedene Policies haben,
- nicht jeder Modus dieselben Startbedingungen braucht,
- ein sicherer Rückfallzustand wichtig ist.

## Zustandswechsel in einfachen Worten

Typisch ist die Logik:
- erst in `FixStand`
- dann in `VelocityWalk` oder `VelocityCrouch`
- bei Problemen zurück zu `Passive`

Das ist robuster, als direkt wild zwischen allen Zuständen zu springen.

## Wichtig für dein Setup

Diese Datei ist der Ort, an dem du am schnellsten prüfst:
- welche Policy ein Zustand wirklich lädt,
- ob Walk und Crouch sauber getrennt sind,
- welche Tastenkombination welchen Zustand aktiviert.

## Kurz gesagt

Wenn `policy.onnx` das Gehirn ist,
dann ist `config.yaml` der Schalterplan,
der sagt, wann welches Gehirn benutzt wird.
