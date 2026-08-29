"""
Script DAT Callbacks

me - this DAT

scriptOp - the OP which is cooking
"""

# press 'Setup Parameters' in the OP to call this function to re-create the
# parameters.
def onSetupParameters(scriptOp: scriptDAT):
	"""
	Called to setup custom parameters for the Script DAT.
	"""
	page = scriptOp.appendCustomPage('Custom')
	p = page.appendFloat('Valuea', label='Value A')
	p = page.appendFloat('Valueb', label='Value B')
	return

def onPulse(par: Par):
	"""
	Called when a custom pulse parameter is pushed.
	
	Args:
		par: The parameter that was pulsed
	"""
	return

def onCook(scriptOp: scriptDAT):
	"""
	Called when the Script DAT needs to cook.

	Builds one row per active YOLO/vision detection read live from oscin1:
	named people present (with confidence) and objects seen per room.
	"""
	scriptOp.clear()

	osc = op('../../oscin1')
	if osc is None:
		return

	for ch in osc.chans('gaia/people/*/present'):
		if ch.eval() < 0.5:
			continue
		parts = ch.name.split('/')
		if len(parts) < 3:
			continue
		personName = parts[2]
		confChan = osc.chan(f'gaia/people/{personName}/confidence')
		if confChan is not None:
			scriptOp.appendRow([f'{personName} ({int(round(confChan.eval() * 100))}%)'])
		else:
			scriptOp.appendRow([personName])

	objectsByRoom = {}
	for ch in osc.chans('gaia/rooms/*/objects/*'):
		if ch.eval() <= 0.5:
			continue
		parts = ch.name.split('/')
		if len(parts) < 5:
			continue
		room, objectName = parts[2], parts[4]
		objectsByRoom.setdefault(room, set()).add(objectName)

	for room in sorted(objectsByRoom):
		scriptOp.appendRow([f'{room}: {", ".join(sorted(objectsByRoom[room]))}'])

	return

def onGetCookLevel(scriptOp: scriptDAT) -> CookLevel:
	"""
	Sets the scriptOp's cook level, the conditions necessary to cause a cook.

	Return one of the following:
		CookLevel.AUTOMATIC - inputs changed and output being used. TD default
							  behavior.
		CookLevel.ON_CHANGE - inputs changed, output used or not.
		CookLevel.WHEN_USED - every frame when output is being used
		CookLevel.ALWAYS - every frame
	"""

	return CookLevel.ALWAYS
