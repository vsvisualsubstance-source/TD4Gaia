"""
Collega servizi REALI all'agent TD (register_service in gaia_device_agent.py)
— senza questo file l'agent compare in Admin/Pi Manager ma "services": {}
resta vuoto, i pulsanti Enable/Disable/Restart non hanno niente da
controllare (gap segnalato dall'utente il 2026-08-06: "al momento non fa
quasi nulla").

ATTENZIONE — PATH DA VERIFICARE DAL VIVO (marcati TODO sotto): scritto da
una sessione SENZA accesso Envoy/TD live. L'unica fonte disponibile,
ARCHITECTURE.md, risale al 2026-08-05 e la rete Visuals è già cambiata da
allora (il tree attuale del repo mostra cam1/data/light1/soul_geo/
zones_geo esternalizzati, NON più mocap_bridge/render1/dmx_out1 come
descritto lì) — quei tre operatori potrebbero non esistere più con questi
nomi/path, o non essere mai esistiti con questi nomi esatti. Prima sessione
con Envoy: aprire ogni op(...) sotto nel network reale, correggere i path,
verificare che il parametro giusto sia .par.active vs .bypass per QUEL
tipo di operatore specifico, poi togliere questo paragrafo di avviso.

Uso: register_all() è idempotente (una seconda chiamata è no-op) — va
richiamata a ogni onFrameStart (vedi agent_lifecycle.py), così si
riapplica da sola dopo un eventuale strip/restore di Embody che azzera
_services in gaia_device_agent.py.
"""
_done = False


def register_all():
    global _done
    if _done:
        return
    agent = me.parent().op('gaia_device_agent').module

    # ── osc_in — riconnette l'ingresso OSC (oscin1, porta 7000) ──────────
    # .par.active confermato per QUESTO operatore dalla docstring originale
    # di gaia_device_agent.py (esempio scritto dalla sessione che lavora
    # dentro TD, quindi con visibilità reale) — unico dei 4 di cui sono
    # ragionevolmente sicuro. TODO: verificare comunque il path assoluto.
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
    # TODO path e meccanismo NON verificati — .bypass è la proprietà Python
    # più universale in TD (esiste su qualunque operatore), scelta apposta
    # per non assumere un parametro specifico che potrebbe non esserci su
    # questo tipo di operatore.
    def _render(paused):
        o = op('/project1/container1/Visuals/render1')
        if o:
            o.bypass = paused
    agent.register_service('render',
        start=lambda: _render(False),
        stop=lambda: _render(True),
        status=lambda: (not op('/project1/container1/Visuals/render1').bypass
                         if op('/project1/container1/Visuals/render1') else None))

    # ── dmx_out — luci DMX separate dai visual (vedi i visual senza pilotare le luci reali) ──
    # TODO path NON verificato.
    def _dmx(active):
        o = op('/project1/container1/Visuals/dmx_out1')
        if o:
            o.par.active = active
    agent.register_service('dmx_out',
        start=lambda: _dmx(1),
        stop=lambda: _dmx(0),
        status=lambda: (bool(op('/project1/container1/Visuals/dmx_out1').par.active.eval())
                         if op('/project1/container1/Visuals/dmx_out1') else None))

    # ── mocap_bridge — restart mirato del parser mocap (Script CHOP) ─────
    # TODO path NON verificato. "Restart" da Admin (già esistente in
    # td_service_control.py: stop()+start()) fa bypass=True poi bypass=False
    # — nessuna logica di restart speciale necessaria qui.
    def _mocap(active):
        o = op('/project1/container1/Visuals/mocap_bridge')
        if o:
            o.bypass = not active
    agent.register_service('mocap_bridge',
        start=lambda: _mocap(True),
        stop=lambda: _mocap(False),
        status=lambda: (not op('/project1/container1/Visuals/mocap_bridge').bypass
                         if op('/project1/container1/Visuals/mocap_bridge') else None))

    _done = True
