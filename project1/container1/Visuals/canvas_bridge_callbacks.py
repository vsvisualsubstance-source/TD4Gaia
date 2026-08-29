def onCook(scriptOp):
	"""
	Re-exposes every numeric gaia/canvas/* value (received via
	event_names_in on port 7001) as CHOP channels named identically to
	oscin1's old channel names, so existing consumers just swap source ops.
	"""
	registry = op('registry')
	scriptOp.clear()
	if registry is None:
		return
	pairs = registry.GetCanvasNumeric()
	scriptOp.numSamples = 1
	for name, value in pairs:
		scriptOp.appendChan(name).vals = [value]
	return
