class MocapBridgeExt:
	"""
	Defensive adapter for Gaia's mocap OSC feed (gaia/mocap/{device_id}/*,
	device_id configurable via gaia_config.Opsdevice -- see _devicePrefix()).
	The feed's channel addressing is unstable (indices keep incrementing across
	tracking sessions instead of reusing fixed per-landmark slots - confirmed
	empirically: pose channel count grew from 132 to 264 mid-session, with two
	different name-formatting eras coexisting). So identity here is tracked by
	ACTIVITY (a channel's value changing between cooks) rather than by literal
	channel name/index. This only supports coarse "these points are alive right
	now" shape-tracing for an abstract body mirror - NOT stable per-joint
	identity (e.g. "always the left wrist"), and the x/y/z grouping of
	consecutive active channels (sorted by name) is a best-effort heuristic,
	not a guaranteed-correct landmark reconstruction.
	"""

	MAX_POSE_POINTS = 40
	MAX_HAND_POINTS = 24
	MAX_FACE_POINTS = 40
	APPEAR_RATE = 0.3
	DECAY_RATE = 0.85
	EPSILON = 0.001
	# A channel holding any real (non-zero) value stays visible at at least
	# this alpha even once it stops changing - added 2026-08-03 because a
	# manual/burst OSC send (no continuous stream, e.g. testing) has real
	# coordinates but decayed to fully invisible within ~1s under the old
	# change-only alpha, which only ever suited a live continuously-updating
	# camera feed. Live/changing points still ramp to 1.0 as before.
	STATIC_FLOOR = 0.3

	def __init__(self, ownerComp):
		self.ownerComp = ownerComp
		self._prevPose = {}
		self._prevHandLeft = {}
		self._prevHandRight = {}
		self._prevFace = {}
		self._poseAlpha = {}
		self._handLeftAlpha = {}
		self._handRightAlpha = {}
		self._faceAlpha = {}
		self._posePoints = [(0.0, 0.0, 0.0, 0.0)] * self.MAX_POSE_POINTS
		self._handLeftPoints = [(0.0, 0.0, 0.0, 0.0)] * self.MAX_HAND_POINTS
		self._handRightPoints = [(0.0, 0.0, 0.0, 0.0)] * self.MAX_HAND_POINTS
		self._facePoints = [(0.0, 0.0, 0.0, 0.0)] * self.MAX_FACE_POINTS
		self._presence = 0.0

	def onDestroyTD(self):
		pass

	def onInitTD(self):
		pass

	def _osc(self):
		return self.ownerComp.op('../../oscin1')

	def _devicePrefix(self):
		"""'gaia/mocap/{device_id}' -- device_id letto da gaia_config.Opsdevice
		invece di essere cablato letteralmente qui (era 'ops-silvermini2' fisso
		in ogni pattern sotto, stessa categoria di bug delle IP hardcoded
		risolte altrove nel progetto: se il nodo OPS cambia id, i pattern
		smettono di matchare senza nessun errore visibile -- mani/viso/pose
		restano fantasma). gaia_config vive in Bridge, sibling di Visuals."""
		cfg = self.ownerComp.op('../../Bridge/gaia_config')
		device_id = cfg.par.Opsdevice.eval() if cfg is not None else 'ops-silvermini2'
		return f'gaia/mocap/{device_id}'

	@staticmethod
	def _numericSortKey(name):
		# Channel names use inconsistent zero-padding widths (e.g. "01",
		# "010", "0100", "01000" for face) so plain string sort scrambles
		# them completely out of numeric order - "010" < "0100" < "01000" <
		# "01001" alphabetically, not by the actual landmark index. Sorting
		# by the parsed integer suffix instead groups genuinely consecutive
		# indices together, which is what x/y/z(/conf) grouping depends on.
		suffix = name.rsplit('/', 1)[-1]
		try:
			return (0, int(suffix))
		except ValueError:
			return (1, suffix)

	def _trackActivity(self, pattern, prevDict, alphaDict):
		"""
		Reads every channel matching pattern, updates prevDict (last value)
		and alphaDict (activity, decaying unless the value just changed),
		and returns {name: value} for every channel currently "present"
		(holds a real value, or is still decaying from a recent change).
		Split out from the old _updateGroup so face can group results by
		anatomical region instead of one flat sorted run.
		"""
		osc = self._osc()
		if osc is None:
			return {}
		present = {}
		for ch in osc.chans(pattern):
			name = ch.name
			val = ch.eval()
			prev = prevDict.get(name)
			prevDict[name] = val
			if prev is not None and val != prev:
				alphaDict[name] = 1.0
			else:
				alphaDict[name] = alphaDict.get(name, 0.0) * self.DECAY_RATE

			if val != 0.0 or alphaDict.get(name, 0.0) >= self.EPSILON:
				present[name] = val
			else:
				alphaDict.pop(name, None)
		return present

	def _groupPoints(self, names, valsDict, alphaDict, groupSize):
		"""
		Sorts names numerically (see _numericSortKey) and groups them
		consecutively into (x, y, z, alpha[, *conf]) point tuples.
		"""
		names = sorted(names, key=self._numericSortKey)
		points = []
		for i in range(0, len(names) - groupSize + 1, groupSize):
			group = names[i:i + groupSize]
			vals = [valsDict[n] for n in group]
			act = max(min(alphaDict.get(n, 0.0) for n in group), self.STATIC_FLOOR)
			if groupSize == 4:
				conf = max(0.0, min(1.0, vals[3]))
				points.append((vals[0], vals[1], vals[2], act * conf))
			else:
				points.append((vals[0], vals[1], vals[2], act))
		return points

	def _updateGroup(self, pattern, prevDict, alphaDict, groupSize, maxPoints):
		present = self._trackActivity(pattern, prevDict, alphaDict)
		points = self._groupPoints(list(present.keys()), prevDict, alphaDict, groupSize)
		points.sort(key=lambda p: -p[3])
		points = points[:maxPoints]
		while len(points) < maxPoints:
			points.append((0.0, 0.0, 0.0, 0.0))
		return points

	def UpdatePose(self):
		self._posePoints = self._updateGroup(
			self._devicePrefix() + '/pose/*', self._prevPose, self._poseAlpha, 4, self.MAX_POSE_POINTS)

	def UpdateHandLeft(self):
		self._handLeftPoints = self._updateGroup(
			self._devicePrefix() + '/hand/left/*', self._prevHandLeft, self._handLeftAlpha, 3, self.MAX_HAND_POINTS)

	def UpdateHandRight(self):
		self._handRightPoints = self._updateGroup(
			self._devicePrefix() + '/hand/right/*', self._prevHandRight, self._handRightAlpha, 3, self.MAX_HAND_POINTS)

	# Matches a per-region face channel's base name, e.g. "eye_left12" ->
	# region "eye_left", index 12. Region names are letters/underscore only,
	# so this never matches the legacy flat "face/1234" addresses (digits
	# right after "face/", no region word) - confirmed live 2026-08-03:
	# both schemes coexist, the legacy one has grown past face/1999 and is
	# just noise now, ignored entirely in favour of the named-region one.
	_FACE_REGION_RE = re.compile(r'^([a-zA-Z_]+)(\d+)$')

	# Fixed per-region slot budget, summing to MAX_FACE_POINTS (40). Added
	# 2026-08-03 - the previous version pooled all 152 candidate points
	# globally and kept the 40 most "active" ones, which meant whichever
	# region happened to be moving most (e.g. lips while talking) could
	# crowd out everything else, so the shape read as a blob from one part
	# of the face rather than a recognizable face (eyes+brows+nose+mouth+
	# outline together). A fixed budget guarantees every region is always
	# represented, matching what "face construction" actually needs.
	_FACE_REGION_BUDGET = {
		'oval': 10, 'lips': 8, 'eye_left': 6, 'eye_right': 6,
		'nose': 6, 'eyebrow_left': 2, 'eyebrow_right': 2,
	}

	def UpdateFace(self):
		present = self._trackActivity(
			self._devicePrefix() + '/face/0/*', self._prevFace, self._faceAlpha)

		# FIX 2026-08-06 (GAIA_INTERFACE.md canale 7): il gruppo (indice,
		# nome) si costruisce QUI, dallo stesso match regex che identifica
		# la regione -- non piu' un secondo passaggio con _numericSortKey.
		# _numericSortKey prova int() sull'INTERO nome base ("eye_left12"),
		# che fallisce sempre per un nome regione-prefissato e ricade su un
		# ordinamento STRINGA ("eye_left1" < "eye_left10" < "eye_left11" <
		# ... < "eye_left2"), tutt'altro che numerico. Raggruppare 3 nomi
		# consecutivi da quell'ordine mischiava componenti di punti diversi
		# (causa root del "viso ricostruisce come rumore, mani/pose ok" --
		# i nomi base di mani/pose sono cifre pure, es. "012", quindi
		# int() lì funziona e non passa mai da questo ramo).
		regions = {}
		for name in present:
			base = name.rsplit('/', 1)[-1]
			m = self._FACE_REGION_RE.match(base)
			if m:
				regions.setdefault(m.group(1), []).append((int(m.group(2)), name))

		# Confirmed live 2026-08-03: lips(120) eye_left(48) eye_right(48)
		# eyebrow_left(30) eyebrow_right(30) nose(72) oval(108), all evenly
		# divisible by 3 (x,y,z per point).
		all_points = []
		for region, budget in self._FACE_REGION_BUDGET.items():
			entries = regions.get(region)
			if not entries:
				continue
			entries.sort(key=lambda e: e[0])
			names = [n for _, n in entries]
			numPoints = len(names) // 3
			if numPoints == 0:
				continue
			take = min(budget, numPoints)
			# Evenly-spaced point INDICES across the region's own contour,
			# NOT picked by activity - MediaPipe contour indices are
			# spatially ordered around the feature, so an even spread here
			# traces the region's actual outline instead of letting its
			# single busiest sub-area (e.g. one lip corner) stand in for
			# the whole thing.
			step = numPoints / float(take)
			for k in range(take):
				pointIdx = int(k * step)
				group = names[pointIdx * 3:pointIdx * 3 + 3]
				vals = [present[n] for n in group]
				act = max(min(self._faceAlpha.get(n, 0.0) for n in group), self.STATIC_FLOOR)
				all_points.append((vals[0], vals[1], vals[2], act))

		while len(all_points) < self.MAX_FACE_POINTS:
			all_points.append((0.0, 0.0, 0.0, 0.0))
		self._facePoints = all_points[:self.MAX_FACE_POINTS]

	def UpdatePresence(self):
		osc = self._osc()
		if osc is None:
			self._presence *= self.DECAY_RATE
			return
		poses = osc.chan(self._devicePrefix() + '/meta/poses')
		hands = osc.chan(self._devicePrefix() + '/meta/hands')
		active = (poses is not None and poses.eval() > 0) or (hands is not None and hands.eval() > 0)
		target = 1.0 if active else 0.0
		rate = self.APPEAR_RATE if target > self._presence else self.DECAY_RATE
		self._presence += (target - self._presence) * rate

	def GetPoseSlots(self):
		return self._posePoints

	def GetHandSlots(self, side):
		if side == 'left':
			return self._handLeftPoints
		return self._handRightPoints

	def GetFaceSlots(self):
		return self._facePoints

	def GetPresence(self):
		return self._presence
