"""
GAIA Nursery — attiva/disattiva componenti visivi pre-costruiti in Visuals
in risposta a decisioni prese lato Gaia (Node-RED + Ollama), via MQTT
(canale 9: gaia/nursery/activate|deactivate|status). Vedi ARCHITECTURE.md
§7 e GAIA_INTERFACE.md "Canale 9" per il design completo.

Stesso pattern nativo di gaia_control/gaia_agent (mqttclientDAT, zero
thread, zero pacchetti esterni) -- vedi td_service_control.py per il
precedente completo.

WHITELIST: ogni activate viene validato contro nursery_library
(File In DAT che legge nursery_components.json alla radice del repo,
STESSO filesystem di questo progetto TD -- non una copia trascritta a
mano). Un component_id non presente nella libreria, o senza un
operatore corrispondente in Visuals, non attiva NULLA -- mai un
default silenzioso, stesso principio del whitelist hard concordato in
GAIA_INTERFACE.md.

BROADCAST + FILTRO LOCALE: gaia/nursery/activate arriva a TUTTE le
istanze TD (stesso pattern del canale 7 mocap opt-in) -- ogni istanza
confronta il campo "room" del messaggio con il proprio
Bridge/gaia_client.par.Stanza e ignora l'evento se non combacia (room
nullo = reagisce comunque, es. un evento non legato a una stanza).

CICLO DI VITA: TTL di sicurezza (default 5 minuti, da ttl_ms nel
messaggio) sweepato da tick() -- mai un componente attivo per sempre.
deactivate esplicito (stesso instance_id) lo chiude prima se arriva.

REFERENCE COUNTING: piu' instance_id possono puntare allo STESSO
componente (es. person_recognized ripetuto per la stessa persona, un
instance_id nuovo ogni volta) -- _deactivate() nasconde l'operatore
solo quando NESSUN altro instance_id attivo lo reclama ancora, altrimenti
il TTL/deactivate del piu' vecchio farebbe sparire un componente che
un'istanza piu' recente considera ancora valido (trovato dal vivo
2026-09-04, 9 instance_id impilati su un solo person_sigil).
"""
import json
import time

_active = {}   # instance_id -> {"component","room","person","activated_ts","ttl_ms"}

_TTL_SWEEP_S = 1.0
_last_sweep = 0.0


def _mqtt():
    return me.parent().op('mqtt_nursery')


def _library():
    """dict component_id -> spec, letto fresco da nursery_components.json
    (File In DAT, stesso filesystem del repo) ad ogni chiamata -- file
    piccolo, costo trascurabile, e cosi' un aggiornamento del file si
    riflette senza dover riavviare TD."""
    dat = me.parent().op('nursery_library')
    if dat is None:
        return {}
    obj = dat.jsonObject
    if not obj:
        return {}
    return {c['id']: c for c in obj.get('components', [])}


def _visuals():
    return me.parent().parent().parent().op('Visuals')


def _myRoom():
    agent = me.parent().parent().op('gaia_client')
    if agent is None:
        return 'unknown'
    return agent.par.Stanza.eval()


def _targetOp(component_id):
    visuals = _visuals()
    if visuals is None:
        return None
    return visuals.op(component_id)


def _applyParams(target, spec, params):
    """Applica i params dell'activation sui custom par del componente,
    con default dallo schema per ogni chiave mancante. Nome par = prima
    lettera maiuscola (convenzione TD custom par), stesso valore per
    Menu (stringa, assegnazione per nome) e Float (numero)."""
    for key, pschema in (spec.get('params_schema') or {}).items():
        value = params.get(key, pschema.get('default'))
        if value is None:
            continue
        parname = key[0].upper() + key[1:]
        par = getattr(target.par, parname, None)
        if par is None:
            print(f"[GAIA Nursery] {spec['id']}: par '{parname}' non trovato, ignorato")
            continue
        par.val = value


def _publishStatus():
    dat = _mqtt()
    if dat is None or not dat.isConnected:
        return
    active_list = [
        {
            "instance_id": iid,
            "component": e["component"],
            "room": e["room"],
            "person": e["person"],
            "activated_ts": int(e["activated_ts"] * 1000),
        }
        for iid, e in _active.items()
    ]
    dat.publish("gaia/nursery/status", json.dumps({"active": active_list}).encode('utf-8'), retain=True)


