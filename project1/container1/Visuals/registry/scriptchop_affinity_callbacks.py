def onCook(scriptOp):
	parent().UpdatePeople()
	r, g, b, intensity = parent().GetAffinityWash()

	scriptOp.clear()
	rChan = scriptOp.appendChan('r')
	gChan = scriptOp.appendChan('g')
	bChan = scriptOp.appendChan('b')
	iChan = scriptOp.appendChan('intensity')
	scriptOp.numSamples = 1
	rChan[0] = r
	gChan[0] = g
	bChan[0] = b
	iChan[0] = intensity
	return
