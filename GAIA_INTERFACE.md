# GAIA ↔ TD — contratto d'interfaccia e log di interscambio

Due sessioni Claude lavorano su questo progetto senza accesso diretta
l'una all'altra: **Gaia/Core** (repo `gaia`, nessun Envoy, vede
Node-RED/MQTT/i sorgenti del bridge) e **TD/Mac** (questo repo, con
Envoy — accesso live alla rete TD reale). Git è l'UNICO canale di sync
fra le due: se una modifica tocca il confine tra i due lati, va sempre
pushata qui, non solo salvata localmente.

`ARCHITECTURE.md` in questo repo descrive la rete TD **interna**
(operatori, Visuals) — manutenuto/verificabile solo da chi ha Envoy,
può risultare disallineato se non riverificato dal vivo. Questo file
invece descrive il **contratto al confine** (porte, topic, schema) più
un changelog datato — è il punto dove ognuna delle due sessioni scrive
"cosa ho cambiato che riguarda l'altro lato" perché l'altra lo trovi al
prossimo giro.

Repo Gaia (pubblico, dettaglio completo): `github.com/vsvisualsubstance-source/gaia`
— in particolare `minipc/touchdesigner/README.md` e
`GAIA_TD_INTEGRATION.md` (schema indirizzi OSC completo),
`minipc/touchdesigner/osc_bridge.py` (sorgente del bridge Core↔TD).

## Canali attivi

| # | Direzione | Trasporto | Porta/topic | Contenuto |
|---|---|---|---|---|
| 1 | Gaia → TD | OSC/UDP | `7000` | Flatten grezzo di tutto lo stato WS (`/gaia/...`, ~1900 indirizzi) |
| 2 | Gaia → TD | OSC/UDP | `7001` | Feed curato "TD Canvas" (`/gaia/canvas/...`): mood+palette, oggetti YOLO con seed FNV-1a, luci pulite, lessico, sogno, eventi one-shot |
| 3 | TD → Gaia | OSC/UDP | `9008` (`OSC_IN_PORT`) | `MoodNudge`: deltas mood/lighting da TD verso Gaia → ripubblicati su MQTT `gaia/touchdesigner/<path>`. **Non attribuito a un device specifico — vedi "Aperto" sotto** |
| 4 | Gaia ↔ TD | MQTT | `gaia/device/{id}/status` \| `.../command` | Protocollo Pi-Manager: heartbeat leggero + start/stop/restart servizi (stesso schema di Pi/OPS/Core) |
| 5 | Gaia ↔ TD | MQTT | `gaia/devices/{id}/announce` \| `.../config` \| `.../profile` | Device Registry autoritativo di Node-RED (room graph, capabilities). **Un device TD deve pubblicare SIA il canale 4 SIA questo — vedi sotto** |
| 6 | Gaia → Admin | MQTT | `gaia/td-bridge/status` (retained) \| `.../command` | Pausa/ripresa del canale 1 per singola istanza TD, da Admin → Pi Manager |
| 7 | Pi/OPS → Admin | MQTT | `gaia/mocap-bridge/{sender_device_id}/status` (retained) \| `.../command` | Mocap grezzo (viso/mani/pose) opt-in per istanza TD — `sender_device_id` è il device mediapipe che manda, non TD |
| 8 | Watchdog → Telegram | MQTT | `gaia/notify/telegram` | Alert quando una TD nota è silente >90s (e recovery al ritorno) |

## Perché un device TD deve pubblicare SIA canale 4 SIA canale 5

Sono due registri quasi indipendenti lato Gaia: il canale 4 (Pi-Manager)
basta per apparire in Admin/Pi Manager, MA il Device Registry di
Node-RED (`brain.devices`, quello che decide il room graph e cosa
appare in Dashboard) si popola SOLO dal canale 5. Senza l'`announce`,
`/api/provision/assign` risponde "device non trovato" e la stanza
resta un'etichetta mai registrata — bug reale trovato e fissato il
2026-08-06 (vedi changelog).

