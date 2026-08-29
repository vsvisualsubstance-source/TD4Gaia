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

	Relays ollama_bridge's Ask pulse into an async POST via webclient_ollama
	(never blocks the frame). Fire-and-forget: does not guard against a
	second Ask while one is still pending, since this is a manual demo button.

	Args:
		par: The Par object that was pulsed
	"""
	if par.name != 'Ask':
		return
	import json
	bridge = parent()
	body = json.dumps({
		'model': bridge.par.Model.eval(),
		'prompt': bridge.par.Prompt.eval(),
		'stream': False,
		# Ollama here runs CPU-only (size_vram=0, confirmed via /api/ps) - with
		# stream=false the whole response must finish before anything arrives,
		# so an uncapped response can take minutes. Capped for a live-demo
		# button; raise if longer answers are wanted once latency is known.
		'options': {'num_predict': 60},
	})
	op('webclient_ollama').request(
		bridge.par.Ollamaurl.eval(),
		'POST',
		header={'Content-Type': 'application/json'},
		data=body,
		timeout=180000,
	)
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
