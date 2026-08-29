def onCook(scriptOp):
	"""
	Packs registry.GetPlantSlots() (16 slots x (r,g,b,brightness,roomNorm))
	into 80 channels in a fixed attribute-major order: 16 r, 16 g, 16 b,
	16 brightness, 16 roomNorm. chopto_plantnotes (rowscropped layout)
	turns this into an 80-row, 1-col texture; the compute shader reads
	texelFetch(tex, ivec2(0, attrIndex*16 + slotID), 0).r per attribute.
	"""
	registry = op('../registry')
	ctrl = op('../event_ctrl')
	scriptOp.clear()
	scriptOp.numSamples = 1

	amount = 1.0
	if ctrl is not None:
		amount = ctrl.par.Plantenable.eval() * ctrl.par.Plantamount.eval()

	slots = registry.GetPlantSlots() if registry is not None else []
	n = 16
	while len(slots) < n:
		slots.append((0.0, 0.0, 0.0, 0.0, 0.0))

	for attrIdx in range(5):
		for slotIdx in range(n):
			val = slots[slotIdx][attrIdx]
			if attrIdx == 3:
				val = val * amount
			scriptOp.appendChan('a%d_%d' % (attrIdx, slotIdx)).vals = [val]
	return
