"""
Parameter Execute DAT

me - this DAT

Make sure the corresponding toggle is enabled in the Parameter Execute DAT.
"""

from typing import Any, List

def onValueChange(par: Par, prev: Any):
	return

def onValuesChanged(changes: List[ParChange]):
	for c in changes:
		par = c.par
		prev = c.prev
	return

_MOOD_SENDS = {
	'Sendstress': ('stress', 'Deltastress'),
	'Sendcalm': ('calm', 'Deltacalm'),
	'Sendsocial': ('social', 'Deltasocial'),
	'Sendcuriosity': ('curiosity', 'Deltacuriosity'),
	'Sendenergy': ('energy', 'Deltaenergy'),
}


def onPulse(par: Par):
	if par.name not in _MOOD_SENDS:
		return
	dimension, delta_par_name = _MOOD_SENDS[par.name]
	delta = parent().par[delta_par_name].eval()
	# Device id prefix agreed in GAIA_INTERFACE.md (2026-08-06) so multiple
	# live TD instances don't collide on the same MQTT topic on the Gaia
	# side (gaia/touchdesigner/<path>). Requires osc_bridge.py's
	# TouchDesignerToGaia to route by device_id -- coordinated there.
	agent = op('../Bridge/gaia_client')
	device_id = agent.par.Deviceid.eval() if agent is not None else 'unknown'
	op('mood_out').sendOSC(f'/gaia/td/{device_id}/mood/{dimension}', [delta])
	return

def onExpressionChange(par: Par, val: str, prev: str):
	return

def onExportChange(par: Par, val: str, prev: str):
	return

def onEnableChange(par: Par, val: bool, prev: bool):
	return

def onModeChange(par: Par, val: ParMode, prev: ParMode):
	return
