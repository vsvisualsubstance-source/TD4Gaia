def onCook(scriptOp):
	"""
	Packs registry.GetRecognitionSlots() (4 room slots x (r,g,b,intensity))
	into 16 channels in a fixed attribute-major order: 4 r, 4 g, 4 b,
	4 intensity. chopto_recognition (rowscropped layout) turns this into
	a 16-row, 1-col texture; the compute shader reads
	texelFetch(tex, ivec2(0, attrIndex*4 + slotID), 0).r per attribute.
	"""
	registry = op('../registry')
	ctrl = op('../event_ctrl')
	scriptOp.clear()
	scriptOp.numSamples = 1

	amount = 1.0
	if ctrl is not None:
		amount = ctrl.par.Recognizeenable.eval() * ctrl.par.Recognizeamount.eval()

	# This is now the only per-frame driver of recognition-state decay -
	# formerly scriptchop_recognition (deleted along with the old wash
	# chain it fed).
	if registry is not None:
		registry.DecayRecognitions()

	slots = registry.GetRecognitionSlots() if registry is not None else []
	n = 4
	while len(slots) < n:
		slots.append((0.0, 0.0, 0.0, 0.0))

	for attrIdx in range(4):
		for slotIdx in range(n):
			val = slots[slotIdx][attrIdx]
			if attrIdx == 3:
				val = val * amount
			scriptOp.appendChan('a%d_%d' % (attrIdx, slotIdx)).vals = [val]
	return
