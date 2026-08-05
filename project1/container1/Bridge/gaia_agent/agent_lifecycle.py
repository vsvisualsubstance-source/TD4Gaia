def onFrameStart(frame):
	op('gaia_device_agent').module.tick()
	return

# NOTA (riscrittura 2026-08-05): onCreate/onExit rimossi -- non serve piu'
# un client Python da avviare/fermare esplicitamente. mqtt_agent
# (mqttclientDAT nativo, Active=1) si connette da solo ogni volta che
# l'operatore e' vivo, incluso dopo un TDN reimport o uno strip/restore
# di Embody. tick() e' un heartbeat throttlato (vedi gaia_device_agent.py).
