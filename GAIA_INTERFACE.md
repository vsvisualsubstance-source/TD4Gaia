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

_(Prossime entry: aggiungere qui, datate, con la sessione che le scrive
tra parentesi — Core o TD/Mac.)_

## Domande aperte per la sessione TD/Envoy

- `td-silvermini2` (OPS) risulta registrato su stanza **"studio"**, non
  "soggiorno" come ipotizzato in precedenza (dato dal Device Registry
  reale, `/gaia/devices`) — è il parametro `Stanza` giusto lato TD o va
  corretto? Non toccabile da Gaia, solo da TD.
- Freeze periodico dell'agent TD (heartbeat fermo 20-40 min, la
  macchina/OPS resta sana) — possibile legame con l'errore "Visual
  Canvas callback12: Editing NumSamples is not supported in Time Slice
  mode" segnalato una volta, mai indagato a fondo. Serve accesso Envoy
  live per capire la causa.
- Il canale 3 (9008/MoodNudge) è realmente usato oggi da entrambe le
  istanze o solo da una? Non verificato da questo lato.
