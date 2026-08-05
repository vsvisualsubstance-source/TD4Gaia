def onCreate():
	op('td_service_control').module.start()
	return

# NOTA (fix 2026-08-05): onStart RIMOSSO da qui apposta -- stesso motivo di
# gaia_agent/agent_lifecycle: il toggle "Start" non sopravvive al roundtrip
# .tox di questo COMP. Il trigger per il vero avvio di TD vive in
# Bridge/gaia_startup (fuori da qualunque sottoalbero tox).

def onFrameStart(frame):
	changed = op('td_service_control').module.drain_inbox()
	if changed:
		lst = op('gaia_control_panel/devices_list')
		if lst is not None:
			lst.par.reset.pulse()
	return

def onExit():
	op('td_service_control').module.stop()
	return
