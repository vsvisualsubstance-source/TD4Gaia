"""
Script CHOP Callbacks

me - this DAT

scriptOp - the OP which is cooking

Reads the 22 zone colors directly from zones_geo's own compute shader output
(glsl_zonelayout's per-point Color attribute) - the SAME color the visual
render actually shows for each zone (on/off mix, brightness, motion, YOLO
presence boost all already applied), not the raw Hue input state. One
virtual DMX "fixture" per zone, driven by what's on screen.
"""

def onSetupParameters(scriptOp: scriptCHOP):
	return

def onPulse(par: Par):
	return

def onCook(scriptOp: scriptCHOP):
	scriptOp.clear()
	# points('Color') is a synchronous GPU->CPU readback (same cost class as
	# TOP.sample() - stalls the GPU pipeline) - measured at ~9.7ms/frame when
	# done every frame via CookLevel.ALWAYS, enough to drop fps 30->~22.
	# DMX lighting doesn't need full-rate precision, so only actually read
	# every 3 frames (~10Hz) and reuse the cached values otherwise - channels
	# still get written every cook (cheap), just from cached Python data.
	frame = absTime.frame
	lastFrame = me.fetch('lastReadFrame', -999)
	cached = me.fetch('cachedColors', None)
	if cached is None or (frame - lastFrame) >= 3:
		src = op('zones_geo/glsl_zonelayout')
		if src is None:
			return
		cached = [tuple(c) for c in src.points('Color')]
		me.store('cachedColors', cached)
		me.store('lastReadFrame', frame)
	for i, c in enumerate(cached):
		n = i + 1
		scriptOp.appendChan('zone%d_r' % n)[0] = c[0]
		scriptOp.appendChan('zone%d_g' % n)[0] = c[1]
		scriptOp.appendChan('zone%d_b' % n)[0] = c[2]
	return

def onGetCookLevel(scriptOp: scriptCHOP) -> CookLevel:
	return CookLevel.ALWAYS
