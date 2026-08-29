"""
Parameter Execute DAT

me - this DAT

Make sure the corresponding toggle is enabled in the Parameter Execute DAT.
"""

from typing import Any, List

def onValueChange(par: Par, prev: Any):
	"""
	Called when a parameter value changes.
	
	Args:
		par: The Par object that has changed (use par.eval() to get current)
		prev: The previous value
	"""
	# use par.eval() to get current value
	return

def onValuesChanged(changes: List[ParChange]):
	"""
	Called at end of frame with complete list of parameter changes.
	
	Args:
		changes: List of ParChange named tuples (Par, previous value)
	"""
	for c in changes:
		# use par.eval() to get current value
		par = c.par
		prev = c.prev
	return

def onPulse(par: Par):
	"""
	Called when a parameter is pulsed.

	Relays web_bridge's Reload custom pulse to webrender1's own Reload
	Current Page pulse - pulse pars can't be bound by expression, so this
	relay is the standard fix (see sediment_reset_relay in Visuals for the
	same pattern).

	Args:
		par: The Par object that was pulsed
	"""
	if par.name == 'Reload':
		op('webrender1').par.reload.pulse()
	return

def onExpressionChange(par: Par, val: str, prev: str):
	"""
	Called when a parameter expression changes.
	
	Args:
		par: The Par object that changed
		val: The current expression value
		prev: The previous expression value
	"""
	return

def onExportChange(par: Par, val: str, prev: str):
	"""
	Called when a parameter export changes.
	
	Args:
		par: The Par object that changed
		val: The current export value
		prev: The previous export value
	"""
	return

def onEnableChange(par: Par, val: bool, prev: bool):
	"""
	Called when a parameter enable state changes.
	
	Args:
		par: The Par object that changed
		val: The current enable state
		prev: The previous enable state
	"""
	return

def onModeChange(par: Par, val: ParMode, prev: ParMode):
	"""
	Called when a parameter mode changes.
	
	Args:
		par: The Par object that changed
		val: The current ParMode
		prev: The previous ParMode
	"""
	return