## Canale 7 in dettaglio — mocap grezzo (viso/mani/pose), spec per chi ricostruisce in TD

Schema completo anche in `pi/mediapipe/README.md` (repo Gaia) — riassunto
qui perché è il canale con più margine di errore in ricostruzione:

```
/gaia/mocap/{device_id}/meta/room                       stringa
/gaia/mocap/{device_id}/meta/faces|hands|poses           interi, conteggio nel frame
/gaia/mocap/{device_id}/face/{person_id}                 478 punti × (x,y,z), UN messaggio, INTERLEAVED
                                                          → lista piatta di 1434 float:
                                                          [x0,y0,z0, x1,y1,z1, ..., x477,y477,z477]
                                                          NON planare (non [x0,x1,...,y0,y1,...])
/gaia/mocap/{device_id}/face/{person_id}/{regione}       sottoinsiemi con nome, STESSI punti sorgente,
                                                          stesso ordine interleaved — regione ∈
                                                          {lips(40), eye_left(16), eye_right(16),
                                                           eyebrow_left(10), eyebrow_right(10),
                                                           nose(24), oval(36)} punti
/gaia/mocap/{device_id}/hand/left|right/{person_id}      21 punti × (x,y,z), interleaved, 63 float
/gaia/mocap/{device_id}/pose/{person_id}                 33 punti × (x,y,z,visibility), interleaved, 132 float
```

**478, non 468**: `refine_landmarks=True` lato MediaPipe — i punti
468-477 (ultimi 10) sono gli iris (5 per occhio), IN AGGIUNTA alla
topologia classica a 468. Se il template/tesselazione usata in TD per
ricostruire la mesh assume 468 punti fissi, gli indici 468-477 vanno
trattati come iris a parte (non fanno parte di `FACEMESH_TESSELATION`),
non riciclati/wrappati su altri vertici.

**Convenzione coordinate**: normalizzate 0-1 rispetto al frame camera,
**origine in alto a sinistra, Y cresce VERSO IL BASSO** (convenzione
immagine standard, non 3D-Y-up) — `z` è profondità relativa (negativo =
più vicino alla camera). Se il rig TD porta queste coordinate in uno
spazio 3D Y-up senza flip esplicito su Y, il risultato è verticalmente
capovolto/specchiato: su una mano il risultato resta comunque
riconoscibile come "una mano" (forma tollerante), su un viso diventa
immediatamente irriconoscibile — è l'ipotesi più probabile per
l'asimmetria "mani ok, viso no" segnalata dall'utente il 2026-08-06.

**Diagnostica consigliata (dal lato Gaia i conteggi sono già verificati
byte-per-byte, 2026-07-25: 1434/63/132 float esatti)**: prima di
sospettare i dati, testare con i canali `face/{person_id}/{regione}` —
sono solo punti (nessuna tesselazione richiesta), quindi bastano sfere
su ~40-132 punti per vedere se il SILHOUETTE del viso (contorno +
occhi + naso + labbra) è coerente. Se quello è già storto (specchiato,
capovolto, punti sparsi a caso), il problema è nell'unpacking/assi, non
nella mesh a 478 punti. Se il silhouette è corretto ma la mesh completa
no, il problema è nella tesselazione/indici usati per i 478 punti.

## Changelog / interscambio

**2026-08-06 (Core)** — sessione lunga sul multi-istanza:
- Canale 1: fan-out dinamico a TUTTE le istanze TD vive (scoperta via
  canale 4, `role=="touchdesigner"`), non più un `TD_OSC_HOST` fisso.
  Pausa/ripresa per istanza da Admin (canale 6).
- Canale 7 aggiunto: mocap diretto opt-in per istanza (prima era
  hardcoded verso un solo IP).
- Watchdog (canale 8) aggiunto — bug trovato e fissato nello stesso
  giro: `last_seen` usava l'orario di ricezione locale invece del `ts`
  nel messaggio, "resuscitava" per errore device morti nei primi 90s
  dopo ogni riavvio del bridge.
