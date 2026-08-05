"""
GAIA Device Agent — vive DENTRO il progetto TouchDesigner (Text DAT +
Execute DAT), non e' un processo di sistema esterno. Nessun manifest sul
filesystem, nessun path a TouchDesigner.exe: gira ovunque il .toe gira,
configurato con i parametri del componente che lo ospita e salvato nel
progetto stesso — portabile da una macchina all'altra senza toccare nulla
fuori dal .toe (ogni macchina puo' avere TD installato diversamente).

SETUP IN TD
1. Crea un COMP contenitore (es. "gaia_agent"). Customize Component ->
   aggiungi una Custom Page con questi parametri (tutti opzionali, se
   mancanti l'agent usa dei default sensati, vedi _read_config):
     Deviceid  (Str)  es. "td-herbarium"
     Stanza    (Str)  es. "salotto"
     Name      (Str)  es. "AV Herbarium"
     Mqtthost  (Str)  default 192.168.1.142
     Mqttport  (Int)  default 1883
2. Dentro quel COMP: un Text DAT chiamato "gaia_device_agent" con QUESTO
   codice (Embody lo esternalizza come .py — non impostare file/syncfile a
   mano, vedi CLAUDE.md).
3. Un Execute DAT nello stesso COMP:
       def onCreate():
           op('gaia_device_agent').module.start()
           return
       def onFrameStart(frame):
           op('gaia_device_agent').module.drain_inbox()
           return
       def onExit():
           op('gaia_device_agent').module.stop()
           return
   USARE "Create" (onCreate), NON "Start" (onStart) (fix 2026-08-05):
   onStart in TD e' un evento di APPLICAZIONE, fired una sola volta per
   sessione TD — NON quando il componente viene ricreato a runtime
   (verificato su docs.derivative.ca/Execute_DAT). Il salvataggio via
   Embody (strip/restore), un TDN reimport, o un copia/incolla ricreano
   questo COMP senza mai passare da un vero riavvio di TD: solo "Create"
   (onCreate) spara in TUTTI questi casi ("triggered on start, by loading
   a component from disk, by copying & pasting, or any other way a node
   can be created"). onExit invece e' legato alla chiusura del PROCESSO
   TD, non alla cancellazione del singolo componente — quindi non esiste
   un hook TD affidabile per un cleanup "per istanza" quando il COMP
   viene ricreato. start() se ne fa carico da solo, vedi sotto.
   onFrameStart e' OBBLIGATORIO, non opzionale: e' l'unico punto in cui i
   messaggi arrivati dal thread MQTT vengono applicati a TD (vedi sotto).

ESPORRE UN SERVIZIO REALE (facoltativo)
Senza fare nient'altro l'agent compare gia' in Admin (presenza + heartbeat,
"services" vuoto, i comandi restano no-op loggati). Per collegare un
controllo vero (es. "riavvia l'OSC In se si blocca"), da un TUO script di
progetto — questo file resta identico in ogni progetto, non editarlo qui:
    agent = op('gaia_agent/gaia_device_agent').module
    agent.register_service('osc_in',
        start=lambda: setattr(op('oscin1').par, 'active', 1),
        stop=lambda: setattr(op('oscin1').par, 'active', 0),
        status=lambda: bool(op('oscin1').par.active.eval()))
NOTA: start/stop/status vengono sempre invocati da drain_inbox() (thread
principale, via onFrameStart), quindi e' sicuro toccare op()/par dentro di
essi.

Stesso protocollo MQTT degli agent Pi/OPS (pi/agent/agent.py,
ops/agent/agent.py): gaia/device/{id}/status (retained, ogni 30s) +
comandi enable/disable/restart su gaia/device/{id}/command e
gaia/device/all/command.

THREAD SAFETY (riscritto 2026-08-05): i due thread worker (rete paho +
heartbeat) toccano SOLO una queue.Queue thread-safe (operazione
esplicitamente permessa per un worker, zero accesso a op()/par/
print()/debug()/run() — run() da un worker solleva tdError, vedi
rules/td-python.md). Un Execute DAT onFrameStart — che gira gia' sul
thread principale ad ogni frame, nessun run() necessario — chiama
drain_inbox() per svuotare la coda e applicare comandi/eventi a TD.

RICREAZIONE SENZA CLEANUP: onCreate puo' scattare piu' volte nella STESSA
sessione TD (project.save() con Embody fa strip/restore del COMP; anche
editare live questo stesso Text DAT causa un reload). Ogni volta un client
MQTT precedente rischia di restare ORFANO — thread ancora vivo, ancora
connesso con lo STESSO client_id — mentre uno nuovo tenta di connettersi:
il broker li fa litigare, disconnessioni a raffica osservate dal vivo.

FIX 2026-08-05 (bug reale trovato dopo il primo fix): il riferimento al
client/stop-event precedente NON va salvato in me.parent().store() — un
threading.Event o un client paho contengono un _thread.lock, non
picklabile, e project.save() PROVA a serializzare tutto lo storage.
Verificato dal vivo: "Error saving storage for operator .../gaia_agent:
TypeError: cannot pickle '_thread.lock' object" — ogni salvataggio falliva
silenziosamente a persistere quello storage. Fix reale: un registro Python
puro attaccato al modulo sys (mai reinizializzato da TD, sopravvive al
reload di QUESTO modulo, non tocca mai project.save()).
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
    print("[GAIA Agent] paho-mqtt non installato nel Python di TD — "
          "pip install paho-mqtt nell'interprete usato da TouchDesigner.")

_client     = None
_running    = False
_start_ts   = None
_stop_event = None       # threading.Event condiviso col thread di heartbeat corrente
_services   = {}         # name -> {"start": fn, "stop": fn, "status": fn}
_inbox      = queue.Queue()  # worker threads put() qui, drain_inbox() lo svuota sul thread principale

_REGISTRY_ATTR = '_gaia_device_agent_registry'


def _registry():
    # Registro Python puro attaccato al modulo sys -- NON usare
    # me.parent().store(): vedi nota FIX 2026-08-05 in cima al file.
    reg = getattr(sys, _REGISTRY_ATTR, None)
    if reg is None:
        reg = {}
        setattr(sys, _REGISTRY_ATTR, reg)
    return reg


def register_service(name, start=None, stop=None, status=None):
    """Chiamalo dal tuo script di progetto per esporre un controllo reale.
    status() deve restituire True/False (o None se sconosciuto). Le tre
    funzioni sono sempre chiamate da drain_inbox() sul thread principale —
    possono toccare op()/par liberamente."""
    _services[name] = {"start": start, "stop": stop, "status": status}


def _read_config():
    # Chiamare SOLO dal thread principale (drain_inbox/start/stop) — legge par di TD.
    host = me.parent()

    def par(name, default):
        try:
            v = host.par[name].eval()
            return v if v not in (None, "") else default
        except Exception:
            return default

    return {
        "device_id": par("Deviceid", f"td-{project.name}"),
        "stanza":    par("Stanza", "unknown"),
        "name":      par("Name", project.name),
        "mqtt_host": par("Mqtthost", "192.168.1.142"),
        "mqtt_port": int(par("Mqttport", 1883) or 1883),
    }


def _service_status(name):
    # Chiamare SOLO dal thread principale — invoca i callback registrati,
    # che tipicamente toccano op()/par.
    fn = _services.get(name, {}).get("status")
    if not fn:
        return "unknown"
    try:
        return "active" if fn() else "inactive"
    except Exception as e:
        print(f"[GAIA Agent] status({name}) errore: {e}")
        return "unknown"


def _publish_status():
    # Chiamare SOLO dal thread principale (legge config/servizi TD).
    if _client is None:
        return
    cfg = _read_config()
    payload = {
        "device_id": cfg["device_id"],
        "name":      cfg["name"],
        "stanza":    cfg["stanza"],
        "role":      "touchdesigner",
        "services":  {n: _service_status(n) for n in _services},
        "uptime":    int(time.time() - _start_ts) if _start_ts else 0,
        "ts":        int(time.time() * 1000),
    }
    _client.publish(f"gaia/device/{cfg['device_id']}/status", json.dumps(payload), retain=True)


def _apply_command(cmd):
    # Chiamata SOLO da drain_inbox() sul thread principale — qui e' sicuro
    # toccare op()/par, mai direttamente dal thread di rete di paho-mqtt.
    action  = cmd.get("action", "")
    service = cmd.get("service", "")
    svc = _services.get(service)
    print(f"[GAIA Agent] Comando: {cmd}")

    if action in ("enable", "disable", "restart") and not svc:
        print(f"[GAIA Agent] Servizio '{service}' non registrato (register_service mai chiamato)")
    elif action == "enable" and svc.get("start"):
        svc["start"]()
    elif action == "disable" and svc.get("stop"):
        svc["stop"]()
    elif action == "restart" and svc:
        if svc.get("stop"):
            svc["stop"]()
        if svc.get("start"):
            svc["start"]()
    elif action == "status":
        pass
    else:
        print(f"[GAIA Agent] Azione ignorata: {action}")

    _publish_status()


def drain_inbox():
    """Chiamare da Execute DAT onFrameStart, OGNI FRAME — gira sul thread
    principale, e' l'unico punto sicuro in cui gli eventi arrivati dai
    thread worker (rete MQTT, heartbeat) toccano davvero TD."""
    while True:
        try:
            kind, payload = _inbox.get_nowait()
        except queue.Empty:
            break
        if kind == "connect":
            cfg = _read_config()
            if payload == 0:
                _client.subscribe(f"gaia/device/{cfg['device_id']}/command")
                _client.subscribe("gaia/device/all/command")
                print(f"[GAIA Agent] Connesso — device_id: {cfg['device_id']}")
                _publish_status()
            else:
                print(f"[GAIA Agent] Connessione MQTT fallita rc={payload}")
        elif kind == "disconnect":
            print(f"[GAIA Agent] Disconnesso (rc={payload})")
        elif kind == "bad_message":
            print(f"[GAIA Agent] Comando non valido: {payload}")
        elif kind == "command":
            _apply_command(payload)
        elif kind == "heartbeat":
            try:
                _publish_status()
            except Exception as e:
                print(f"[GAIA Agent] Errore heartbeat: {e}")


# ---- Callback paho-mqtt: girano sul thread di rete di loop_start(). -------
# ZERO accesso a op()/par/print()/debug()/run() qui: solo _inbox.put(),
# l'unica operazione esplicitamente sicura da un worker thread.

def _on_message(client, userdata, msg):
    try:
        cmd = json.loads(msg.payload)
    except Exception as e:
        _inbox.put(("bad_message", str(e)))
        return
    _inbox.put(("command", cmd))


def _on_connect(client, userdata, flags, reason_code, properties=None):
    _inbox.put(("connect", reason_code))


def _on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    # Firma v2 verificata contro il sorgente paho installato: 5 posizionali
    # (disconnect_flags, non solo reason_code) — una firma a 4 argomenti
    # lancia TypeError ad ogni disconnessione reale, impedendo la
    # riconnessione automatica di paho.
    if reason_code != 0:
        _inbox.put(("disconnect", reason_code))


def _heartbeat_loop(stop_event):
    # threading.Thread indipendente — stesso vincolo sopra: solo _inbox.put().
    while not stop_event.is_set():
        _inbox.put(("heartbeat", None))
        stop_event.wait(30)


def _stop_previous_instance(host):
    """Ferma un'istanza precedente lasciata orfana da un reload del modulo
    (project.save() con strip/restore, TDN reimport, copia/incolla, o un
    editing live di questo stesso Text DAT) — SEMPRE chiamata da start(),
    indipendentemente dal motivo per cui il modulo si e' reinizializzato."""
    prev = _registry().pop(host.path, None)
    if prev is None:
        return
    old_client = prev.get('client')
    if old_client is not None:
        try:
            old_client.loop_stop()
            old_client.disconnect()
        except Exception as e:
            print(f"[GAIA Agent] Errore fermando client precedente: {e}")
    old_event = prev.get('stop_event')
    if old_event is not None:
        old_event.set()


def start():
    global _client, _running, _start_ts, _stop_event
    if mqtt is None:
        return
    if _running:
        # Stessa istanza di modulo, gia' avviata — no-op, NON tocca
        # _stop_previous_instance (altrimenti fermerebbe il proprio client
        # corrente, ancora valido, invece di uno davvero orfano).
        return
    host = me.parent()
    _stop_previous_instance(host)
    cfg = _read_config()
    _running    = True
    _start_ts   = time.time()
    _stop_event = threading.Event()
    _client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"gaia-td-{cfg['device_id']}")
    _client.on_connect    = _on_connect
    _client.on_disconnect = _on_disconnect
    _client.on_message    = _on_message
    _registry()[host.path] = {'client': _client, 'stop_event': _stop_event}
    _client.connect_async(cfg["mqtt_host"], cfg["mqtt_port"], 60)
    _client.loop_start()
    threading.Thread(target=_heartbeat_loop, args=(_stop_event,), daemon=True).start()
    print(f"[GAIA Agent] Avviato ({cfg['device_id']} @ {cfg['mqtt_host']}:{cfg['mqtt_port']})")


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
    print("[GAIA Agent] Fermato.")
