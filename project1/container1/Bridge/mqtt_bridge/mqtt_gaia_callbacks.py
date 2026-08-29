"""
MQTT Client DAT Callbacks

me - this DAT

Subscribes to everything on Gaia's MQTT bus (widened from an initial 4-topic
list to '#' on 2026-08-03, once a real broker was reachable and the user
asked to see the whole bus) in parallel to Node-RED - read-only, never
publishes back.
"""

def onConnect(dat: mqttclientDAT):
	dat.subscribe('#')
	debug('mqtt_gaia connected to', dat.par.netaddress.eval(), '- subscribed to everything (#)')
	return

def onConnectFailure(dat: mqttclientDAT, msg: str):
	debug('mqtt_gaia connect failed:', msg)
	return

def onConnectionLost(dat: mqttclientDAT, msg: str):
	debug('mqtt_gaia connection lost:', msg)
	return

def onSubscribe(dat: mqttclientDAT):
	return

def onSubscribeFailure(dat: mqttclientDAT, msg: str):
	debug('mqtt_gaia subscribe failed:', msg)
	return

def onUnsubscribe(dat: mqttclientDAT):
	return

def onUnsubscribeFailure(dat: mqttclientDAT, msg: str):
	return

def onPublish(dat: mqttclientDAT, topic: str):
	return

def onMessage(dat: mqttclientDAT, topic: str, payload: str, qos: int,
			  retained: bool, dup: bool):
	# mqtt_gaia's own table is an unstructured single-column message log (no
	# topic column - verified empirically), so this is the only place a
	# message's topic is ever known.
	#
	# The 'payload: str' type hint in TD's own auto-generated scaffold is
	# WRONG - verified empirically that payload arrives as raw bytes at
	# runtime, which without decoding gets str()-coerced into a "b'...'" repr
	# when written into a DAT cell, corrupting downstream JSON parsing.
	if isinstance(payload, bytes):
		payload = payload.decode('utf-8', errors='replace')

	log = op('mqtt_log')
	log.appendRow([topic, payload, qos, retained])
	max_rows = 300
	while log.numRows - 1 > max_rows:
		log.deleteRow(1)
	return
