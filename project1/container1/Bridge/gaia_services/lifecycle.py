"""
Execute DAT -- registra i servizi reali di questo progetto (osc_in/render/
dmx_out/mocap_bridge) su Bridge/gaia_client dopo la migrazione dal vecchio
Bridge/gaia_agent (2026-08-29, GAIA_INTERFACE.md "Gaia Agent Universale").

Il self-heal vero e proprio (retry quando il registro e' vuoto) vive
generico dentro gaia_device_agent.py (_self_check(), sezione 2) -- questo
file si limita ad ARMARE quel meccanismo con register_project_registrar(),
ripetuto ogni pochi secondi perche' un hot-reload di gaia_device_agent.py
da solo (file diverso, non questo) azzera quel puntatore senza toccare
questa DAT. Stesso pattern di PATCHDECK/gaia_services/lifecycle.py
(TD4PatchDeck).

ATTENZIONE (causa 1 del bug "services vuoto", trovata piu' volte in
flotta il 2026-08-25/29): un executeDAT appena creato ha TUTTI i toggle
callback OFF di default -- Create e Frame Start sono stati accesi
esplicitamente su questa DAT dopo la creazione, non fidarsi del default.
"""

import time

_last_registrar_check = 0.0
_REGISTRAR_CHECK_INTERVAL_S = 5.0


def _agent():
	return op('/project1/container1/Bridge/gaia_client/gaia_device_agent')


def _services_dat():
	return op('gaia_project_services')


def _ensure_registrar():
	"""Ri-arma il puntatore registrar su gaia_device_agent se un suo
	hot-reload indipendente lo ha azzerato."""
	global _last_registrar_check
	now = time.time()
	if (now - _last_registrar_check) < _REGISTRAR_CHECK_INTERVAL_S:
		return
	_last_registrar_check = now
	agent_dat = _agent()
	services_dat = _services_dat()
	if agent_dat is None or services_dat is None:
		return
	if agent_dat.module._registrar is None:
		agent_dat.module.register_project_registrar(services_dat.module.register_all)


def onCreate():
	agent_dat = _agent()
	services_dat = _services_dat()
	if agent_dat and services_dat:
		agent_dat.module.register_project_registrar(services_dat.module.register_all)
		services_dat.module.register_all()
	return


def onStart():
	agent_dat = _agent()
	services_dat = _services_dat()
	if agent_dat and services_dat:
		agent_dat.module.register_project_registrar(services_dat.module.register_all)
		services_dat.module.register_all()
	return


def onFrameStart(frame: int):
	_ensure_registrar()
	return
