def onCook(scriptOp):
	parent().UpdatePresence()
	parent().UpdatePose()
	slots = parent().GetPoseSlots()
	presence = parent().GetPresence()

	scriptOp.clear()
	xChan = scriptOp.appendChan('x')
	yChan = scriptOp.appendChan('y')
	zChan = scriptOp.appendChan('z')
	aChan = scriptOp.appendChan('alpha')
	pChan = scriptOp.appendChan('presence')
	scriptOp.numSamples = len(slots)
	for i, (x, y, z, a) in enumerate(slots):
		xChan[i] = x
		yChan[i] = y
		zChan[i] = z
		aChan[i] = a
		pChan[i] = presence
	return
