def onFrameStart(frame):
	changed = op('td_service_control').module.tick()
	if changed:
		lst = op('ui_panel/devices_list')
		if lst is not None:
			lst.par.reset.pulse()
	return

# NOTA (riscrittura 2026-08-05): onCreate/onExit rimossi -- non serve piu'
# un client Python da avviare/fermare esplicitamente. mqtt_control
# (mqttclientDAT nativo, Active=1) si connette da solo ogni volta che
# l'operatore e' vivo. tick() ricalcola il flag "offline" ogni ~10s e
# riporta se la tabella e' cambiata (vedi td_service_control.py).
