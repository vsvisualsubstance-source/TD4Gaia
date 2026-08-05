"""
GAIA Service Control — play/stop/restart dei servizi base dei device
(Pi, OPS, Core) nativamente dentro TouchDesigner. Stesso ruolo di Pi
Manager in web/admin.html, stesso protocollo MQTT, ma qui TD e' il
CONTROLLORE: ascolta gli status di TUTTI i device (gaia/device/+/status)
e puo' inviare comandi enable/disable/restart a ciascuno.

Complementare a gaia_device_agent (che invece fa comparire QUESTA istanza
TD come UN device controllabile) — i due coesistono nello stesso progetto
senza conflitti, sono moduli indipendenti.

SETUP IN TD
1. COMP contenitore (es. "gaia_control"), Custom Page opzionale con
   Mqtthost (Str, default 192.168.1.142) / Mqttport (Int, default 1883).
2. Un Table DAT vuoto chiamato "devices_table" nello stesso COMP — questo
   script lo riscrive ogni volta che arriva uno status (una riga per
   coppia device+servizio: device_id, name, stanza, role, service, state,
   offline). Bind diretto per un List COMP.
3. Text DAT "td_service_control" con QUESTO file come sorgente esterna.
4. Execute DAT nello stesso COMP:
       def onCreate():
           op('td_service_control').module.start()
           return
       def onFrameStart(frame):
           op('td_service_control').module.drain_inbox()
           return
       def onExit():
           op('td_service_control').module.stop()
           return
   USARE "Create" (onCreate), NON "Start" (onStart) — stesso motivo di
   gaia_device_agent: onStart e' un evento di APPLICAZIONE (una volta per
   sessione TD), NON di componente. Un project.save() con Embody
   (strip/restore), un TDN reimport, o un copia/incolla ricreano questo
   COMP senza mai passare da un vero riavvio di TD — solo onCreate spara
   in tutti questi casi (verificato su docs.derivative.ca/Execute_DAT).
   onFrameStart e' OBBLIGATORIO: e' l'unico punto in cui gli status
   arrivati dal thread MQTT vengono scritti nella devices_table.
5. Per i bottoni play/stop/restart (Button COMP, List COMP onClick...):
       op('gaia_control/td_service_control').module.send_command(
           device_id, service_name, 'enable')   # o 'disable' / 'restart'
   send_command() e' sicura da chiamare direttamente da un callback UI
   (gira gia' sul thread principale di TD) — nessun marshalling
   necessario li'.

STATI: "active" / "inactive" / "failed" — stessi valori pubblicati dagli
agent Pi/OPS/local_agent, nessuna traduzione. offline=True se il device
non manda status da piu' di OFFLINE_AFTER_S secondi (stesso timeout di
Pi Manager, 90s).

THREAD SAFETY (fix 2026-08-05, stessa classe di bug gia' trovata e
corretta in gaia_device_agent): la versione originale chiamava run()
direttamente da _on_message (thread di rete paho) e da _staleness_loop
(thread separato) per marshalare la scrittura della Table DAT sul thread
principale — SBAGLIATO: "Never call run()/td.run() from a worker - it
raises tdError" (rules/td-python.md). Fix: i due thread worker toccano
SOLO una queue.Queue thread-safe; un Execute DAT onFrameStart (thread
principale, nessun run() necessario) drena la coda e scrive davvero la
Table DAT.

RICREAZIONE SENZA CLEANUP: come gaia_device_agent, onCreate puo' scattare
piu' volte nella stessa sessione (project.save() con strip/restore, TDN
reimport, editing live di questo Text DAT). Il client MQTT precedente e
l'Event di stop del suo staleness-thread vanno tracciati per essere
fermati esplicitamente al prossimo start() — vedi FIX sotto per come.

FIX 2026-08-05 (bug reale trovato dopo il primo fix): quel riferimento
NON va salvato in me.parent().store() — un threading.Event o un client
paho contengono un _thread.lock, non picklabile, e project.save() PROVA a
serializzare tutto lo storage. Verificato dal vivo: "Error saving storage
for operator .../gaia_control: TypeError: cannot pickle '_thread.lock'
object" — ogni salvataggio falliva silenziosamente a persistere quello
storage. Fix reale: un registro Python puro attaccato al modulo sys (mai
reinizializzato da TD, sopravvive al reload di QUESTO modulo, non tocca
mai project.save()), stesso pattern di gaia_device_agent.
"""
import json
import queue
import sys
import threading
import time

