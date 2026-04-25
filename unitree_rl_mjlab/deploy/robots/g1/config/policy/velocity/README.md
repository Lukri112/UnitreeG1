# Velocity Policies für G1 erklärt, ganz einfach

In diesem Ordner liegen die fertigen Policy-Dateien für den Deploy-Controller.

## Die zwei wichtigsten Unterordner

### `v0`
Das ist die normale Walking-Policy.

Typisch:
- normale Default-Pose
- normales Velocity Walking
- wird im Controller als `VelocityWalk` verwendet

### `v1`
Das ist die Crouch-Walking-Policy.

Typisch:
- tiefe crouch Default-Pose
- deploy-kompatible Observation
- wird im Controller als `VelocityCrouch` verwendet

## Was in jedem Policy-Ordner liegt

### `params/deploy.yaml`
Diese Datei beschreibt, wie der Controller die Policy benutzen muss.

Darin stehen zum Beispiel:
- Gelenk-Reihenfolge
- Default-Gelenkpose
- Stiffness / Damping
- Beobachtungsnamen und Reihenfolge
- Action-Scale
- erlaubte Command-Bereiche

Einfach gesagt:
Diese Datei sagt dem Controller,
**wie er die ONNX-Policy korrekt füttert**.

### `exported/policy.onnx`
Das ist die exportierte Policy selbst.

Einfach gesagt:
Das ist das trainierte neuronale Netz in einem Format,
das der Controller direkt laden kann.

## Warum `v0` und `v1` getrennt sind

Das ist wichtig, weil normales Walking und Crouch Walking nicht dieselbe Ausgangslage haben.

Zum Beispiel unterscheidet sich:
- die Default-Pose,
- das gewünschte Verhalten,
- die passendere Policy.

Darum ist die Trennung sinnvoll und sauber.

## Wichtiger Zusammenhang zum Training

Die Trainingsseite muss so gebaut sein,
dass die Actor-Observation später genau zu `deploy.yaml` passt.

Wenn das nicht passt, funktioniert Deploy oft schlecht oder gar nicht.

Darum gibt es im Python-Code spezielle Deploy-Varianten wie:
- `Unitree-G1-Flat-Deploy98`
- `Unitree-G1-Flat-Crouch-Deploy`

## Kurz gesagt

- `v0` = normale Walk-Policy
- `v1` = Crouch-Policy
- `deploy.yaml` = Beschreibung für den Controller
- `policy.onnx` = trainierte Policy
