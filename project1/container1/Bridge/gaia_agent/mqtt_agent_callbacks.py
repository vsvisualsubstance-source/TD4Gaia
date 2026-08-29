"""
MQTT Client DAT Callbacks — delega tutta la logica a gaia_device_agent.py
(sorgente di verita' condivisa, portabile identica in ogni progetto). Le
funzioni qui girano gia' sul thread principale (dispatch nativo del
Callbacks DAT), quindi e' sicuro toccare op()/par direttamente.

me - this DAT
"""

def onConnect(dat: mqttclientDAT):
	op('gaia_device_agent').module.on_connect(dat)
	return

def onConnectFailure(dat: mqttclientDAT, msg: str):
	op('gaia_device_agent').module.on_connect_failure(msg)
	return

def onConnectionLost(dat: mqttclientDAT, msg: str):
	op('gaia_device_agent').module.on_connection_lost(msg)
	return

def onSubscribe(dat: mqttclientDAT):
	return

def onSubscribeFailure(dat: mqttclientDAT, msg: str):
	print(f"[GAIA Agent] Subscribe fallita: {msg}")
	return

def onUnsubscribe(dat: mqttclientDAT):
	return

def onUnsubscribeFailure(dat: mqttclientDAT, msg: str):
	return

def onPublish(dat: mqttclientDAT, topic: str):
	return

def onMessage(dat: mqttclientDAT, topic: str, payload: str, qos: int,
			  retained: bool, dup: bool):
	op('gaia_device_agent').module.on_message(topic, payload)
	return
