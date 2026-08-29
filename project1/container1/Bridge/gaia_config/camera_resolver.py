"""
Camera URL Auto-Resolution — deriva l'URL di streaming di ogni camera
dal registro device MQTT (Bridge/gaia_control/td_service_control),
invece di un IP hardcoded per stanza. Chiude l'ultimo buco di
portabilita' individuato dall'utente ("osc mqtt camera") dopo mqtt
host/port e OSC/Ollama/web host (vedi gaia_config).

PERCHE': gaia_control gia' riceve, per ogni device connesso, "stanza"
(es. "salotto") e "ip" (es. "192.168.1.142") dentro gaia/device/{id}/status
(vedi get_devices()). Le videostreaminTOP cam_salotto/cam_ingresso/
cam_soggiorno in Visuals hanno oggi un url costante
"http://<ip fisso>:8766/video" — su un'altra rete quell'IP non esiste
piu'. Qui deriviamo l'url a runtime cercando, tra i device connessi,
quello con stanza == nome-stanza e capabilities.camera == True.

Chiamare resolve() da un Execute DAT onFrameStart (gia' throttlato
internamente, non serve un contatore esterno) — sola lettura di
get_devices() (thread-safe, nessun accesso TD dal lato gaia_control) +
scrittura url/reloadpulse SOLO se il valore risolto e' cambiato
davvero, per non pulsare reload in continuazione.
"""
import time

# stanza (come pubblicata in gaia/device/*/status) -> nome della
# videostreaminTOP in Visuals che deve mostrarla.
#
# NOTA 2026-08-06: inizialmente "corretto" per errore a "studio",
# ipotizzando che td-silvermini2 (stanza "studio") fosse lo stesso
# device di ops-silvermini2 (la camera). Chiarito da Gaia/Core in
# GAIA_INTERFACE.md: sono due device_id DISTINTI sulla stessa macchina
# fisica OPS -- ops-silvermini2 (mediapipe/camera, protocollo
# Pi-Manager) resta "soggiorno", td-silvermini2 (un agent TD separato
# sulla stessa macchina) e' "studio". Ripristinato "soggiorno" qui,
# che e' quello giusto per _find_camera_ip.
_ROOM_TO_CAM = {
    "salotto": "cam_salotto",
    "ingresso": "cam_ingresso",
    "soggiorno": "cam_soggiorno",
}

_CAM_PORT = 8766
_CHECK_EVERY_S = 2.0   # i device pubblicano status ogni ~30s, non serve controllare ogni frame

_last_check = 0.0
_last_urls = {}   # nome cam -> ultimo url applicato, per pulsare reload solo sul cambiamento


def _find_camera_ip(devices, stanza):
    for d in devices.values():
        if d.get("stanza") != stanza:
            continue
        caps = d.get("capabilities") or {}
        if caps.get("camera") and d.get("ip"):
            return d["ip"]
    return None


def resolve():
    """Richiamare ogni frame da onFrameStart — internamente throttlato
    a _CHECK_EVERY_S, quindi il costo reale e' un semplice confronto di
    tempo per la stragrande maggioranza delle chiamate."""
    global _last_check
    now = time.time()
    if (now - _last_check) < _CHECK_EVERY_S:
        return
    _last_check = now

    control = me.parent().op("../gaia_control/td_service_control")
    if control is None:
        return
    devices = control.module.get_devices()

    visuals = me.parent().op("../../Visuals")
    if visuals is None:
        return

    for stanza, cam_name in _ROOM_TO_CAM.items():
        cam = visuals.op(cam_name)
        if cam is None:
            continue
        ip = _find_camera_ip(devices, stanza)
        if not ip:
            continue
        new_url = f"http://{ip}:{_CAM_PORT}/video"
        if _last_urls.get(cam_name) == new_url:
            continue
        cam.par.url.val = new_url
        cam.par.reloadpulse.pulse()
        _last_urls[cam_name] = new_url
        print(f"[GAIA Camera Resolver] {cam_name} -> {new_url}")
