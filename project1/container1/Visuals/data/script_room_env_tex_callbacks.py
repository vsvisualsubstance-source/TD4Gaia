def onCook(scriptOp):
	"""
	Packs registry.GetRoomEnvironment() (4 rooms x (tempNorm, hasTemp,
	darkness, presenceNorm, activityLevel)) into 20 channels in a fixed
	attribute-major order: 4 tempNorm, 4 hasTemp, 4 darkness,
	4 presenceNorm, 4 activityLevel. chopto_room_env (rowscropped layout)
	turns this into a 20-row, 1-col texture; glsl_soulfx_compute reads
	texelFetch(tex, ivec2(0, attrIndex*4 + roomIdx), 0).r per attribute,
	where roomIdx comes from each point's own angle around the sphere -
	not from this script (which just packs, per-room, in ROOMS order).
	"""
	registry = op('../registry')
	scriptOp.clear()
	scriptOp.numSamples = 1

	rooms = registry.GetRoomEnvironment() if registry is not None else []
	n = 4
	while len(rooms) < n:
		rooms.append((0.5, 0.0, 0.0, 0.0, 0.15))

	for attrIdx in range(5):
		for roomIdx in range(n):
			val = rooms[roomIdx][attrIdx]
			scriptOp.appendChan('a%d_%d' % (attrIdx, roomIdx)).vals = [val]
	return
