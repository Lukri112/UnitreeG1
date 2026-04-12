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
