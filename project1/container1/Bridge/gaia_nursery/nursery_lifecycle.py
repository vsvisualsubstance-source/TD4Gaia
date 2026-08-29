def onFrameStart(frame):
	op('gaia_nursery_control').module.tick()
	return

# mqtt_nursery (mqttclientDAT nativo, Active=1) si connette da solo ogni
# volta che l'operatore e' vivo, incluso dopo un TDN reimport o uno
# strip/restore di Embody -- nessun onCreate/onExit necessario, stesso
# pattern di gaia_control/gaia_agent. tick() e' il solo hook richiesto:
# sweep del TTL, throttlato internamente (vedi gaia_nursery_control.py).
