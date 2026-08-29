def onCook(scriptOp):
	parent().UpdateLexicon()
	slots = parent().GetLexiconSlots()

	scriptOp.clear()
	seedChan = scriptOp.appendChan('seedNorm')
	countChan = scriptOp.appendChan('countNorm')
	alphaChan = scriptOp.appendChan('alpha')
	scriptOp.numSamples = len(slots)
	for i, (seedNorm, countNorm, alpha) in enumerate(slots):
		seedChan[i] = seedNorm
		countChan[i] = countNorm
		alphaChan[i] = alpha
	return
