def onFrameStart(frame):
	op('gaia_device_agent').module.tick()
	op('project_services').module.register_all()
	return

# NOTA (riscrittura 2026-08-05): onCreate/onExit rimossi -- non serve piu'
# un client Python da avviare/fermare esplicitamente. mqtt_agent
# (mqttclientDAT nativo, Active=1) si connette da solo ogni volta che
# l'operatore e' vivo, incluso dopo un TDN reimport o uno strip/restore
# di Embody. tick() e' un heartbeat throttlato (vedi gaia_device_agent.py).
#
# AGGIUNTO 2026-08-06: register_all() (project_services.py, nuovo Text DAT
# in questo stesso COMP) collega i servizi reali (osc_in/render/dmx_out/
# mocap_bridge) -- e' idempotente e va richiamata ad ogni frame per lo
# stesso motivo di tick(): dopo uno strip/restore di Embody _services in
# gaia_device_agent.py torna vuoto, senza questa chiamata i pulsanti in
# Admin resterebbero di nuovo senza controlli finche' non si riavvia TD.
