"""
GAIA Service Control — play/stop/restart dei servizi base dei device
(Pi, OPS, Core) nativamente dentro TouchDesigner. Stesso ruolo di Pi
Manager in web/admin.html, stesso protocollo MQTT, ma qui TD e' il
CONTROLLORE: ascolta gli status di TUTTI i device (gaia/device/+/status)
e puo' inviare comandi enable/disable/restart a ciascuno.

Complementare a gaia_device_agent (che invece fa comparire QUESTA istanza
TD come UN device controllabile) — i due coesistono nello stesso progetto
senza conflitti, sono moduli indipendenti.

RISCRITTO 2026-08-05 (v2): la v1 usava paho.mqtt.client + due thread
Python (queue.Queue, un registro su sys, un thread di staleness) perche'
il Python embedded di TD non ha pip. Quel disegno funzionava SOLO perche'
Envoy, quando parte, aggiunge il proprio venv a sys.path di TD — su una
macchina "solo spettacolo" senza Envoy mai avviato, l'import falliva
silenziosamente. Il progetto ha gia' un mqttclientDAT NATIVO (vedi
Bridge/mqtt_bridge/mqtt_gaia, il firehose di debug): zero pacchetti
esterni, zero sys.path, callback che girano gia' sul thread principale di
TD. Questa v2 usa lo stesso operatore nativo: elimina paho E tutta la
macchina di thread-safety (non serve piu' un client Python vivo da
tracciare/fermare tra un project.save() e l'altro — il "client" e'
l'operatore mqttclientDAT stesso, gestito da TD come qualunque altro DAT
esternalizzato; niente da fermare esplicitamente, niente orfani).

SETUP IN TD
1. COMP contenitore ("gaia_control"), Custom Page con Mqtthost/Mqttport
   (espressione verso gaia_config).
2. Un mqttclientDAT "mqtt_control" nello stesso COMP, Network Address =
   espressione 'tcp://%s:%d' % (Mqtthost, Mqttport), Active=1. La sua
   Callbacks DAT ("mqtt_control_callbacks") delega qui.
3. Un Table DAT vuoto "devices_table" nello stesso COMP — questo script
   lo riscrive ogni volta che arriva uno status (una riga per coppia
   device+servizio: device_id, name, stanza, role, service, state,
   offline). Bind diretto per un List COMP.
4. Text DAT "td_service_control" con QUESTO file come sorgente esterna.
5. Execute DAT "control_lifecycle" nello stesso COMP:
       def onFrameStart(frame):
           changed = op('td_service_control').module.tick()
           if changed:
               lst = op('ui_panel/devices_list')
               if lst is not None:
                   lst.par.reset.pulse()
           return
   tick() ricalcola periodicamente il flag "offline" (i device non
   pubblicano ad ogni frame) — stesso pattern throttlato di
   camera_resolver.py, nessun thread separato.
6. Per i bottoni play/stop/restart (Button COMP, List COMP onClick...):
       op('gaia_control/td_service_control').module.send_command(
           device_id, service_name, 'enable')   # o 'disable' / 'restart'
   send_command() e' sicura da chiamare direttamente da un callback UI
   (gira gia' sul thread principale di TD).

STATI: "active" / "inactive" / "failed" — stessi valori pubblicati dagli
agent Pi/OPS/local_agent, nessuna traduzione. offline=True se il device
non manda status da piu' di OFFLINE_AFTER_S secondi (stesso timeout di
Pi Manager, 90s).
"""
import json
import time

OFFLINE_AFTER_S = 90
STALENESS_CHECK_S = 10

_devices = {}   # device_id -> {status..., "_last_seen": float}
_last_staleness_check = 0.0
_dirty = False   # set True by _rebuild_table(), cleared+reported by tick()


def _mqtt():
    return me.parent().op('mqtt_control')


def get_devices():
    """Snapshot corrente device_id -> ultimo payload status ricevuto."""
    return {k: dict(v) for k, v in _devices.items()}


def send_command(device_id, service, action):
    """Chiamala da un Button/List COMP: play='enable', stop='disable',
    restart='restart'. Sicura da un callback UI (thread principale)."""
    dat = _mqtt()
    if dat is None or not dat.isConnected:
        print("[GAIA Service Control] non connesso, comando ignorato")
        return
    dat.publish(
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
    global _dirty
    table = me.parent().op("devices_table")
    if table is None:
        print("[GAIA Service Control] Table DAT 'devices_table' non trovata (vedi setup nel README)")
        return
    _dirty = True
    table.clear()
    table.appendRow(["device_id", "name", "stanza", "role", "service", "state", "offline"])
    now = time.time()
    for device_id, d in sorted(_devices.items()):
        offline = (now - d.get("_last_seen", 0)) > OFFLINE_AFTER_S
        keys = _svc_keys(d) or [""]
        for svc in keys:
            state = (d.get("services") or {}).get(svc, "unknown")
            table.appendRow([
                device_id, d.get("name") or d.get("stanza") or device_id,
                d.get("stanza", ""), d.get("role", ""), svc, state, str(offline),
            ])


def tick():
    """Chiamare da Execute DAT onFrameStart, OGNI FRAME — ricalcola il
    flag 'offline' ogni STALENESS_CHECK_S secondi (i device non
    pubblicano ad ogni frame, ma un device sparito deve comunque
    apparire offline entro OFFLINE_AFTER_S) E riporta se devices_table e'
    stata riscritta in QUESTO frame, sia dallo staleness check qui sotto
    sia da un on_message() arrivato nel frattempo (_dirty e' condiviso),
    cosi' control_lifecycle sa quando pulsare il reset della UI."""
    global _last_staleness_check, _dirty
    now = time.time()
    if (now - _last_staleness_check) >= STALENESS_CHECK_S:
        _last_staleness_check = now
        _rebuild_table()
    changed, _dirty = _dirty, False
    return changed


# ---- Chiamate da mqtt_control_callbacks — girano gia' sul thread
# principale (dispatch nativo del Callbacks DAT). --------------------------

def on_connect(dat):
    dat.subscribe("gaia/device/+/status")
    print(f"[GAIA Service Control] Connesso, in ascolto su gaia/device/+/status")


def on_connect_failure(msg):
    print(f"[GAIA Service Control] Connessione MQTT fallita: {msg}")


def on_connection_lost(msg):
    print(f"[GAIA Service Control] Disconnesso: {msg}")


def on_message(topic, payload):
    if isinstance(payload, bytes):
        payload = payload.decode('utf-8', errors='replace')
    try:
        d = json.loads(payload)
    except Exception as e:
        print(f"[GAIA Service Control] Status non valido: {e}")
        return
    device_id = d.get("device_id")
    if not device_id:
        return
    d["_last_seen"] = time.time()
    _devices[device_id] = d
    _rebuild_table()
