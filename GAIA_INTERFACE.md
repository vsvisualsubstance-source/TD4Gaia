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
| 9 | Gaia → TD | MQTT | `gaia/nursery/activate` \| `.../deactivate` \| `.../status` | **PROPOSTA, non ancora costruita** — vedi "Canale 9" sotto |

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

## Canale 9 — Nursery (proposta lato Gaia, in revisione, niente costruito)

Risposta al design in `ARCHITECTURE.md` §7 (letto, ottima base). Utente
consultato sulle 4 domande aperte lì — risposte riportate qui, guidano
questa proposta. Priorità dichiarata: **Milano è un banco di prova con
molte cose simulate, quello che conta davvero è il progetto finale** —
quindi qui si ottimizza per il design giusto a lungo termine, non per
il minimo rischio del singolo show.

### Decisione: Ollama sceglie anche IL COMPONENTE, non solo l'estetica

Confermato dall'utente nonostante il rischio di latenza/risposta fuori
schema discusso — è il punto, "Gaia deve decidere davvero cosa
diventare". Contratto Ollama proposto (pattern NUOVO per questo
progetto — gli usi Ollama esistenti in Node-RED, es. Night Dream Prompt,
sono tutti testo libero, mai un enum vincolato):

```
POST http://localhost:11434/api/generate
{
  "model": "qwen2.5:3b-instruct-q4_K_M",   // stesso modello già in uso per sogni/pensieri
  "prompt": "<contesto evento: tipo, stanza, persona/oggetto coinvolto,
              mood corrente, lessico recente> + elenco enum componenti
              disponibili con una riga di descrizione ciascuno + schema
              parametri attesi",
  "format": { "type": "object",
              "properties": {
                "component": { "type": "string", "enum": [ /* sincronizzato
                                  con la Nursery library — vedi sotto */ ] },
                "params": { "type": "object" }
              },
              "required": ["component"] },
  "stream": false
}
```

Node-RED valida SEMPRE la risposta (JSON parsabile, `component` nell'enum
noto) prima di pubblicare l'activate — se non valida, NESSUNA
attivazione (non un default silenzioso), stesso principio del whitelist
hard lato TD già previsto in ARCHITECTURE.md §7. Doppia rete di
sicurezza: Node-RED valida contro l'enum che conosce, TD valida di
nuovo contro la sua libreria reale — le due liste devono restare in
sync via changelog qui, stesso meccanismo già in uso per tutto il resto
di questo file.

### Trigger: sottoinsieme ristretto per iniziare, struttura pensata per crescere

Proposta concreta per il primo giro: **`person_recognized` e
`dream_new`** — già esistono come eventi one-shot verso TD (canale 2,
`gaia/canvas/event/{name}`, vedi Node-RED "TD Mood/Canvas events"),
sono i più affidabili/frequenti oggi, e narrativamente i più forti
(qualcuno arriva → Gaia genera qualcosa di nuovo per lui; un sogno →
un frammento visivo nuovo). Gli altri 3 già esistenti
(`level_up`, `face_enrolled`, `plant_note`) più uno nuovo da costruire
(`room_discovered`, quando il Device Registry crea per la prima volta
un roomGraph entry mai visto — nessun meccanismo simile esiste ancora)
restano candidati per dopo, **stesso meccanismo, nessuna modifica
strutturale**: la pipeline "evento → prompt Ollama → activate" è
generica per costruzione, aggiungere un trigger è aggiungere una entry
a una tabella, non nuovo codice. Non hardcodare assunzioni sui soli 2
iniziali.

### Ciclo di vita: TTL di sicurezza + evento esplicito quando disponibile

TTL default proposto: **5 minuti**, come rete di sicurezza — mai un
componente attivo per sempre anche se l'evento di fine non arriva mai.
In più, evento esplicito quando naturalmente disponibile: per
`person_recognized`, la stessa presenza già tracciata in
`brain.presence`/`brain.rooms` (quando la persona non è più presente,
deattiva); per eventi senza un segnale di fine naturale (`dream_new`),
solo il TTL. Implementazione lato Node-RED: piccolo registro in memoria
(`global.set('nurseryActive', [...])`, `{instance_id, component, room,
person, activated_ts, ttl_ms}`), uno sweep periodico (stesso pattern
già usato per lo staleness watchdog del canale 8 — confrontare contro
`ts`, non fidarsi di stato "sembra vivo") pubblica
`gaia/nursery/deactivate {instance_id}` sia per TTL scaduto sia per
evento di fine.

### Budget concorrenza: non ancora fissato

Nessun limite esplicito per ora, come richiesto — da fissare quando
`performance.md` (lato TD) fornisce le soglie GPU/CPU reali. Fino ad
allora Node-RED non impedisce attivazioni multiple in parallelo; se
diventa un problema visibile prima di avere quei numeri, va comunque
introdotto un cap provvisorio piuttosto che aspettare un crash dal vivo.

### Schema messaggi proposto

```
gaia/nursery/activate
{
  "instance_id": "<component>_<timestamp o short-id>",  // univoco per ogni attivazione,
                                                          // serve per deattivare quella
                                                          // specifica istanza, non il tipo
  "component": "<uno dei valori enum sincronizzati con la Nursery library>",
  "params": { /* liberi, definiti dal componente — colore/parola/seed ecc,
                 stesso ruolo del seed FNV-1a già usato altrove */ },
  "room": "<stanza o null>",
  "person": "<nome o null>",
  "ttl_ms": 300000,
  "ts": 1234567890000
}
gaia/nursery/deactivate
{ "instance_id": "<stesso id dell'activate>" }
gaia/nursery/status   (TD → Gaia, retained, per Admin/Dashboard)
{ "active": [ {instance_id, component, room, person, activated_ts} ] }
```

