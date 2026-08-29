def onCook(scriptOp):
	"""
	Packs registry.GetRoomLighting() (4 rooms x (r, g, b, powerOn)) into
	16 channels in a fixed attribute-major order: 4 r, 4 g, 4 b,
	4 powerOn. chopto_room_light (rowscropped layout) turns this into a
	16-row, 1-col texture; glsl_soulfx_compute reads
	texelFetch(tex, ivec2(0, attrIndex*4 + roomIdx), 0).r per attribute,
	same roomIdx (point angle -> sector) as roomTex.
	"""
	registry = op('../registry')
	scriptOp.clear()
	scriptOp.numSamples = 1

	rooms = registry.GetRoomLighting() if registry is not None else []
	n = 4
	while len(rooms) < n:
		rooms.append((0.0, 0.0, 0.0, 0.0))

	for attrIdx in range(4):
		for roomIdx in range(n):
			val = rooms[roomIdx][attrIdx]
			scriptOp.appendChan('a%d_%d' % (attrIdx, roomIdx)).vals = [val]
	return
