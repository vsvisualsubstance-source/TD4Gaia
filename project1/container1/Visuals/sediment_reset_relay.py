def onValueChange(par, prev):
	return

def onPulse(par):
	if par.name == 'Sedimentreset':
		op('feedback_sediment').par.resetpulse.pulse()
	return

def onExpressionChange(par, val):
	return

def onExportChange(par, val):
	return

def onEnableChange(par, val):
	return

def onModeChange(par, val):
	return