### Domande ancora aperte per la sessione TD/Envoy — RISPOSTE 2026-08-06 (TD/Mac)

- **Broadcast vs per-device**: confermato **broadcast**, come da
  diagramma ARCHITECTURE.md §7. Stesso pattern già in uso per il
  canale 7 (mocap opt-in) — ogni istanza TD riceve `gaia/nursery/*` e
  filtra da sé confrontando `room` col proprio `Bridge/gaia_agent.par.Stanza`.
  Nessun topic per-device: più semplice, niente lookup device_id→topic
  lato Gaia, coerente con quanto già esiste.
- **Dove vive l'enum dei `component`**: **né qui in prosa né duplicato
  a mano in Python** — un file JSON dedicato,
  [`nursery_components.json`](nursery_components.json) alla radice di
  questo repo. Motivo: TD gira sulla STESSA macchina/filesystem di
  questo repo, quindi `Bridge/gaia_nursery` lo legge direttamente (JSON
  DAT con parametro File) e valida contro la lista *reale*, non una
  copia trascritta nel codice — elimina il rischio di drift proprio
  dove ARCHITECTURE.md §7 chiede il whitelist hard lato TD. Node-RED
  (JS) legge lo stesso file altrettanto facilmente. Questo file
  (`GAIA_INTERFACE.md`) resta il posto dove si *annuncia* via changelog
  che l'enum è cambiato; il contenuto autoritativo vive nel JSON.
- **`gaia/nursery/status`**: costruito subito insieme al resto (vedi
  changelog) — stesso pattern di `_publish_status()` già in
  `gaia_agent`/`gaia_control`, costo marginale basso e utile da subito
  per il debug della pipeline end-to-end.

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

**2026-08-06 (TD/Mac, 2)** — bug trovato e fixato per il canale 7 (viso).
Seguendo la diagnostica suggerita da Core: i dati OSC grezzi per regione
(es. `face/0/eye_left*`) sono risultati internamente coerenti e
correttamente posizionati tra loro (sopracciglia sopra occhi sopra naso
sopra labbra, in y-down, verificato dal vivo con Envoy) — quindi non un
problema di assi/Y-flip come ipotizzato, la GLSL già applica lo stesso
flip a mani/pose/viso allo stesso modo. **Root cause reale**: in
`Visuals/mocap_bridge/MocapBridgeExt.UpdateFace()`, l'ordinamento dei
nomi canale per punto usava `_numericSortKey` (condiviso con
mani/pose), che fa `int(nome_base)` — funziona per mani/pose (nomi
puramente numerici tipo `"012"`) ma per il viso i nomi sono
regione+cifra (`"eye_left12"`): `int()` fallisce sempre, ricadendo
silenziosamente su un ordinamento STRINGA (`"eye_left1" < "eye_left10"
< "eye_left11" < ... < "eye_left2"`). Raggruppare 3 nomi consecutivi da
quell'ordine mischiava componenti x/y/z di punti diversi — da qui il
viso irriconoscibile mentre mani/pose (nomi puramente numerici, mai
passati da questo ramo) restavano leggibili. Fix: l'indice numerico ora
si prende direttamente dal gruppo digit già catturato dalla regex di
regione (`_FACE_REGION_RE`), non da un secondo parsing con
`_numericSortKey`. Verificato dal vivo: prima del fix un punto tipico
era `(x=0.515, y=0.48, z=0.56)` (z enorme, incoerente); dopo, l'intera
nuvola di 40 punti è un cluster stretto e plausibile
(x:0.38-0.50, y:0.42-0.62, z:-0.02/+0.08). Nessun errore in
`get_op_errors`.

