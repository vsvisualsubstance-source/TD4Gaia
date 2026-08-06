"""
Collega servizi REALI all'agent TD (register_service in gaia_device_agent.py)
— senza questo file l'agent compare in Admin/Pi Manager ma "services": {}
resta vuoto, i pulsanti Enable/Disable/Restart non hanno niente da
controllare (gap segnalato dall'utente il 2026-08-06: "al momento non fa
quasi nulla").

Verificato dal vivo 2026-08-06 (sessione con Envoy) — tutti e 4 i path
esistono nel network reale, ma due meccanismi della prima stesura (scritta
senza accesso Envoy) erano sbagliati, non solo "da verificare":

- dmx_out: la prima versione assegnava direttamente dmx_out1.par.active,
  che ha un'espressione (op('dmx_ctrl').par.Dmxenable.eval()) legata
  all'interruttore di sicurezza DMX — assegnare un valore costante la
  distrugge silenziosamente (assegnare un par commuta sempre a CONSTANT,
  vedi rules/parameters.md). Fix: pilotare dmx_ctrl.par.Dmxenable
  direttamente — il vero interruttore — senza toccare l'espressione
  derivata su dmx_out1.
- mocap_bridge: bypassare il COMP contenitore non ferma nulla — verificato
  dal vivo (scriptchop_pose continua a cuocere, totalCooks incrementa,
  anche con mocap_bridge.bypass=True). Il COMP non ha connettori cablati:
  i 4 Script CHOP interni sono letti per path relativo da chopto_pose/
  chopto_hand_left/chopto_hand_right/chopto_face, indipendentemente dal
  bypass del container. Fix: bypassare i 4 Script CHOP veri.

Uso: register_all() è idempotente (una seconda chiamata è no-op) — va
richiamata a ogni onFrameStart (vedi agent_lifecycle.py), così si
riapplica da sola dopo un eventuale strip/restore di Embody che azzera
_services in gaia_device_agent.py.
"""
_done = False

_MOCAP_CHOPS = ('scriptchop_pose', 'scriptchop_hand_left', 'scriptchop_hand_right', 'scriptchop_face')


def register_all():
    global _done
    if _done:
        return
    agent = me.parent().op('gaia_device_agent').module

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

    _done = True
