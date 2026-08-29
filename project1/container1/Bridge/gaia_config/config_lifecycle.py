def onFrameStart(frame):
	op('camera_resolver').module.resolve()
	op('beacon_discovery').module.resolve()
	return

def onCreate():
	return

def onExit():
	return
