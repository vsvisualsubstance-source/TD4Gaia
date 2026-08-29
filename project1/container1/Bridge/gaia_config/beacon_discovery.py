"""
Auto-discovery di Core (broker MQTT + target OSC canale 3) via gaia_beacon
(UDP 8899, protocollo in docs/discovery-protocol.md del repo gaia -- vedi
GAIA_INTERFACE.md 2026-08-08 "migrazione Node-RED su OPS + richiesta
auto-config").

Cosa copre: SOLO Brokerhost e Corehost -- entrambi puntano oggi alla
stessa macchina fisica (Core, mosquitto:1883 + osc_bridge.py, entrambi
confermati fissi li' anche dopo la migrazione di Node-RED su OPS), che e'
esattamente cio' che il beacon risponde (mqtt_host). Fallback: se il
beacon non risponde, i due parametri restano al valore fisso impostato a
mano -- nessuna sovrascrittura finche' non arriva una risposta valida.

Cosa NON copre: l'host Web/Node-RED (oggi OPS, puo' spostarsi di nuovo).
Il protocollo beacon espone solo mqtt_host/mqtt_port/admin_port di
"gaia-core" -- non ha un campo per "dove gira Node-RED oggi", quindi
quell'host resta un parametro manuale finche' un componente TD reale non
lo consuma davvero (oggi nessuno lo fa).
"""
import json
import time

_PROBE_INTERVAL_S = 30.0
_last_probe = 0.0

# beacon_probe e' in formato 'One Per Byte' (Row/Callback Format) --
# UDP e' a datagrammi, ma la DAT tratta i byte in arrivo come un flusso
# continuo: senza terminatore esplicito (la risposta JSON del beacon non
# ne ha uno, e non e' modificabile da qui, e' un contratto esterno)
# 'One Per Message'/'One Per Line' non chiudono mai una riga -- i byte
# restano accumulati senza mai far scattare onReceive con un messaggio
# completo (visto dal vivo: 5 risposte concatenate nella stessa riga,
# zero trigger). Bufferizza byte per byte e prova il parse JSON ad ogni
# arrivo: un dizionario valido chiude il messaggio, altrimenti continua.
_rx_buffer = ''
_RX_BUFFER_MAX = 4096  # guardia contro un buffer che non chiude mai


def resolve():
	"""Richiamare ogni frame da onFrameStart -- throttlato internamente,
	riprova per sempre ogni _PROBE_INTERVAL_S (self-healing se Core cambia
	IP mentre TD e' gia' avviata, costo trascurabile: un pacchetto UDP
	minuscolo ogni 30s)."""
	global _last_probe
	now = time.time()
	if (now - _last_probe) < _PROBE_INTERVAL_S:
		return
	_last_probe = now
	_send_probe()


def _send_probe():
	probe = op('beacon_probe')
	if probe is None:
		return
	probe.send('GAIA_DISCOVER')


def onReceive(dat, rowIndex, message, bytes, peer):
	"""Callback della UDP Out DAT (beacon_probe), un byte alla volta --
	vedi nota sopra _rx_buffer sul perche' non e' un messaggio completo."""
	global _rx_buffer
	_rx_buffer += message
	if len(_rx_buffer) > _RX_BUFFER_MAX:
		_rx_buffer = ''
		return
	try:
		reply = json.loads(_rx_buffer)
	except (ValueError, TypeError):
		return  # non ancora un JSON completo, aspetta altri byte
	_rx_buffer = ''
	_apply_reply(dat.parent(), reply)


def _apply_reply(cfg, reply):
	if reply.get('service') != 'gaia-core':
		return
	host = reply.get('mqtt_host')
	if not host:
		return

	changed = []
	if cfg.par.Brokerhost.eval() != host:
		cfg.par.Brokerhost.val = host
		changed.append('Brokerhost')
	if cfg.par.Corehost.eval() != host:
		cfg.par.Corehost.val = host
		changed.append('Corehost')

	stamp = time.strftime('%H:%M:%S')
	cfg.par.Beaconstatus.val = 'auto: %s (beacon @ %s, %s)' % (
		host, reply.get('hostname', '?'), stamp)
	if changed:
		print('[GAIA Beacon] aggiornati %s -> %s' % (', '.join(changed), host))
	return