try:
    import paho.mqtt.client as mqtt
except ImportError:
    mqtt = None
    print("[GAIA Service Control] paho-mqtt non installato nel Python di TD.")

OFFLINE_AFTER_S = 90
HEARTBEAT_CHECK_S = 10

_client     = None
_running    = False
_stop_event = None
_devices    = {}   # device_id -> {status..., "_last_seen": float}
_lock       = threading.Lock()   # protegge _devices, toccato da piu' thread
_inbox      = queue.Queue()      # worker threads put() qui, drain_inbox() lo svuota sul thread principale

_REGISTRY_ATTR = '_gaia_control_registry'


def _registry():
    # Registro Python puro attaccato al modulo sys -- NON usare
    # me.parent().store(): vedi nota FIX 2026-08-05 in cima al file.
    reg = getattr(sys, _REGISTRY_ATTR, None)
    if reg is None:
        reg = {}
        setattr(sys, _REGISTRY_ATTR, reg)
    return reg


def _read_config():
    # Chiamare SOLO dal thread principale — legge par di TD.
    host = me.parent()

    def par(name, default):
        try:
            v = host.par[name].eval()
            return v if v not in (None, "") else default
        except Exception:
            return default

    return {
        "mqtt_host": par("Mqtthost", "192.168.1.142"),
        "mqtt_port": int(par("Mqttport", 1883) or 1883),
    }


def get_devices():
    """Snapshot corrente device_id -> ultimo payload status ricevuto.
    Sicura da qualunque thread: legge solo _devices sotto lock, zero
    accesso a TD."""
    with _lock:
        return {k: dict(v) for k, v in _devices.items()}


def send_command(device_id, service, action):
    """Chiamala da un Button/List COMP: play='enable', stop='disable',
    restart='restart'. Sicura da un callback UI (thread principale) —
    _client.publish() e' comunque thread-safe lato paho."""
    if _client is None:
        print("[GAIA Service Control] non connesso, comando ignorato")
        return
    _client.publish(
        f"gaia/device/{device_id}/command",
        json.dumps({"action": action, "service": service}),
    )


def _svc_keys(d):
    keys = list((d.get("services") or {}).keys())
    for k in (d.get("config") or {}):
        if k not in keys:
            keys.append(k)
    return keys


def _rebuild_table():
    # Chiamata SOLO da drain_inbox() sul thread principale — mai
    # direttamente dal thread di rete MQTT (scrivere in un Table DAT e'
    # una mutazione TD).
    table = me.parent().op("devices_table")
    if table is None:
        print("[GAIA Service Control] Table DAT 'devices_table' non trovata (vedi setup nel README)")
        return
    table.clear()
    table.appendRow(["device_id", "name", "stanza", "role", "service", "state", "offline"])
    now = time.time()
    with _lock:
        devices = dict(_devices)
    for device_id, d in sorted(devices.items()):
        offline = (now - d.get("_last_seen", 0)) > OFFLINE_AFTER_S
        keys = _svc_keys(d) or [""]
        for svc in keys:
            state = (d.get("services") or {}).get(svc, "unknown")
            table.appendRow([
                device_id, d.get("name") or d.get("stanza") or device_id,
                d.get("stanza", ""), d.get("role", ""), svc, state, str(offline),
            ])


