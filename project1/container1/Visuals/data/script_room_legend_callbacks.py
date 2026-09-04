def onCook(scriptOp):
	"""
	Builds the room-sensor legend: one compact line showing the real
	per-room data now driving that room's sector on the soul sphere (see
	glsl_soulfx_compute) - temperature when a sensor is present, plus
	darkness/presence. Gated by text_ctrl.Showsensors.
	"""
	scriptOp.clear()
	ctrl = op('../text_ctrl')
	if ctrl is not None:
		p = getattr(ctrl.par, 'Showsensors', None)
		if p is not None and not p.eval():
			return

	canvas = op('../canvas_bridge')
	registry = op('../registry')
	if canvas is None:
		return

	rooms = ['corridoio', 'ingresso', 'salotto', 'soggiorno']
	labels = {'corridoio': 'Corridoio', 'ingresso': 'Ingresso', 'salotto': 'Salotto', 'soggiorno': 'Soggiorno'}
	activity_it = {
		'empty': 'vuoto', 'idle': 'inattivo', 'resting': 'a riposo',
		'sitting': 'seduto', 'present': 'presente', 'working': 'al lavoro',
	}
	lighting = registry.GetRoomLighting() if registry is not None else [(0.0, 0.0, 0.0, 0.0)] * 4
	parts = []
	for i, room in enumerate(rooms):
		tempChan = canvas.chan('gaia/canvas/rooms/%s/temperature' % room)
		darkChan = canvas.chan('gaia/canvas/rooms/%s/darkness' % room)
		lightChan = canvas.chan('gaia/canvas/rooms/%s/ambient_light' % room)
		bits = []
		if tempChan is not None:
			bits.append('%.0f°C' % tempChan.eval())
		if lightChan is not None:
			bits.append('%.0flux' % lightChan.eval())
		dark = darkChan.eval() if darkChan is not None else 0.0
		if dark > 0.5:
			bits.append('buio')
		activity = registry.GetCanvasString('gaia/canvas/rooms/%s/activity' % room, '')
		if activity:
			bits.append(activity_it.get(activity, activity))
		if lighting[i][3] > 0.5:
			bits.append('luce')
		# Cross-rig awareness (canale 2, 2026-08-30): another TD instance's
		# active DMX palette in this room, mirrored via Gaia room aggregation
		# -- no direct MQTT link needed between TD instances.
		tdActiveChan = canvas.chan('gaia/canvas/rooms/%s/touchdesignerActive' % room)
		if tdActiveChan is not None and tdActiveChan.eval() > 0.5:
			palette = registry.GetCanvasString('gaia/canvas/rooms/%s/dmxPalette/a' % room, '') if registry is not None else ''
			bits.append('DMX %s' % palette if palette else 'TD attivo')
		text = ', '.join(bits) if bits else 'n/d'
		parts.append('%s: %s' % (labels[room], text))
	scriptOp.appendRow(['Sensori - ' + '  |  '.join(parts)])

	# Global row - the sphere's whole-sphere breathing (lifeIndex) and
	# ambient house-aliveness glow (metrics), on port 7000/oscin1, since
	# neither is exposed on the curated 7001 canvas feed.
	lifeIndex = registry.GetCanvas('gaia/canvas/soul/lifeIndex', -1.0)
	osc = op('/project1/container1/oscin1')
	glights = osc.chan('gaia/metrics/activeLights') if osc is not None else None
	gpeople = osc.chan('gaia/metrics/activePeople') if osc is not None else None
	gbits = []
	if lifeIndex >= 0.0:
		gbits.append('vitalità %.0f%%' % lifeIndex)
	if glights is not None:
		gbits.append('%d luci attive' % int(glights.eval()))
	if gpeople is not None:
		n = int(gpeople.eval())
		gbits.append('%d person%s in casa' % (n, 'a' if n == 1 else 'e'))
	if gbits:
		scriptOp.appendRow(['Gaia - ' + ', '.join(gbits)])
	return


def onGetCookLevel(scriptOp: scriptDAT) -> CookLevel:
	return CookLevel.ALWAYS
