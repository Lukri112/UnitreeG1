# Zusammenfassung

## Problemstellung
Beim Deploy des `unitree_rl_mjlab`-Controllers sowie im MuJoCo- und Isaac-Lab-Controller ist trotz erfolgreicher Netzwerkverbindung zum Roboter der Fehler **`Unmatched robot type`** aufgetreten. Die Verbindung zum Roboter wurde korrekt aufgebaut, der Start des Controllers wurde jedoch direkt nach dem Verbindungsaufbau abgebrochen. Zusätzlich wurde anfangs ein falsches Netzwerkinterface getestet, was getrennt vom eigentlichen Problem zu einem DDS-Fehler geführt hat.

## Vorgehensweise
Zunächst wurde geprüft, ob das Problem durch die Netzwerkverbindung verursacht wurde. Dabei wurde festgestellt, dass das Interface `enp2s0` korrekt war, während `enp3s0` nicht verfügbar war. Anschließend wurde der Quellcode des Controllers untersucht, insbesondere die Stelle, an der `mode_machine` gesetzt und mit dem vom Roboter gemeldeten Zustand verglichen wird.

Zur Analyse wurden Debug-Ausgaben eingebaut, damit sowohl der erwartete als auch der tatsächlich gemeldete `mode_machine`-Wert sichtbar gemacht werden konnten. Dabei wurde festgestellt, dass der Controller für den 29-DoF-Roboter fest auf **Robot Type 5** eingestellt war, der reale Roboter jedoch **Robot Type 6** meldete. Dadurch ist die interne Typprüfung fehlgeschlagen.

Danach wurde derselbe Abgleich auch in der MuJoCo-Simulation untersucht. Dort wurde die Logik in `G1Bridge` gefunden, in der abhängig von der Szene zwischen **23DoF** und **29DoF** unterschieden wurde. Für 23DoF wurde **Robot Type 4**, für 29DoF jedoch noch **Robot Type 5** gesetzt. Diese Stelle wurde analog angepasst. Anschließend wurde die gleiche Korrektur auch für den Isaac-Lab-Controller übernommen.

## Lösung
Die Lösung bestand darin, alle relevanten Stellen im Code so anzupassen, dass für den verwendeten **G1-29DoF-Roboter** nicht mehr `mode_machine = 5`, sondern **`mode_machine = 6`** gesetzt wird. Für **G1-23DoF** bleibt weiterhin **`mode_machine = 4`** bestehen.

Damit wurde die Typprüfung erfolgreich passiert und die Controller konnten korrekt gestartet werden.

## Inhaltlich wichtige technische Punkte
- Die Netzwerkverbindung war grundsätzlich funktionsfähig; das Problem lag nicht in der Kommunikation, sondern in der Robotertyp-Erkennung.
- Der reale Roboter hat als `reported mode_machine` den Wert **6** geliefert.
- Der ursprüngliche Controller hat für 29DoF fälschlich **5** erwartet.
- Die Zuordnung wurde auf folgende Logik korrigiert:
  - **23DoF → Robot Type 4**
  - **29DoF → Robot Type 6**
- Die MuJoCo-Bridge wurde entsprechend angepasst, damit die simulierte Low-State-Nachricht denselben Robot Type wie der reale Roboter verwendet.
- Dieselbe Anpassung wurde anschließend auch im Isaac-Lab-Controller vorgenommen.
- Die eigentliche Ursache war damit ein **Mismatch zwischen erwartetem Robot State / Machine Mode und dem tatsächlich vom Roboter gelieferten Zustand**.

## Relevanz für States, Inputs und Outputs
- Der `mode_machine` bestimmt, welcher Robotertyp vom Controller erwartet wird.
- Wenn der falsche Typ gesetzt wird, wird die Ausführung bereits vor dem eigentlichen FSM-Start abgebrochen.
- Damit wird verhindert, dass ein Controller mit nicht passender Robotervariante arbeitet.
- Diese Prüfung ist besonders wichtig, weil Robotervarianten sich in **Robot States**, **Input-Strukturen**, **Output-Strukturen** und typischerweise auch in der **Anzahl bzw. Zuordnung der Freiheitsgrade (DoF)** unterscheiden können.
- Für die Simulations- und Deploy-Pipeline musste daher sichergestellt werden, dass der gleiche Robot Type in
  - dem realen Controller,
  - der MuJoCo-Bridge und
  - dem Isaac-Lab-Controller
  konsistent verwendet wird.

## Ergebnis
Das Problem wurde durch die Umstellung des erwarteten Robot Types von **5 auf 6** für den 29DoF-G1 behoben. Die Controller in `unitree_rl_mjlab`, MuJoCo und Isaac Lab konnten danach erfolgreich gestartet werden.
