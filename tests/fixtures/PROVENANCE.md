# Herkunft der Fixtures

**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**

Aufgezeichnet am **2026-08-07**.

Ohne Datum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht
mehr zu unterscheiden — die Datei sieht gleich aus.

## Was hier NICHT aufgezeichnet ist: Antworten

Alle vier Datenquellen dieses Servers verlangen einen Bearer-Token aus dem
API-Manager von opentransportdata.swiss. Ohne Token liefert keine von
ihnen Daten. Gemessen am Aufzeichnungstag, festgehalten in
`upstream_auth_probe.json`:

| Quelle | Methode | Antwort ohne Token |
|---|---|---|
| `ojp` | GET | **403** |
| `ckan` | GET | **401** |
| `siri_sx` | GET | **401** |
| `formation` | GET | **401** |

Die Payloads in den Testmodulen sind damit weiterhin **ausgedacht** und
tragen kein Datum. Das ist der Ist-Zustand und keine Nachlaessigkeit
dieses Laufs. Wer einen Token hat, zeichnet echte Antworten auf; das
Skript daneben ist dafuer die Vorlage.

## Was aufgezeichnet ist: der Vertrag

OJP 2.0 ist eine CEN-Norm (CEN/TS 17118). Ihr XML-Schema ist oeffentlich
und sagt, welche Elemente es gibt, welche Pflicht sind und wo sie stehen
duerfen — also genau das, worueber sich Produktivcode und
handgeschriebene Fixture einig sein koennen, ohne dass es stimmt.

Quelle: `https://github.com/VDVde/OJP`, fester Tag **`v2.0`**.
Ein Branch verschiebt sich; ein Index gegen einen beweglichen Stand waere
wieder undatiert, nur unauffaelliger.

### Das Schema selbst liegt NICHT im Repo

Das Quell-Repository fuehrt keine Lizenzdatei, und die zugrunde liegende
Norm ist kostenpflichtig. 424 KB fremdes XSD in ein MIT-Repo zu kopieren
waere eine Lizenzentscheidung, die ein Aufzeichnungsskript nicht treffen
darf. `ojp_2_0_contract.json` ist deshalb ein **abgeleiteter Index**:

- 508 Elementnamen des OJP-Namensraums
- 16 Strukturen und 25 Gruppen, auf die dieser Server baut
- 3 Aufzaehlungen, aus denen er Werte sendet

Gruppenverweise (`<xs:group ref=...>`) bleiben im Index **unaufgeloest**.
Wer sie aufloest, schreibt seine eigene Lesart hinein und kann sie danach
nicht mehr widerlegen — dasselbe Muster wie beim handgeschriebenen Mock,
eine Ebene hoeher.

Die Ableitung ist nachrechenbar: `python scripts/record_fixtures.py --check`
laedt dieselben Dateien am selben Tag und faellt, wenn Hash oder Ableitung
abweichen.

**Der OJP-Namensraum ist vollstaendig erfasst, der SIRI-Namensraum nicht.**
Elemente mit `siri:`-Praefix stehen in einem eigenen Schema, das hier nicht
gelesen wird; Pruefungen gegen diesen Index sagen ueber sie nichts.

### Gelesene Schema-Dateien

| Datei | Groesse | SHA-256 |
|---|---:|---|
| `OJP.xsd` | 2201 B | `a78e43c7304a4c7c73929659dd3a8edc6b2ab917571165669eb490163409df82` |
| `OJP_All.xsd` | 1247 B | `9ddfb7a87fef274bb20a92fad44e432a424768d87714c8998064523916a28621` |
| `OJP_Availability.xsd` | 19997 B | `e0bdd02a9a1443682ca40abaeac3830e6c47a546f18f170b4f19d9c6dbcbd97f` |
| `OJP_Common.xsd` | 22299 B | `9c29e47f99ff64dce309265b98ebb63059811ac6e0426752edcbd8f39704ac93` |
| `OJP_FacilitySupport.xsd` | 1057 B | `f85c4edaa20f6ba4335174fe1a0387cca40031ada93894a9f060c4e513d9df00` |
| `OJP_Fare.xsd` | 14789 B | `fb37854085c93665627b8f3d3aafdfa85267ad4c2ad6b445fc6e687be3d9e2d0` |
| `OJP_FareSupport.xsd` | 39580 B | `d44911f3783f1341dda9c469b9dfed93b4a6bae272812168f01b5fa2fe25a55d` |
| `OJP_JourneySupport.xsd` | 45476 B | `04693353f6d99033d122e446fd6079ae62bb58134c65f6e09a696169e4e329cc` |
| `OJP_Lines.xsd` | 4331 B | `b69e3c5321f404df686c118caf40f5491d07747d2007ea66339f4f1445e82079` |
| `OJP_Locations.xsd` | 23627 B | `5cae3f08db6f0500144644a542dcfca094154f4bfe5a43ed45a0891f7136fd90` |
| `OJP_ModesSupport.xsd` | 26596 B | `55cf74b4b031e97f3f000f15be2510bc3eb95e3e60c32264dc37f75623450238` |
| `OJP_PlaceSupport.xsd` | 30494 B | `1dd949db06fd4dc0f21f6978f94ad5ee55421025b0f0ce6840e94ff5ae0f9fa2` |
| `OJP_Requests.xsd` | 28268 B | `b599d54aed00bbd5dce124bba93c093b6708255d5b03ba6df61f9cfc4c2b582b` |
| `OJP_RequestSupport.xsd` | 9237 B | `92f266378dd065ed202abbc19786feb698d2a1de82e2fec62fc680d99b3eff9d` |
| `OJP_SituationSupport.xsd` | 2333 B | `284dbef3cd1f5e3af0840824378fdd082a3431c2cb12422819df7249d702c089` |
| `OJP_Status.xsd` | 3409 B | `b7fa91756871b08f4c5c97da4605a88aa96d0f064ea32b66e72837d78357ff78` |
| `OJP_StopEvents.xsd` | 16371 B | `84715591c9181c0a9ebe1d19579c70c34ab7007e61ee71a96af0f7b9e1d5b644` |
| `OJP_TripInfo.xsd` | 10404 B | `59a1c982f372c259bdcb1e9107403d7a30aed12d6661c3a53b40d972246c5a7d` |
| `OJP_Trips.xsd` | 94067 B | `e41c2713c8c0fd7fc2ea546b2cfa3a341b7f43e7de950c531e55fa9dd2aae934` |
| `OJP_Utility.xsd` | 4534 B | `86ba2ffa5a5138e6191b33e97194c184e3a0c75d37a7b1d826d8d4132fd96656` |

`OJP.xsd` unter `https://raw.githubusercontent.com/VDVde/OJP/v2.0/OJP.xsd`, alle uebrigen unter `https://raw.githubusercontent.com/VDVde/OJP/v2.0/OJP/`.