def _activate(msg):
    instance_id = msg.get('instance_id')
    component_id = msg.get('component')
    if not instance_id or not component_id:
        print(f"[GAIA Nursery] activate senza instance_id/component, ignorato: {msg}")
        return

    spec = _library().get(component_id)
    if spec is None:
        print(f"[GAIA Nursery] component '{component_id}' non in nursery_components.json, NESSUNA attivazione")
        return

    room = msg.get('room')
    if room and room != _myRoom():
        # Broadcast a tutte le istanze -- questa non e' la stanza giusta, ignora silenziosamente
        # (non un errore: e' il comportamento atteso per le altre istanze).
        return

    target = _targetOp(component_id)
    if target is None:
        print(f"[GAIA Nursery] component '{component_id}' in libreria ma nessun operatore Visuals/{component_id}, NESSUNA attivazione")
        return

    _applyParams(target, spec, msg.get('params') or {})
    target.display = True
    target.render = True

    _active[instance_id] = {
        "component": component_id,
        "room": room,
        "person": msg.get('person'),
        "activated_ts": time.time(),
        "ttl_ms": msg.get('ttl_ms', 300000),
    }
    print(f"[GAIA Nursery] Attivato {component_id} (instance_id={instance_id})")
    _publishStatus()


def _deactivate(instance_id):
    entry = _active.pop(instance_id, None)
    if entry is None:
        return
    component_id = entry['component']
    # Reference-count the shared target op: multiple instance_ids (e.g.
    # repeated person_recognized for the same person) can point at the
    # SAME Visuals/{component_id} operator. Only hide it once no other
    # active instance still claims it -- otherwise the oldest instance's
    # TTL/deactivate would blink the component off under a still-active one.
    still_claimed = any(e['component'] == component_id for e in _active.values())
    if not still_claimed:
        target = _targetOp(component_id)
        if target is not None:
            target.display = False
            target.render = False
    print(f"[GAIA Nursery] Disattivato {component_id} (instance_id={instance_id})" +
          (" -- componente resta visibile, altre istanze attive" if still_claimed else ""))
    _publishStatus()


def _sweepTTL():
    now = time.time()
    for instance_id, entry in list(_active.items()):
        if (now - entry['activated_ts']) * 1000.0 > entry['ttl_ms']:
            print(f"[GAIA Nursery] TTL scaduto per instance_id={instance_id}")
            _deactivate(instance_id)


def tick():
    """Chiamare da Execute DAT onFrameStart, OGNI FRAME -- sweep TTL
    throttlato internamente a _TTL_SWEEP_S (stesso pattern throttlato di
    camera_resolver.py/gaia_device_agent.py)."""
    global _last_sweep
    now = time.time()
    if (now - _last_sweep) < _TTL_SWEEP_S:
        return
    _last_sweep = now
    _sweepTTL()


# ---- Chiamate da mqtt_nursery_callbacks -- girano gia' sul thread
# principale (dispatch nativo del Callbacks DAT). ------------------------

def on_connect(dat):
    dat.subscribe("gaia/nursery/activate")
    dat.subscribe("gaia/nursery/deactivate")
    print(f"[GAIA Nursery] Connesso, in ascolto su gaia/nursery/activate|deactivate (stanza={_myRoom()})")
    _publishStatus()


def on_connect_failure(msg):
    print(f"[GAIA Nursery] Connessione MQTT fallita: {msg}")


def on_connection_lost(msg):
    print(f"[GAIA Nursery] Disconnesso: {msg}")


def on_message(topic, payload):
    if isinstance(payload, bytes):
        payload = payload.decode('utf-8', errors='replace')
    try:
        d = json.loads(payload)
    except Exception as e:
        print(f"[GAIA Nursery] Messaggio non valido: {e}")
        return
    if topic.endswith('/activate'):
        _activate(d)
    elif topic.endswith('/deactivate'):
        instance_id = d.get('instance_id')
        if instance_id:
            _deactivate(instance_id)
