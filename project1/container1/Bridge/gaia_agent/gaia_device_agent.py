"""
GAIA Device Agent — vive DENTRO il progetto TouchDesigner (Text DAT +
Execute DAT + un mqttclientDAT nativo), non e' un processo di sistema
esterno. Nessun manifest sul filesystem, nessun path a TouchDesigner.exe:
gira ovunque il .toe gira, configurato con i parametri del componente che
lo ospita e salvato nel progetto stesso — portabile da una macchina
all'altra senza toccare nulla fuori dal .toe.

RISCRITTO 2026-08-05 (v2): la v1 usava paho.mqtt.client + thread Python
(queue.Queue, un registro su sys, un thread di heartbeat separato) perche'
il Python embedded di TD non ha pip. Quel disegno funzionava SOLO perche'
Envoy, quando parte, aggiunge il proprio venv a sys.path di TD
(EmbodyExt._setupEnvironment) — su una macchina "solo spettacolo" senza
Envoy mai avviato, l'import falliva silenziosamente. Il progetto ha gia'
un mqttclientDAT NATIVO (vedi Bridge/mqtt_bridge/mqtt_gaia, il firehose di
debug) — zero pacchetti esterni, zero sys.path, callback che girano gia'
sul thread principale di TD. Questa v2 usa lo stesso operatore nativo:
elimina la dipendenza da paho E tutta la macchina di thread-safety (non
serve piu': non esiste un client Python vivo da tracciare/fermare tra un
project.save() e l'altro, l'oggetto "client" e' l'operatore mqttclientDAT
stesso, gestito da TD come qualunque altro DAT esternalizzato).

SETUP IN TD
1. COMP contenitore ("gaia_agent"), Custom Page con:
     Deviceid  (Str)  default derivato dall'hostname macchina (espressione)
     Stanza    (Str)  es. "salotto"
     Name      (Str)  es. "AV Herbarium"
     Mqtthost  (Str)  espressione verso gaia_config
     Mqttport  (Int)  espressione verso gaia_config
2. Un mqttclientDAT "mqtt_agent" nello stesso COMP, Network Address =
   espressione 'tcp://%s:%d' % (Mqtthost, Mqttport), Active=1. La sua
   Callbacks DAT ("mqtt_agent_callbacks") delega qui (vedi in fondo).
3. Text DAT "gaia_device_agent" con QUESTO file come sorgente esterna.
4. Execute DAT "agent_lifecycle" nello stesso COMP:
       def onFrameStart(frame):
           op('gaia_device_agent').module.tick()
           return
   Un SOLO hook necessario: tick() e' un heartbeat throttlato via
   time.time() (stesso pattern di camera_resolver.py), NON serve piu'
   onCreate/onExit — il mqttclientDAT si connette da solo (Active=1 +
   Network Address validi) ogni volta che l'operatore e' vivo, incluso
   dopo un TDN reimport o uno strip/restore di Embody.

ESPORRE UN SERVIZIO REALE (facoltativo)
Senza fare nient'altro l'agent compare gia' in Admin (presenza + heartbeat,
"services" vuoto, i comandi restano no-op loggati). Per collegare un
controllo vero, da un TUO script di progetto — questo file resta identico
in ogni progetto, non editarlo qui:
    agent = op('gaia_agent/gaia_device_agent').module
    agent.register_service('osc_in',
        start=lambda: setattr(op('oscin1').par, 'active', 1),
        stop=lambda: setattr(op('oscin1').par, 'active', 0),
        status=lambda: bool(op('oscin1').par.active.eval()))
NOTA: start/stop/status vengono sempre invocati da on_message() (gia' sul
thread principale, dispatch nativo del Callbacks DAT), quindi e' sicuro
toccare op()/par dentro di essi.

Stesso protocollo MQTT degli agent Pi/OPS (pi/agent/agent.py,
ops/agent/agent.py): gaia/device/{id}/status (retained, ogni 30s) +
comandi enable/disable/restart su gaia/device/{id}/command e
gaia/device/all/command.
"""
import json
import time

_START_TS = time.time()
_services = {}   # name -> {"start": fn, "stop": fn, "status": fn}

_HEARTBEAT_S = 30
_last_heartbeat = 0.0


def register_service(name, start=None, stop=None, status=None):
    """Chiamalo dal tuo script di progetto per esporre un controllo reale.
    status() deve restituire True/False (o None se sconosciuto). Le tre
    funzioni sono sempre chiamate da on_message()/tick() sul thread
    principale — possono toccare op()/par liberamente."""
    _services[name] = {"start": start, "stop": stop, "status": status}


def _mqtt():
    return me.parent().op('mqtt_agent')


def _read_config():
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
    }


def _service_status(name):
    fn = _services.get(name, {}).get("status")
    if not fn:
        return "unknown"
    try:
        return "active" if fn() else "inactive"
    except Exception as e:
        print(f"[GAIA Agent] status({name}) errore: {e}")
        return "unknown"


def _publish_status():
    dat = _mqtt()
    if dat is None or not dat.isConnected:
        return
    cfg = _read_config()
    payload = {
        "device_id": cfg["device_id"],
        "name":      cfg["name"],
        "stanza":    cfg["stanza"],
        "role":      "touchdesigner",
        "services":  {n: _service_status(n) for n in _services},
        "uptime":    int(time.time() - _START_TS),
        "ts":        int(time.time() * 1000),
    }
    dat.publish(f"gaia/device/{cfg['device_id']}/status", json.dumps(payload).encode('utf-8'), retain=True)


def _apply_command(cmd):
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


def tick():
    """Chiamare da Execute DAT onFrameStart, OGNI FRAME — heartbeat
    throttlato internamente a _HEARTBEAT_S (stesso pattern di
    camera_resolver.py), nessun thread separato necessario."""
    global _last_heartbeat
    now = time.time()
    if (now - _last_heartbeat) < _HEARTBEAT_S:
        return
    _last_heartbeat = now
    _publish_status()


# ---- Chiamate da mqtt_agent_callbacks — girano gia' sul thread principale
# (dispatch nativo del Callbacks DAT, verificato su mqtt_bridge/mqtt_gaia). --

def on_connect(dat):
    cfg = _read_config()
    dat.subscribe(f"gaia/device/{cfg['device_id']}/command")
    dat.subscribe("gaia/device/all/command")
    print(f"[GAIA Agent] Connesso — device_id: {cfg['device_id']}")
    _publish_status()


def on_connect_failure(msg):
    print(f"[GAIA Agent] Connessione MQTT fallita: {msg}")


def on_connection_lost(msg):
    print(f"[GAIA Agent] Disconnesso: {msg}")


def on_message(topic, payload):
    if isinstance(payload, bytes):
        payload = payload.decode('utf-8', errors='replace')
    try:
        cmd = json.loads(payload)
    except Exception as e:
        print(f"[GAIA Agent] Comando non valido: {e}")
        return
    _apply_command(cmd)
