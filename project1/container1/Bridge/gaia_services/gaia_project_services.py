"""
Collega i servizi REALI di questo progetto a gaia_client (register_service
in Bridge/gaia_client/gaia_device_agent.py) -- senza questo file l'agent
compare in Admin/Pi Manager ma "services": {} resta vuoto, i pulsanti
Enable/Disable/Restart non hanno niente da controllare.

Portato 2026-08-29 da Bridge/gaia_agent/project_services.py durante la
migrazione al gaia_client Universale (GAIA_INTERFACE.md, "Gaia Agent
Universale") -- stessa identica logica di servizio, solo il modulo agent
di riferimento e' cambiato (gaia_device_agent.py dentro gaia_client
invece del vecchio gaia_agent bespoke). I 3 gotcha gia' documentati sotto
restano validi, non sono stati ricontrollati da zero in questo porting.

Storia (preservata dal file originale):
Verificato dal vivo 2026-08-06 (sessione con Envoy) -- tutti e 4 i path
esistono nel network reale, ma due meccanismi della prima stesura (scritta
senza accesso Envoy) erano sbagliati, non solo "da verificare":

- dmx_out: la prima versione assegnava direttamente dmx_out1.par.active,
  che ha un'espressione (op('dmx_ctrl').par.Dmxenable.eval()) legata
  all'interruttore di sicurezza DMX -- assegnare un valore costante la
  distrugge silenziosamente (assegnare un par commuta sempre a CONSTANT,
  vedi rules/parameters.md). Fix: pilotare dmx_ctrl.par.Dmxenable
  direttamente -- il vero interruttore -- senza toccare l'espressione
  derivata su dmx_out1.
- mocap_bridge: bypassare il COMP contenitore non ferma nulla -- verificato
  dal vivo (scriptchop_pose continua a cuocere, totalCooks incrementa,
  anche con mocap_bridge.bypass=True). Il COMP non ha connettori cablati:
  i 4 Script CHOP interni sono letti per path relativo da chopto_pose/
  chopto_hand_left/chopto_hand_right/chopto_face, indipendentemente dal
  bypass del container. Fix: bypassare i 4 Script CHOP veri.

register_all() e' idempotente -- il self-check/self-heal generico dentro
gaia_device_agent.py la richiama da solo se il registro risulta vuoto
(vedi Bridge/gaia_services/lifecycle.py), non serve piu' il richiamo
incondizionato ad ogni frame che il vecchio agent_lifecycle.py faceva.
"""
_MOCAP_CHOPS = ('scriptchop_pose', 'scriptchop_hand_left', 'scriptchop_hand_right', 'scriptchop_face')


def register_all():
	agent = op('/project1/container1/Bridge/gaia_client/gaia_device_agent').module
	if 'mocap_bridge' in agent._services:
		return

	# ── osc_in — riconnette l'ingresso OSC (oscin1, porta 7000) ──────────
	def _osc_in(active):
		o = op('/project1/container1/oscin1')
		if o:
			o.par.active = active
	agent.register_service('osc_in',
		start=lambda: _osc_in(1),
		stop=lambda: _osc_in(0),
		status=lambda: (bool(op('/project1/container1/oscin1').par.active.eval())
						 if op('/project1/container1/oscin1') else None))

	# ── render — pausa/riprendi l'output visivo (blackout senza chiudere TD) ──
	def _render(paused):
		o = op('/project1/container1/Visuals/render1')
		if o:
			o.bypass = paused
	agent.register_service('render',
		start=lambda: _render(False),
		stop=lambda: _render(True),
		status=lambda: (not op('/project1/container1/Visuals/render1').bypass
						 if op('/project1/container1/Visuals/render1') else None))

	# ── dmx_out — luci DMX, via il vero interruttore di sicurezza dmx_ctrl.Dmxenable ──
	def _dmx(active):
		o = op('/project1/container1/Visuals/dmx_ctrl')
		if o:
			o.par.Dmxenable = active
	agent.register_service('dmx_out',
		start=lambda: _dmx(1),
		stop=lambda: _dmx(0),
		status=lambda: (bool(op('/project1/container1/Visuals/dmx_ctrl').par.Dmxenable.eval())
						 if op('/project1/container1/Visuals/dmx_ctrl') else None))

	# ── mocap_bridge — restart mirato del parser mocap (i 4 Script CHOP veri) ──
	def _mocap_chops():
		mb = op('/project1/container1/Visuals/mocap_bridge')
		if mb is None:
			return []
		return [c for c in (mb.op(name) for name in _MOCAP_CHOPS) if c is not None]

	def _mocap(active):
		for chop in _mocap_chops():
			chop.bypass = not active
	agent.register_service('mocap_bridge',
		start=lambda: _mocap(True),
		stop=lambda: _mocap(False),
		status=lambda: (all(not c.bypass for c in _mocap_chops())
						 if _mocap_chops() else None))