- `gaia_device_agent.py`: aggiunto `_publish_announce()` (canale 5
  mancava del tutto, causa della stanza "studio" invisibile in
  Dashboard), `_publish_profile()`, `_last_error`, `fps`/`target_fps`/
  `dropped_frames` nello status (canale 4).
- Dashboard (Node-RED `ThreeViewEngineGAME`) e Admin
  (`web/admin.html`) aggiornati per mostrare stanze/perf dei device TD.
- **TODO aperto per la sessione TD/Envoy**: canale 3 (`MoodNudge`,
  porta 9008) non include alcun identificativo del device nei
  messaggi — con 2 istanze vive, i mood-nudge/comandi luci di due TD
  diverse arriverebbero mescolati sullo stesso topic MQTT senza modo
  di distinguerli. Proposta: includere `Deviceid` nel path OSC
  (`/gaia/td/{deviceid}/mood/...`); se la convenzione cambia serve poi
  un aggiornamento parallelo in `osc_bridge.py` (`TouchDesignerToGaia`)
  per instradare per device_id — coordinare qui prima di finalizzare.

**2026-08-06 (TD/Mac)** — sessione con Envoy live, in risposta ai 4 punti aperti sopra:

- **Canale 3 (MoodNudge, 9008) — device id**: implementato. `mood_send_relay`
  dentro `/project1/container1/MoodNudge` ora invia
  `/gaia/td/{deviceid}/mood/{dimension}` (prima: `/gaia/td/mood/{dimension}`,
  senza id). `deviceid` è letto da `Bridge/gaia_agent.par.Deviceid`
  (stesso valore che l'agent pubblica su MQTT). Verificato via Envoy che
  `MoodNudge` ha un SOLO sender OSC (`mood_out`, solo dimensioni mood:
  stress/calm/social/curiosity/energy) — nessun sender "lighting" esiste
  oggi nonostante il commento nel sorgente lo menzioni; probabilmente
  pianificato ma mai costruito. **Rottura intenzionale finché
  `osc_bridge.py`/`TouchDesignerToGaia` non instrada per device_id** —
  finché quel lato non è aggiornato, i mood-nudge da questa istanza non
  verranno più ripubblicati su `gaia/touchdesigner/<path>` con il vecchio
  path fisso. Fatto anche: `MoodNudge` non era mai stato esternalizzato
  (viveva solo nel `.toe` binario) — ora taggato `tox` così il diff resta
  leggibile in git.
- **Stanza "studio" vs "soggiorno"**: **la mia ipotesi iniziale era
  sbagliata** — avevo diagnosticato un bug in `camera_resolver.py`
  (`_ROOM_TO_CAM`) e cambiato la chiave `soggiorno`→`studio`, assumendo
  che `td-silvermini2` fosse lo stesso device di `ops-silvermini2`. Non
  avevo visibilità live sui device_id MQTT distinti per verificarlo.
  Gaia/Core ha chiarito nello stesso giro (vedi "Domande aperte" sotto,
  verificato dal vivo su `gaia/device/+/status`): sono **due device_id
  diversi sulla stessa macchina fisica OPS** — `ops-silvermini2`
  (mediapipe/camera, protocollo Pi-Manager) resta `soggiorno` (quello
  che conta per `_find_camera_ip`), `td-silvermini2` (un agent TD
  separato sulla stessa macchina) è `studio`. **Ripristinato**
  `_ROOM_TO_CAM["soggiorno"]` e l'etichetta in `ARCHITECTURE.md` — non
  era un bug, nessuna azione necessaria.
- **Freeze periodico / errore NumSamples+Time Slice**: causa probabile già
  trovata e fixata **prima** di leggere questo file (commit locale
  `cbbe63f`, la mattina del 2026-08-06): `canvas_bridge_clock` (LFO CHOP)
  aveva Time Slice ON mentre `canvas_bridge` (lo Script CHOP a valle, che
  ricostruisce un numero di canali variabile ad ogni cook via
  `registry.GetCanvasNumeric()`) lo ha volutamente OFF — un mismatch
  input/output che riproduce esattamente la classe di errore riportata
  ("Time slice mode not supported chop.timeslice=false" ↔ "Editing
  NumSamples is not supported in Time Slice mode", stesso errore TD,
  fraseggio diverso). Fix: `canvas_bridge_clock.timeslice = False`,
  verificato via restart (nessun errore, il valore persiste). Riverificato
  ora via Envoy: nessun altro Script CHOP nel progetto che tocca
  `numSamples` (i 3 dentro `Visuals/registry`, `event_watcher`,
  `script_zone_colors`, `dream_visibility`) ha oggi un input CHOP wired
  che possa reintrodurre lo stesso mismatch — tutti o non impostano
  `numSamples`, o non hanno input a monte. **Non confermato**: se questo
  sia davvero la causa dello specifico freeze dell'heartbeat
  (20-40 min) — il nesso è plausibile ma non provato. Da osservare se il
  freeze si ripresenta ora che il fix è in produzione da stamattina.
- **Uso reale del canale 3**: verificato — oggi i 5 pulsanti `Send*` di
  `MoodNudge` sono Pulse manuali, nessun trigger automatico nel
  progetto (nessun Timer/Execute che li pulsa). Il canale non è mai
  stato inviato automaticamente finora, solo su intervento manuale.
**2026-08-06 (Core, 2)** — analisi del canale 7 (mocap viso): utente
segnala "mani ricostruite bene, viso no" in TD. Dati lato Gaia già
verificati byte-per-byte in precedenza (conteggi esatti), quindi
ipotesi principale è TD-side, non un bug di invio — vedi sezione
"Canale 7 in dettaglio" sopra per lo spec preciso e la diagnostica
consigliata (testare prima i sottoinsiemi con nome, che non richiedono
tesselazione, per isolare dati-vs-rendering).

_(Prossime entry: aggiungere qui, datate, con la sessione che le scrive
tra parentesi — Core o TD/Mac.)_

## Domande aperte per la sessione TD/Envoy

- **[RISOLTO 2026-08-06, Core]** `td-silvermini2` (OPS) risultava
  registrato su stanza "studio", diverso da "soggiorno" — non è un bug:
  sono DUE device_id distinti sulla stessa macchina fisica OPS
  (192.168.1.240), ciascuno con la propria stanza indipendente.
  `ops-silvermini2` (mediapipe/yolo/camera, protocollo Pi-Manager) =
  "soggiorno"; `td-silvermini2` (agent TD) = "studio". Confermato dal
  vivo via MQTT (`gaia/device/+/status`). Nessuna azione necessaria
  (il fix errato tentato lato TD/Mac nello stesso giro è stato
  ripristinato — vedi changelog).
- **[RISOLTO 2026-08-06, TD/Mac]** Freeze periodico dell'agent TD
  (heartbeat fermo 20-40 min) — causa probabile già trovata e fixata
  (mismatch Time Slice `canvas_bridge_clock`/`canvas_bridge`, vedi
  changelog TD/Mac sopra). Nesso causale con lo specifico freeze non
  confermato — da osservare se si ripresenta.
- **[RISOLTO 2026-08-06, TD/Mac]** Il canale 3 (9008/MoodNudge) è
  realmente usato oggi da entrambe le istanze o solo da una? —
  verificato: solo uso manuale (Pulse), nessun trigger automatico nel
  progetto (vedi changelog TD/Mac sopra).
- **Nuovo, aperto**: il canale 7 (mocap viso) ricostruisce male in TD
  ("mani ok, viso no") — vedi entry changelog "Core, 2" sopra e sezione
  "Canale 7 in dettaglio" per lo spec e la diagnostica proposta. Non
  ancora indagato lato TD/Mac.
