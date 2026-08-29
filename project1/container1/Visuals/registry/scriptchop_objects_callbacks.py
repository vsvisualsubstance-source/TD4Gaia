def onCook(scriptOp):
	parent().UpdateObjects()
	slots = parent().GetObjectSlots()

	scriptOp.clear()
	seedChan = scriptOp.appendChan('seedNorm')
	countChan = scriptOp.appendChan('countNorm')
	alphaChan = scriptOp.appendChan('alpha')
	roomChan = scriptOp.appendChan('roomNorm')
	scriptOp.numSamples = len(slots)
	for i, (seedNorm, countNorm, alpha, roomNorm) in enumerate(slots):
		seedChan[i] = seedNorm
		countChan[i] = countNorm
		alphaChan[i] = alpha
		roomChan[i] = roomNorm
	return