def drain_inbox():
    """Chiamare da Execute DAT onFrameStart, OGNI FRAME — gira sul thread
    principale, e' l'unico punto sicuro in cui gli status arrivati dal
    thread MQTT vengono scritti nella devices_table.

    Ritorna True se devices_table e' stata riscritta in questa chiamata
    (usato da control_lifecycle per pulsare il reset della UI opzionale,
    vedi devices_list_callbacks) — questo modulo resta comunque
    UI-agnostico, si limita a riportare "e' cambiato qualcosa"."""
    rebuild = False
    while True:
        try:
            kind, payload = _inbox.get_nowait()
        except queue.Empty:
            break
        if kind == "status":
            device_id = payload.get("device_id")
            if device_id:
                payload["_last_seen"] = time.time()
                with _lock:
                    _devices[device_id] = payload
                rebuild = True
        elif kind == "bad_status":
            print(f"[GAIA Service Control] Status non valido: {payload}")
        elif kind == "connect":
            if payload == 0:
                print("[GAIA Service Control] Connesso, in ascolto su gaia/device/+/status")
            else:
                print(f"[GAIA Service Control] Connessione MQTT fallita rc={payload}")
        elif kind == "disconnect":
            print(f"[GAIA Service Control] Disconnesso (rc={payload})")
        elif kind == "staleness_tick":
            rebuild = True
    if rebuild:
        _rebuild_table()
    return rebuild


# ---- Callback paho-mqtt: girano sul thread di rete di loop_start(). -------
# ZERO accesso a op()/par/print()/debug()/run() qui: solo _inbox.put() e
# il lock su _devices (pure Python, esplicitamente permessi a un worker).

def _on_message(client, userdata, msg):
    try:
        d = json.loads(msg.payload)
    except Exception as e:
        _inbox.put(("bad_status", str(e)))
        return
    _inbox.put(("status", d))


def _on_connect(client, userdata, flags, reason_code, properties=None):
    # client.subscribe() non tocca TD (e' thread-safe lato paho) -- va
    # richiamato qui ad OGNI connect/riconnessione, non solo alla prima
    # volta in start(), altrimenti una riconnessione dopo un drop di rete
    # perderebbe la subscription. Solo il logging passa dalla coda.
    if reason_code == 0:
        client.subscribe("gaia/device/+/status")
    _inbox.put(("connect", reason_code))


def _on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    # Firma v2 (disconnect_flags, reason_code, properties) — verificata
    # contro il sorgente paho installato, stessa correzione applicata a
    # gaia_device_agent.
    if reason_code != 0:
        _inbox.put(("disconnect", reason_code))


def _staleness_loop(stop_event):
    # threading.Thread indipendente — stesso vincolo sopra: solo _inbox.put().
    while not stop_event.is_set():
        stop_event.wait(HEARTBEAT_CHECK_S)
        if not stop_event.is_set():
            _inbox.put(("staleness_tick", None))


def _stop_previous_instance(host):
    """Ferma un'istanza precedente lasciata orfana da un reload del modulo
    — SEMPRE chiamata da start(), indipendentemente dal motivo per cui il
    modulo si e' reinizializzato (vedi gaia_device_agent per i dettagli)."""
    prev = _registry().pop(host.path, None)
    if prev is None:
        return
    old_client = prev.get('client')
    if old_client is not None:
        try:
            old_client.loop_stop()
            old_client.disconnect()
        except Exception as e:
            print(f"[GAIA Service Control] Errore fermando client precedente: {e}")
    old_event = prev.get('stop_event')
    if old_event is not None:
        old_event.set()


def start():
    global _client, _running, _stop_event
    if mqtt is None:
        return
    if _running:
        return
    host = me.parent()
    _stop_previous_instance(host)
    cfg = _read_config()
    _running    = True
    _stop_event = threading.Event()
    _client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"gaia-td-control-{int(time.time())}")
    _client.on_connect    = _on_connect
    _client.on_disconnect = _on_disconnect
    _client.on_message    = _on_message
    _registry()[host.path] = {'client': _client, 'stop_event': _stop_event}
    _client.connect_async(cfg["mqtt_host"], cfg["mqtt_port"], 60)
    _client.loop_start()
    threading.Thread(target=_staleness_loop, args=(_stop_event,), daemon=True).start()
    print(f"[GAIA Service Control] Avviato ({cfg['mqtt_host']}:{cfg['mqtt_port']})")


def stop():
    global _client, _running
    _running = False
    if _stop_event is not None:
        _stop_event.set()
    if _client:
        _client.loop_stop()
        _client.disconnect()
        _client = None
    _registry().pop(me.parent().path, None)
    print("[GAIA Service Control] Fermato.")