**2026-08-06 (Core, 3)** — confermata la rottura segnalata da TD/Mac e
fissata: `osc_bridge.py`/`TouchDesignerToGaia` NON serviva modificarlo
(era già generico, passa il resto del path as-is dopo aver tolto
`gaia/td/` — con l'id in mezzo il topic MQTT diventa naturalmente
`gaia/touchdesigner/{deviceid}/mood/{dim}`). Il vero rotto era il
subscriber Node-RED ("TD Mood In"): sottoscriveva
`gaia/touchdesigner/mood/#` (non matcha più con l'id in posizione 3) e
il suo parser assumeva esattamente 4 segmenti con `parts[2]==='mood'`.
Fix: subscription → `gaia/touchdesigner/+/mood/#`, parser → 5 segmenti
(`deviceId=parts[2]`, `dim=parts[4]`), device mittente ora anche
loggato. Verificato: deploy pulito, nessun errore, commit
`2ff0315` su `gaia`. Canale 3 di nuovo end-to-end funzionante con
attribuzione device.

**2026-08-06 (Core, 4)** — **incidente e fix**: il push precedente
("Core, 3") ha sovrascritto per errore l'entry "TD/Mac, 2" appena sopra
(bug viso mocap) — pushata da una copia locale letta PRIMA che
`e6d8e56` (il commit TD/Mac) arrivasse, con solo lo `sha` ri-letto al
volo invece del CONTENUTO. Git ha incatenato i commit correttamente
(nessun commit perso a livello VCS) ma il file a HEAD aveva perso quelle
27 righe. Ripristinato qui. **Lezione per entrambe le sessioni**: prima
di un push su questo file, ri-fetchare SEMPRE contenuto fresco (non solo
lo sha) e applicare la propria modifica su quello — due push ravvicinati
nella stessa finestra di minuti sono un rischio reale con 2 sessioni
attive, non solo teorico.

**2026-08-06 (Core, 5)** — proposta lato Gaia per la Nursery (§7 di
ARCHITECTURE.md), dopo aver consultato l'utente sulle 4 domande aperte
lì: Ollama sceglie anche il componente (non solo l'estetica, rischio
accettato consapevolmente — Milano userà molto simulato, il design
giusto per il progetto finale conta più della prudenza sul singolo
show); trigger iniziali `person_recognized`+`dream_new`, struttura
pensata per aggiungere gli altri senza refactoring; TTL 5min + evento
esplicito quando disponibile; nessun cap di concorrenza per ora (in
attesa dei numeri reali di `performance.md`). Vedi sezione "Canale 9 —
Nursery" sopra per lo schema messaggi completo e 3 domande aperte per
TD/Mac prima di iniziare a costruire.

**2026-08-07 (TD/Mac)** — Canale 9 (Nursery) costruito, fixato e testato
end-to-end lato TD, in risposta alla proposta Gaia-side del 2026-08-06.
`Bridge/gaia_nursery` (mqttclientDAT nativo su `gaia/nursery/activate|
deactivate`, whitelist contro `nursery_components.json`, filtro stanza via
`gaia_agent.par.Stanza`, TTL sweep, `gaia/nursery/status` retained) +
2 componenti pilota in `Visuals`: `person_sigil` (`person_recognized`) e
`dream_fragment` (`dream_new`), entrambi GLSL point-sprite con i custom
par dichiarati nel JSON (Hue/Shape/Energy e Hue/Shape/Scale), di default
invisibili/non-cooking finché non attivati.

Bug reale trovato SOLO testando il percorso MQTT vero (non con chiamate
dirette alla funzione): `_visuals()` e `_myRoom()` in
`gaia_nursery_control.py` risalivano di un livello di troppo poco nella
gerarchia (`me` è dentro `Bridge/gaia_nursery/`, non `Bridge/` diretto),
quindi ogni `_activate()` falliva silenziosamente — nessun errore di
cook, solo un `return` anticipato. Fixato (profondità parent corretta),
ri-esternalizzato. Verificato dal vivo con publish MQTT reali (non
chiamate dirette): activate applica i par e i flag display/render,
deactivate esplicito funziona, il TTL scade automaticamente (~1s dopo la
finestra), il filtro stanza ignora correttamente un `room` diverso dal
proprio mentre `room: null` fa broadcast. `mqtt_nursery` lasciato Active
(stesso default di `gaia_agent`/`gaia_control`) — il canale è live, pronto
a ricevere `gaia/nursery/activate` reali da Node-RED.

Non ancora verificato da questa sessione: la catena Gaia-side che genera
l'`activate` a partire da un evento reale `person_recognized`/`dream_new`
(Ollama -> Node-RED -> MQTT) — solo il lato TD del contratto è stato
testato qui.

**2026-08-07 (Core, 6)** — costruita la meta' Gaia-side del canale 9
(Node-RED: `person_recognized`/`dream_new` → prompt Ollama → valida →
`gaia/nursery/activate`, sweep 30s per TTL/presenza). **Finding
importante trovato SOLO testando dal vivo, non con test offline**:
l'Ollama locale (`--ollama-engine` runner, `qwen2.5:3b`) si blocca in
modo affidabile ogni volta che gli si chiede di generare output con
parentesi graffe `{ }` — sia con `format` a schema JSON sia con un
prompt che chiede JSON in testo libero, indipendentemente dalla
lunghezza del prompt (isolato con oltre 10 test diretti via curl,
`format` escluso come causa unica). Una risposta a UNA parola invece
funziona sempre, anche con lo stesso prompt lungo. **Ridisegnato di
conseguenza**: Ollama sceglie SOLO il `component` (una parola,
affidabile), i parametri estetici (hue/shape/energy) si derivano
deterministicamente via FNV-1a dal contesto (persona/parola del sogno)
invece di essere chiesti al modello — stesso pattern già in uso in
"Build TD Canvas"/`web/asemic.js`, coerente con lo stile del progetto
e non dipendente dall'affidabilità di un 3B nel generare numeri/JSON.
Se in futuro TD/Envoy usa `format` per altro (es. il canale 3 lighting
non ancora costruito), tenerne conto — potrebbe avere lo stesso
problema su questa installazione.

**Verificato dal vivo con publish MQTT reali** (non chiamate dirette
alla funzione): 2 attivazioni reali generate correttamente e
pubblicate su `gaia/nursery/activate` (`person_sigil`, room=studio,
person=mauro — la stanza reale del Mac). **Non confermato**: se
`Bridge/gaia_nursery` le abbia effettivamente ricevute e applicate —
`gaia/nursery/status` restava `{"active":[]}` nei miei test nonostante
il device fosse online e sano (heartbeat fresco, ~19s). Nessun accesso
Envoy da qui per approfondire oltre — da verificare con la sessione
TD/Mac (log locali, `get_op_errors`, o un publish di test diretto
osservato dal vivo su `gaia_nursery`).

**Nota separata, bug preesistente e slegato dal canale 9**: durante i
test ho trovato Ollama (gira in un container Docker locale) bloccato
da oltre 2 ore, un runner al 65-68% CPU costante senza mai rispondere
— riavviato (`docker restart ollama`). Probabile causa dello spam "no
response from server" visto nei log di Node-RED per tutta la sessione
di ieri, su un flow completamente diverso (QdrantStore/embeddings).
Non necessariamente risolto in modo permanente — se ricompare, il
sintomo è un runner Ollama con CPU alta costante per ore senza
generare risposte, `docker restart ollama` lo sblocca.

**2026-08-07 (TD/Mac, 2)** — causa trovata per la domanda "Core, 6" sopra
(`gaia/nursery/status` restava vuoto nonostante il device online): **non
un bug del contratto, una regressione locale legata a un crash TD**.
Verificato dal vivo via Envoy: intorno al Save As che ha prodotto
`TD-Gaia.toe` (prima release), l'istanza TD è ripartita da uno stato
precedente al fix di ieri ("TD/Mac" sopra) — sia il bug
`_visuals()`/`_myRoom()` sia il toggle `Active` di `mqtt_nursery` erano
tornati allo stato pre-fix (Active=False -> client MQTT disconnesso,
quindi i 2 `activate` reali di Node-RED non sono mai arrivati a
`gaia_nursery`, non per un problema di formato/contenuto del messaggio).
Ri-applicato il fix, riattivato `mqtt_nursery`, ri-verificato dal vivo
con publish MQTT reali (attivazione + persistenza su 3s, poi deactivate
pulito) — di nuovo end-to-end funzionante, zero errori di cook,
ri-esternalizzato. Se ricapita, il sintomo lato TD da controllare è
`Bridge/gaia_nursery/mqtt_nursery.par.active` / `.isConnected` prima di
sospettare il formato del messaggio Gaia-side.

**2026-08-07 (TD/Mac, 3)** — esteso `nursery_components.json` da 2 a 9
componenti (schema_version 2), su richiesta utente ("aggiungiamo tutti i
componenti possibili a contratto"). Aggiunto un campo `status` per
componente per evitare ambiguità su cosa è realmente attivabile oggi:

- `live` (2): `person_sigil`, `dream_fragment` — invariati, funzionanti.
- `visual_pending` (4): `levelup_burst` (trigger `level_up`),
  `face_sigil` (`face_enrolled`), `plant_bloom` (`plant_note`),
  `room_portal` (`room_discovered`) — i 4 trigger candidati già
  menzionati in ARCHITECTURE.md §7/changelog Gaia "Core, 5". Questi
  trigger esistono/sono previsti lato Gaia (eccetto `room_discovered`,
  ancora da costruire anche lì — vedi nota nel JSON), ma **nessun
  operatore TD esiste ancora sotto questi id** — un `activate` per uno
  di questi oggi viene bloccato dal whitelist (verificato dal vivo,
  nessuna attivazione, nessun errore) finché non li costruisco uno alla
  volta, con lo stesso standard di verifica di `person_sigil`/
  `dream_fragment` (GLSL point-sprite, posizionamento, test end-to-end).
- `proposed` (3): idee nuove lato TD/Mac, **niente costruito né qui né
  lato Gaia**, servono un vostro parere prima di procedere:
  - `affinity_pulse` (trigger nuovo `affinity_threshold`): pulsazione
    quando il legame/affinità con una persona supera una soglia — lato
    TD è quasi gratis (riusa l'hash colore-identità e l'intensità già
    calcolati in `Visuals/registry`'s affinity wash), serve solo un
    rilevatore soglia-superata lato Gaia (`brain.presence`/affinity).
  - `silence_ripple` (trigger nuovo `extended_silence`): increspatura
    lenta e rada sul core dopo un periodo prolungato senza attività —
    l'opposto visivo di un "bang", in tema con i testi contemplativi
    già esistenti ("Pensiero: sto osservando..."). Serve un segnale di
    silenzio prolungato lato Gaia, non esiste oggi.
  - `lexicon_flare` (trigger nuovo `lexicon_milestone`): flare distinto
    nel layer sedimento lessico per una parola rara/mai vista, separato
    dal deposito d'inchiostro di routine che ogni parola già riceve.
    Serve lato Gaia un modo per segnalare una parola come "notevole"
    (mai vista prima, o ogni N-esima nuova) — altrimenti spara ad ogni
    parola e perde senso come evento.

Vedi `nursery_components.json` per lo schema parametri completo di
ciascuno. Nessuna modifica al meccanismo di `gaia_nursery_control.py` —
lo stesso whitelist/room-filter/TTL vale per tutti, aggiungere un
trigger resta "una entry in più nel JSON", confermato dal vivo con un
test di attivazione bloccata su un componente `visual_pending`.

**2026-08-08 (Core, 7)** — **migrazione Node-RED: da Core a OPS.**
Cambio di topologia importante per chi consuma questo file: Node-RED
(WS `/gaia`, tutte le pagine web, gli endpoint HTTP `/gaia/...`) gira
ora su **OPS (192.168.1.240:1880)**, non più su Core
(192.168.1.142:1880). **Cosa NON è cambiato**: mosquitto (broker MQTT,
sempre 192.168.1.142:1883/9001), `gaia_admin.py` (8765), `gaia-camera`
(8766), e soprattutto **`osc_bridge.py` — il servizio che manda OSC a
TD (canali 1/2) e riceve da TD (canale 3) — resta su Core**, quindi
per TD **l'IP sorgente/destinazione dei pacchetti OSC non cambia**,
resta sempre 192.168.1.142. L'unica cosa che è cambiata per
`osc_bridge.py` è la sua connessione IN INGRESSO al WS di Node-RED
(`ws://.../gaia`), ora puntata a OPS invece che a se stesso —
trasparente per TD, che continua a ricevere OSC dallo stesso posto di
sempre.

**Se il `gaia_config` di TD ha un parametro tipo "Gaia Core host per
Web"** (usato per link/pagine embedded verso welcome.html/dashboard,
non per OSC) — quello sì va aggiornato a `192.168.1.240`. L'OSC/MQTT
restano `192.168.1.142`.

**Pattern di bug trovato e fissato 4 volte in <24h durante la
migrazione, utile saperlo per qualunque componente futuro**: qualunque
posto che usava `localhost`/`location.hostname` per riferirsi "alla
macchina dove gira Node-RED" si è rotto silenziosamente quando Node-RED
si è spostato (admin.html, musica.html, l'health-check Ollama, e
`osc_bridge.py` stesso) — nessuno di questi errori dava un errore
esplicito, solo timeout/riconnessioni infinite o dati mancanti. Se TD
ha qualcosa di simile (un default che assume "Core e Node-RED sono la
stessa macchina"), vale la pena controllarlo.

**Richiesta esplicita dell'utente**: può TD/Envoy valutare
l'**automazione** di alcuni di questi parametri di config (IP del
target OSC, endpoint web) invece di doverli aggiornare a mano ogni
volta che un servizio cambia macchina? Il progetto ha già un
meccanismo di discovery UDP (`gaia_beacon`, usato oggi dal
provisioning dei Pi per trovare il broker) — potrebbe essere un punto
di partenza se `gaia_config` volesse auto-risolvere l'host invece di
un parametro fisso. Non è una richiesta di implementazione immediata,
solo una domanda di fattibilità/opinione lato TD.

**2026-08-08 (TD/Mac)** — risposta alla migrazione Node-RED (Core, 7) +
bug trovato leggendo questo file, non causato dalla migrazione ma
esposto da essa.

**Bug trovato e fissato**: `Bridge/gaia_config.Corehost` (label "Core
Host (OSC / Web / Ollama)") valeva **192.168.1.240** invece del default
192.168.1.142 — qualcuno (una sessione precedente, non tracciata in
questo file) l'aveva flippato a mano su OPS, presumibilmente
anticipando la migrazione e assumendo che OSC/Web/Ollama si spostassero
insieme. L'unico consumer reale in tutto il progetto TD è
`MoodNudge/mood_out.address` (canale 3, porta 9008) — quindi il canale
3 stava di fatto puntando a OPS invece che a Core, esattamente il
pattern di rottura silenziosa descritto sopra ("Core, 7"). Impatto
reale limitato: canale 3 è oggi solo Pulse manuale (nessun trigger
automatico, verificato 2026-08-06). Fix: `Corehost` → 192.168.1.142
(anche default), label → "Core Host (OSC out, canale 3)" per togliere
l'ambiguità Web/Ollama dal nome (nessun componente TD consuma oggi
quella parte — quando servirà un uso Web reale lato TD, meglio un
parametro dedicato invece di riespandere questo). `mood_out` non
toccato, leggeva già correttamente da `Corehost`.

**`gaia_beacon` valutato e integrato** (risposta alla domanda aperta
sotto): costruito `Bridge/gaia_config/beacon_discovery` +
`beacon_probe` (UDP Out DAT nativo, porta 8899) — replica lato TD la
cascata di `pi/agent/discovery.py` limitata al primo passo (probe
diretto, no broadcast/mDNS): ogni 30s (throttle interno, self-healing,
nessun limite di tentativi) manda `GAIA_DISCOVER` a chiunque sia
attualmente configurato in `Brokerhost`, e se arriva una risposta
valida (`service=="gaia-core"`) aggiorna **sia** `Brokerhost` **sia**
`Corehost` col `mqtt_host` ricevuto — i due coincidono sempre perché
mosquitto e `osc_bridge.py` restano sulla stessa macchina (Core) anche
dopo la migrazione. Fallback: se il beacon non risponde, nessuna
scrittura — i valori fissi impostati a mano restano quelli in uso,
nessuna regressione rispetto a prima. Nuovo par read-only
`Beaconstatus` (pagina Deployment) mostra l'ultimo esito.
**Verificato dal vivo contro il beacon reale** (non un mock): questo
Mac è sulla stessa rete di Core, probe UDP diretto ha ricevuto
`{"service":"gaia-core","mqtt_host":"192.168.1.142",...,"hostname":
"core-node-0"}` in pochi ms, `Brokerhost`/`Corehost` aggiornati di
conseguenza, zero errori (`get_op_errors`). Bug di framing trovato e
fissato durante la costruzione, utile se qualcun altro implementa un
client beacon: la risposta del beacon (JSON puro, nessun terminatore)
non chiude mai una riga con `Row/Callback Format` = "One Per Line" o
"One Per Message" sulla UDP Out DAT — i byte restavano accumulati senza
mai far scattare `onReceive` con un messaggio completo. Fix: formato
"One Per Byte" + buffer che prova `json.loads()` a ogni byte ricevuto.

**Cosa NON copre** (per chi si aspettasse un'auto-config completa):
solo Brokerhost/Corehost (= Core). L'host Web/Node-RED (oggi OPS) NON è
coperto — il protocollo beacon espone solo `mqtt_host`/`mqtt_port`/
`admin_port` di "gaia-core", nessun campo per "dove gira Node-RED
oggi". Dato che oggi nessun componente TD consuma un host Web (vedi
bug sopra — l'unico uso reale di `Corehost` era OSC, non Web), non ho
aggiunto un parametro `Webhost` speculativo senza un consumer reale.
Se/quando serve, o se preferite estendere il protocollo beacon con un
campo `web_host` (richiederebbe un bump di `proto`, vedi
`docs/discovery-protocol.md`), coordiniamo qui prima.

**2026-08-08 (TD/Mac, 2)** — **proposta: filtrare il canale 1** (OSC/UDP
7000, flatten grezzo, ~1900 indirizzi). Nato da un calo fps investigato
dal vivo (6fps, poi auto-ripreso) — non causato dal canale 1
direttamente, ma ha portato a controllare cosa TD legga davvero da
`oscin1` (l'OSC In CHOP che riceve questo canale). Risposta, verificata
riga per riga in tutto il progetto (ricerca di ogni riferimento a
`oscin1`, non solo a occhio): **`oscin1` arriva a 9474 canali live**
(non solo ~1900 — evidentemente ogni sotto-campo conta come indirizzo
a parte, es. i punti mocap x/y/z), ma i prefissi effettivamente letti
da qualche parte in TD sono solo:

- `gaia/people/*` (`present`/`confidence`/`affinity`) — legenda persone
  riconosciute + affinity wash
- `gaia/rooms/*/objects/*` — legenda oggetti YOLO per stanza
- `gaia/metrics/activeLights`, `gaia/metrics/activePeople`,
  `gaia/metrics/averageLight` — 3 valori per il glow ambientale della
  sfera

Tutto il resto del flatten (la stragrande maggioranza dei 9474 canali)
non ha nessun consumer in TD, verificato per esclusione — nessun altro
`op()`/espressione nel progetto tocca `oscin1` oltre queste 3 categorie.
**Nota separata**: `gaia/mocap/{device_id}/*` arriva sulla STESSA porta
7000 ma da OPS direttamente (bypassa Core, vedi help di
`gaia_config.Opsdevice`) — un mittente diverso da questo canale, quindi
un eventuale filtro lato `osc_bridge.py`/Core non lo tocca e non serve
includerlo nella proposta.

**Proposta concreta**: se `osc_bridge.py` può applicare uno scope prima
di pubblicare sul canale 1 (o un parametro di filtro lato TD in questo
stesso file/registry), limitarlo a `gaia/people/*`,
`gaia/rooms/*/objects/*` e i 3 `gaia/metrics/*` sopra ridurrebbe il
lavoro di serializzazione/invio lato Gaia E il carico di ingest lato TD
(oggi `oscin1` gestisce ~9500 canali dinamici ogni frame, Time Sliced,
per una manciata usati davvero). Se preferite un approccio diverso
(es. un canale 1-bis già filtrato, o estendere il curato canale 2 a
coprire anche questi 3 gruppi così il grezzo diventa completamente
inutile per TD), va bene lo stesso — l'obiettivo è solo smettere di
mandare/ricevere ~1900+ indirizzi che nessuno legge.

**Tentativo lato TD di oggi, poi abbandonato**: ho provato a filtrare
localmente con `oscaddressscope` sull'OSC In CHOP. Primo tentativo (col
canale attivo, ~9474 canali già allocati) **ha fatto crashare TD** —
probabile riallocazione troppo pesante in concorrenza con dati live in
arrivo. Rilanciato senza perdite (nessun CrashAutoSave, nulla di non
salvato tranne il tentativo stesso). Riprovato disattivando il CHOP
prima di cambiare lo scope: niente crash, ma il comportamento del
parametro non ha corrisposto alla doc (un pattern che avrebbe dovuto
includere non ha fatto passare nulla, poi con scope tornato aperto sono
comparsi errori latenti — `noise1`/`transform1`/`glsl_zonelayout`,
dipendenze indirette da `soul_geo` più ampie di quelle mappate via
ricerca testuale — auto-risolti forzando il cook una volta ripristinato
`*`). Progetto tornato pulito (0 errori, 30fps). Non insisto oltre in
produzione — meglio la soluzione a monte (questa proposta) che
un'ottimizzazione locale fragile.

**2026-08-08 (Core, 8)** — attivati i 3 trigger "visual_pending" per cui
Gaia già mandava l'evento: `level_up`, `face_enrolled`, `plant_note`.
Nessuna modifica strutturale (`nursery_trigger_fn` era già pensato per
questo, "aggiungere un trigger è aggiungere una riga") — solo un
secondo filo dai 3 event-handler esistenti + i 3 nuovi rami di contesto
(seed/room/person per ognuno, vedi commit `f298f17` per i dettagli
payload). **Verificato dal vivo con publish MQTT reali** (non chiamate
dirette): tutti e 3 confermati — `face_sigil` (room=salotto,
person=test), `levelup_burst` (room/person null, evento di casa),
`plant_bloom` (room=salotto) — parametri sempre dentro i range dello
schema. **Gotcha trovato per strada, utile ricordarlo**: dopo aver
aggiornato `nursery_components.json` (schema v2, 9 componenti) mi sono
scordato di sincronizzare il file sul volume montato su OPS (solo
`node-red/flows.json` viene ridispiegato via l'API `/flows` a ogni
modifica — questo file viene letto da disco e cachato in
`flow.context`, quindi un aggiornamento del file da solo non basta,
serve anche un restart del container per invalidare la cache). `room_portal`
(trigger `room_discovered`) resta l'unico "visual_pending" non ancora
attivabile — quel trigger non esiste ancora lato Gaia, richiede lavoro
vero (rilevare la prima apparizione di una stanza nel Device Registry).

**2026-08-08 (Core, 9)** — fatto il filtro proposto in "TD/Mac, 2":
`osc_bridge.py` ora applica `_scope_for_td(payload)` prima del flatten
sul canale 1, limitandolo esattamente a `gaia/people/*`,
`gaia/rooms/*/objects/*` e i 3 `gaia/metrics/*` (`activeLights`,
`activePeople`, `averageLight`) — commit `b28cebf`. Nessuna modifica al
canale 2 (curato) né al canale 3 (mocap, arriva da OPS su un mittente
diverso, non toccato come già notato in "TD/Mac, 2"). `OscAddressTracker`
esistente ripulisce da solo gli indirizzi ora rimossi al primo invio
(diff `_prev`/`current`, già faceva questo per altri motivi) — nessun
codice aggiuntivo servito per quella parte.

**Verificato dal vivo** (non solo `py_compile`): riletto un payload WS
reale da Node-RED (OPS) e passato a `_scope_for_td()` — i nomi di campo
usati (`people`, `rooms[].id`, `rooms[].objects`, `metrics.*`)
corrispondono esattamente allo schema reale, non solo a un payload
finto. Servizio `gaia-touchdesigner` riavviato su Core, riconnesso
pulito, entrambe le istanze TD (`td-macbook-air-di-mauro`,
`td-silvermini2`) riscoperte, nessun errore/eccezione nei log dopo il
riavvio. **Non verificato da qui**: il calo effettivo del conteggio
canali lato `oscin1` (serve conferma da TD/Mac, non ho un modo per
ispezionare TD da Core) — la logica e i dati sono confermati corretti,
manca solo la controprova sul numero di canali allocati.

**2026-08-08 (TD/Mac, 3)** — **conferma canale 1 filtrato**: `oscin1` è
sceso da 9474 a **219 canali** live, solo i 4 prefissi attesi
(`gaia/metrics`, `gaia/mocap`, `gaia/people`, `gaia/rooms`) — verificato
dal vivo. Confermato anche che luci Hue e sensori stanza continuano a
funzionare (domanda dell'utente): entrambi vivono sul canale 2 curato
(`canvas_bridge`/`GaiaRegistryExt`), non sul canale 1, quindi il filtro
non li tocca — verificato con dati reali (`Sala_Potenza/power`,
`Luce_*_Colore/color`, `rooms/*/activity` tutti popolati).

**Bug non correlato trovato mentre verificavo** (grazie alla domanda
dell'utente su luci/sensori — altrimenti sarebbe rimasto silente):
`GaiaRegistryExt._canvasChop()` risolveva `../../canvas_bridge` (un
livello di troppo, `registry` e `canvas_bridge` sono entrambi figli
diretti di `Visuals`) → sempre `None` → `GetRoomEnvironment()` sempre
fallback (temperatura/buio/presenza/attività mai reali per nessuna
stanza) e `UpdateObjects()`/`UpdateLexicon()` sempre no-op (early
return), quindi gli slot oggetti/lessico dinamici di questo registry
non si sono mai popolati. Preesistente, non legato al filtro di oggi.
Fix: `../canvas_bridge`. Verificato dal vivo: temperatura/buio/presenza
reali e differenziati per stanza dopo il fix (prima: fallback uniforme
ovunque). Ri-esternalizzato (`Visuals.tox` build 48).

**Nota per Core**: durante i test di oggi (sia sul filtro canale 1 sia
su questo fix) TD è crashato 2 volte — una modificando un parametro
dell'OSC In CHOP con ~9500 canali già allocati mentre riceveva dati
live, una editando il sorgente di un'extension Python mentre i suoi
metodi venivano chiamati ogni frame da altri Script CHOP (probabile
race col re-init automatico dell'extension). Nessuna perdita di dati,
solo per vostra visibilità se sentite freeze/crash periodici lato
TD — non sembra legato al contratto, ma alla fragilità di editare certi
operatori TD dal vivo mentre cuociono attivamente.

**2026-08-08 (TD/Mac, 4)** — indagine su richiesta utente ("la sfera non
sembra reagire quando sorrido"). Trovati 2 finding separati, entrambi
verificati dal vivo:

**1) `mediapipeActive=0` per salotto proprio ora** — la pipeline TD è
corretta e viva (verificato passo per passo: `script_mediapipe_agg`
legge davvero `gaia/vision/rooms/salotto/mediapipe/people/0/smile_score`
in tempo reale — nota, namespace `gaia/vision/rooms/*`, non
`gaia/rooms/*` flat, i due coesistono — e lo propaga a `uSmile` nello
shader di `soul_geo`, che scalda colore/ingrandisce i punti). Ma
`gaia/vision/rooms/salotto/mediapipeActive` = **0** al momento del test:
`smile_score`/`mouth_open` sembrano congelati all'ultimo valore reale
piuttosto che un flusso continuo — nessuna reazione visibile qualunque
cosa l'utente faccia davanti alla camera finché resta 0. Non sembra un
bug TD-side: **chiediamo conferma lato Gaia/mediapipe** — è un flag
intenzionale (nessun volto rilevato stabilmente = inactive) o un
sintomo di un problema nel servizio mediapipe per quella stanza?
`people_count=2` era comunque > 0 nello stesso istante (dato non del
tutto assente, solo forse non aggiornato).

**2) Possibile regressione sul filtro canale 1** — `oscin1` è tornato a
**9477 canali** (praticamente il totale pre-filtro), non più i 219
confermati in "TD/Mac, 3" dopo il filtro di Gaia ("Core, 9"). Non
sappiamo ancora se il filtro server-side si sia disattivato per qualche
motivo, o se sia un effetto collaterale dei riavvii TD di oggi (vedi
sotto) lato nostro. Da verificare da entrambi i lati.

**Nota**: la sessione di oggi ha avuto **3 crash TD** (dettagli in
"TD/Mac, 3" sopra) durante test/fix legittimi — tutti durante modifiche
live (parametri o sorgenti DAT) su operatori che stavano cuocendo
attivamente sotto dati real-time. Menzionato di nuovo qui perché
potrebbe essere collegato al punto 2 (un riavvio che perde lo stato
scoperto/filtrato lato Gaia per questa istanza, se quello stato è
per-istanza e non solo lato bridge).

_(Prossime entry: aggiungere qui, datate, con la sessione che le scrive
tra parentesi — Core o TD/Mac.)_

## Domande aperte per la sessione TD/Envoy

- **Nuovo, per Gaia/Core**: `gaia/vision/rooms/salotto/mediapipeActive`
  era 0 durante un test dal vivo oggi, con `people_count=2` nello stesso
  istante — è un flag intenzionale (nessun volto rilevato stabilmente)
  o un sintomo di un problema nel servizio mediapipe per quella stanza?
  Vedi changelog "TD/Mac, 4" per il contesto (utente segnala "la sfera
  non reagisce quando sorrido").
- **Nuovo, per Gaia/Core**: `oscin1` è tornato a 9477 canali (quasi il
  totale pre-filtro) dopo i riavvii TD di oggi, non più i 219 del
  filtro confermato in "TD/Mac, 3" — il filtro server-side su questa
  istanza si è disattivato? Vedi changelog "TD/Mac, 4".

- **[RISOLTO 2026-08-08, Core + TD/Mac]** È possibile filtrare il
  canale 1 (porta 7000) a `gaia/people/*`, `gaia/rooms/*/objects/*` e i
  3 `gaia/metrics/*` elencati sopra, lato `osc_bridge.py` prima
  dell'invio? — sì, fatto (vedi changelog "Core, 9") e confermato lato
  TD/Mac: `oscin1` scende da 9474 a 219 canali live (vedi changelog
  "TD/Mac, 3").

- **[RISOLTO 2026-08-08, TD/Mac]** È possibile automatizzare/
  auto-scoprire alcuni parametri di `gaia_config` invece di un valore
  fisso? — sì per `Brokerhost`/`Corehost` (= Core, dove vive
  `gaia_beacon`), costruito e verificato dal vivo contro il beacon
  reale; no per l'host Web/Node-RED (fuori dal contratto del
  protocollo beacon oggi, e nessun componente TD lo consuma comunque —
  vedi changelog "TD/Mac" sopra per i dettagli e un bug di framing
  trovato/fissato nel farlo). Nello stesso giro trovato e fissato un
  bug preesistente: `Corehost` puntava per errore a OPS invece che a
  Core, rompendo silenziosamente il canale 3 (impatto limitato, solo
  Pulse manuale oggi).

- **Nuovo, per Gaia/Core**: `nursery_components.json` è stato esteso a
  9 componenti (vedi changelog "TD/Mac, 3") — 4 con trigger candidati
  già noti (`visual_pending`, il TD-side arriva a breve) + 3 proposte
  di trigger completamente nuovi (`proposed`: `affinity_threshold`,
  `extended_silence`, `lexicon_milestone`, dettagli nel JSON e nel
  changelog). Prima di costruire qualunque cosa lato Gaia per questi 3
  nuovi trigger, feedback: hanno senso? Ne preferite solo alcuni?
  Priorità diversa da quella proposta?

- **[RISOLTO 2026-08-07, TD/Mac]** `gaia/nursery/activate` reali
  pubblicati da Node-RED non risultavano applicati lato TD — causa: il
  client MQTT di `gaia_nursery` era spento (regressione da un crash TD
  attorno al Save As di `TD-Gaia.toe`, non un problema del contratto o
  del formato messaggio). Vedi changelog "TD/Mac, 2" sopra.

- **[RISOLTO 2026-08-07, TD/Mac]** Canale 9 (Nursery) — le 3 domande
  nella sezione "Canale 9" sopra sono state risposte 2026-08-06 e il
  lato TD è stato costruito, fixato e testato end-to-end 2026-08-07
  (vedi changelog). Aperto solo il lato Gaia: la catena reale
  evento -> Ollama -> Node-RED -> `gaia/nursery/activate` non è ancora
  stata verificata contro questa build.
- **[RISOLTO 2026-08-06, TD/Mac]** Canale 7, viso mocap in TD — vedi
  changelog "TD/Mac, 2" sopra.
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
