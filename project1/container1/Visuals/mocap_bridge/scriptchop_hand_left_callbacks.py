def onCook(scriptOp):
	parent().UpdateHandLeft()
	slots = parent().GetHandSlots('left')

	scriptOp.clear()
	xChan = scriptOp.appendChan('x')
	yChan = scriptOp.appendChan('y')
	zChan = scriptOp.appendChan('z')
	aChan = scriptOp.appendChan('alpha')
	scriptOp.numSamples = len(slots)
	for i, (x, y, z, a) in enumerate(slots):
		xChan[i] = x
		yChan[i] = y
		zChan[i] = z
		aChan[i] = a
	return
