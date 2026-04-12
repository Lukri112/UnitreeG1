## Zusammenfassung: Observation-Inputs, Outputs und Joint-Reihenfolge bei Reinforcement-Policies

**Problemstellung**  
Es sollte geprüft werden, wie zwei ONNX-Policies bezüglich ihrer Ein- und Ausgaben aufgebaut sind und ob sie mit dem realen Deploy-Setup eines **Unitree G1 Edu mit 29 DoF** kompatibel sind.

**Grundprinzip**  
Bei Reinforcement-Policies besteht der **Input** aus einem Observation-Vektor, also einer geordneten Liste von Zustandsinformationen des Roboters. Dazu gehören typischerweise Basisbewegung, Gravitation, Kommandos, Gelenkpositionen, Gelenkgeschwindigkeiten und oft auch die vorherige Aktion.  
Der **Output** besteht aus einem Action-Vektor, also den von der Policy vorhergesagten Sollwerten für die Aktoren, hier für **29 Gelenke**.

**Vergleich der Policies**  
Es wurde festgestellt, dass beide untersuchten Policies jeweils genau **einen Input** und **einen Output** besitzen:
- Input: `obs`
- Output: `actions`

Die Policies unterscheiden sich jedoch in der Größe des Observation-Vektors:
- **MJLab-Policy:** 98 Inputs
- **IsaacLab-Policy:** 480 Inputs

Beide Policies erzeugen jedoch denselben Action-Output:
- **29 Actions**

**Bedeutung für Deployment**  
Damit eine Policy korrekt auf dem Roboter läuft, reicht es nicht, nur dieselbe Anzahl an Inputs und Outputs zu haben. Entscheidend ist auch, dass die **semantische Reihenfolge** identisch ist:
- Welche Beobachtung steht an welcher Stelle im Observation-Vektor?
- Welches Gelenk gehört zu welchem Action-Eintrag?
- Welche Offsets, Skalierungen und Default-Posen werden verwendet?

Ein zentraler Punkt ist dabei die **Joint-Reihenfolge**.  
Die Policy lernt im Training nicht nur, *welche* 29 Gelenke existieren, sondern auch, **in welcher festen Reihenfolge** diese im Observation-Vektor und im Action-Vektor angeordnet sind. Genau diese Reihenfolge muss später in der `config.yaml`, in der `deploy.yaml` und im Controller- bzw. Deploy-Code konsistent beibehalten werden.

Denn:
- die **Observationen** für Gelenkpositionen und Gelenkgeschwindigkeiten werden in genau dieser Reihenfolge in den Input geschrieben,
- die **Actions** werden in genau dieser Reihenfolge wieder auf die Gelenke verteilt,
- auch **`default_joint_pos`**, **Offsets**, **Skalierungen** und andere gelenkbezogene Parameter müssen exakt zu derselben Reihenfolge passen.

Schon wenn die Reihenfolge zwischen **Training** und **Deployment** an nur einer Stelle abweicht, kann die Policy formal zwar weiterhin dieselben Dimensionen haben, aber inhaltlich falsche Werte lesen oder auf falsche Gelenke schreiben. Dann würde zum Beispiel ein Action-Eintrag, der im Training für das Knie gelernt wurde, im Deployment möglicherweise auf der Hüfte oder am Arm landen. In so einem Fall ist die Policy trotz passender Tensorformen **nicht tatsächlich kompatibel**.

**Empfohlene Architektur**  
Deshalb ist ein gemeinsamer **RobotState** sinnvoll, der alle Rohdaten des Roboters zentral bereitstellt. Aus diesem RobotState werden dann policy-spezifisch die passenden Eingaben über **ObsAdapter** erzeugt. Ebenso sollten die Outputs über passende **ActionAdapter** interpretiert werden.  
So kann sichergestellt werden, dass sowohl die Beobachtungen als auch die Aktionen in der exakt richtigen Reihenfolge verarbeitet werden.

**Ergebnis**  
Für die 29-DoF-G1-Deploy-Konfiguration wurde bestätigt, dass die Referenz-Policy strukturell zum offiziellen Setup passt:
- **98 Observation-Inputs**
- **29 Action-Outputs**
- passende `deploy.yaml` mit 29 Gelenken, 29 Offsets und 29 Skalierungswerten

Damit ist die neue eigene Policy **strukturell kompatibel**, sofern sie mit derselben Beobachtungs- und Aktionsreihenfolge trainiert und exportiert wurde wie die Referenz-Policy.

**Restunsicherheit**  
Sicher bestätigt wurde die **formale bzw. strukturelle Kompatibilität**. Nicht vollständig bewiesen ist allein, ob die neue Policy auch **semantisch exakt dieselbe Reihenfolge** von Observationen, Gelenken und Actions verwendet wie das originale Training- und Export-Setup.

**Praktisches Fazit**  
Observation-Inputs und Action-Outputs bei RL-Policies lassen sich am besten so erklären:  
Die Policy erhält einen **geordneten Zustandsvektor** des Roboters als Input und erzeugt daraus einen **geordneten Aktionsvektor** als Output. Für erfolgreiches Deployment müssen dabei nicht nur die Dimensionen stimmen, sondern auch die **genaue inhaltliche Zuordnung jedes Eintrags**.

Die **korrekte Joint-Reihenfolge** ist dabei einer der wichtigsten Punkte überhaupt:  
Sie muss im **Training**, in der **`config.yaml`**, in der **`deploy.yaml`** und in der **Runtime/Controller-Logik** vollständig konsistent sein. Nur dann bedeuten Observationen und Actions im Deployment dasselbe wie im Training.
