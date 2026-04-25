# Logs erklärt, ganz einfach

In diesem Ordner liegen gespeicherte Trainingsläufe.

## Typischer Aufbau

Zum Beispiel:
- `logs/rsl_rl/g1_velocity/<run_name>/...`

In einem Run-Ordner liegen oft:
- `model_XXXX.pt` = gespeicherte Checkpoints
- `policy.onnx` = exportierte Policy
- `params/env.yaml` = genaue Umgebungsbeschreibung
- `params/agent.yaml` = genaue PPO-Einstellungen

## Warum dieser Ordner wichtig ist

Wenn du später wissen willst:
- mit welcher Pose trainiert wurde,
- mit welchen Rewards trainiert wurde,
- welche PPO-Werte benutzt wurden,
- welcher Checkpoint erfolgreich war,

... dann findest du das hier.

## Für Crouch Walking besonders wichtig

Bei einem Crouch-Run kannst du hier sehr gut nachsehen:
- ob die crouch Robot-Config wirklich benutzt wurde,
- ob die Observation deploy-kompatibel war,
- welche Trainingsparameter aktiv waren.

## Einfach gesagt

Der Code sagt dir,
**was trainiert werden soll**.

Die Logs zeigen dir,
**was bei einem echten Lauf tatsächlich benutzt wurde**.
