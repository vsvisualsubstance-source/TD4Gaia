# me - this DAT
# panelValue - the PanelValue object that changed
# 
# Make sure the corresponding toggle is enabled in the Panel Execute DAT.

def onValueChange(panelValue):
	#if panelValue.name == 'key':
	#	if panelValue > 0:
	#		op('webrender1').sendKey(panelValue)

	# retrieve all panel states necessary for the interactMouse method
	ownerVals = panelValue.owner.panel
	click = ownerVals.click
	u = ownerVals.insideu
	v = ownerVals.insidev
	left = bool(ownerVals.lselect)
	middle = bool(ownerVals.mselect)
	right = bool(ownerVals.rselect)
	leftClick = [0,click][left]
	middleClick = [0,click][middle]
	rightClick = [0,click][right]
	wheel = ownerVals.wheel

	# call interactMouse on webrender
	op('webrender1').interactMouse(u, v, left=left, middle=middle, right=right, wheel=wheel)

	return