"""
MQTT Client DAT Callbacks — delega tutta la logica a gaia_nursery_control.py
(sorgente di verita' condivisa). Le funzioni qui girano gia' sul thread
principale (dispatch nativo del Callbacks DAT), quindi e' sicuro toccare
op()/par direttamente.

me - this DAT
"""

def onConnect(dat: mqttclientDAT):
	op('gaia_nursery_control').module.on_connect(dat)
	return

def onConnectFailure(dat: mqttclientDAT, msg: str):
	op('gaia_nursery_control').module.on_connect_failure(msg)
	return

def onConnectionLost(dat: mqttclientDAT, msg: str):
	op('gaia_nursery_control').module.on_connection_lost(msg)
	return

def onSubscribe(dat: mqttclientDAT):
	return

def onSubscribeFailure(dat: mqttclientDAT, msg: str):
	print(f"[GAIA Nursery] Subscribe fallita: {msg}")
	return

def onUnsubscribe(dat: mqttclientDAT):
	return

def onUnsubscribeFailure(dat: mqttclientDAT, msg: str):
	return

def onPublish(dat: mqttclientDAT, topic: str):
	return

def onMessage(dat: mqttclientDAT, topic: str, payload: str, qos: int,
			  retained: bool, dup: bool):
	op('gaia_nursery_control').module.on_message(topic, payload)
	return
