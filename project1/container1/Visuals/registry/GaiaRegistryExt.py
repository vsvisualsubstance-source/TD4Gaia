class GaiaRegistryExt:
	"""
	Tracks dynamic gaia/canvas/* keys (detected object classes, lexicon words)
	that a static Select CHOP cannot represent, since keys appear and disappear
	at runtime. Owns per-key seed/count/alpha state so disappearance fades out
	over a few seconds instead of snapping to nothing.
	"""

	MAX_INHABITANTS = 32
	MAX_LEXICON_SLOTS = 64
	APPEAR_RATE = 0.22
	DECAY_RATE = 0.90
	EPSILON = 0.001
	SEED_MOD = 16777216
	ROOMS = ['corridoio', 'ingresso', 'salotto', 'soggiorno']
	RECOGNITION_GRACE_FRAMES = 90
	PLANT_SLOT_COUNT = 16
	PLANT_SLOT_LIFE_FRAMES = 60

	def __init__(self, ownerComp):
		self.ownerComp = ownerComp
		self._objects = {}
		self._lexicon = {}
		self._people = {}
		self._recognitions = {}
		self._pending_recognition = {}
		self._pending_enrollment = {}
		self._canvas = {}
		self._pending_plant = {}
		self._plantSlots = [
			{'active': False, 'hue': 0.0, 'vel': 0.0, 'roomNorm': 0.0, 'bornFrame': -100000}
			for _ in range(self.PLANT_SLOT_COUNT)
		]
		self._plantSlotCursor = 0

	def onDestroyTD(self):
		pass

	def onInitTD(self):
		pass

	def _osc(self):
		return self.ownerComp.op('../../oscin1')

	def _canvasChop(self):
		# gaia/canvas/* moved off oscin1 (port 7000) to port 7001 (OSC In
		# DAT, string-capable) on 2026-08-04. canvas_bridge re-exposes the
		# numeric subset as CHOP channels with the same names oscin1 used.
		# FIX 2026-08-08: era '../../canvas_bridge' (un livello di troppo,
		# risolveva a /project1/container1/canvas_bridge, None). registry
		# e canvas_bridge sono entrambi figli diretti di Visuals.
		return self.ownerComp.op('../canvas_bridge')

	def _roomNorm(self, room):
		if room not in self.ROOMS:
			return 0.0
		return self.ROOMS.index(room) / max(1, len(self.ROOMS) - 1)

	def UpdateObjects(self):
		osc = self._canvasChop()
		if osc is None:
			return
		seen = set()
		for ch in osc.chans('gaia/canvas/rooms/*/objects/*/count'):
			parts = ch.name.split('/')
			if len(parts) < 7:
				continue
			room, cls = parts[3], parts[5]
			key = room + '/' + cls
			seedChan = osc.chan('gaia/canvas/rooms/%s/objects/%s/seed' % (room, cls))
			seed = seedChan.eval() if seedChan is not None else 0.0
			seen.add(key)
			entry = self._objects.get(key)
			if entry is None:
				entry = {'alpha': 0.0}
				self._objects[key] = entry
			entry['seed'] = seed
			# Deterministic reduction of the already-hashed incoming seed (NOT a
			# re-hash) - GLSL float32 can't hold Gaia's full FNV-1a range.
			entry['seed_reduced'] = int(seed) % self.SEED_MOD
			entry['count'] = ch.eval()
			entry['room'] = room
			entry['lastSeenFrame'] = absTime.frame
			entry['alpha'] += (1.0 - entry['alpha']) * self.APPEAR_RATE

		for key in list(self._objects.keys()):
			if key in seen:
				continue
			entry = self._objects[key]
			entry['alpha'] *= self.DECAY_RATE
			if entry['alpha'] < self.EPSILON:
				del self._objects[key]

	def GetObjectSlots(self):
		items = sorted(self._objects.items(), key=lambda kv: (-kv[1]['count'], kv[1].get('lastSeenFrame', 0)))
		slots = []
		for key, e in items[:self.MAX_INHABITANTS]:
			slots.append((
				e['seed_reduced'] / float(self.SEED_MOD),
				min(e['count'] / 10.0, 1.0),
				e['alpha'],
				self._roomNorm(e.get('room', '')),
			))
		while len(slots) < self.MAX_INHABITANTS:
			slots.append((0.0, 0.0, 0.0, 0.0))
		return slots

	def UpdateLexicon(self):
		osc = self._canvasChop()
		if osc is None:
			return
		seen = set()
		for ch in osc.chans('gaia/canvas/lexicon/*/count'):
			parts = ch.name.split('/')
			if len(parts) < 5:
				continue
			word = parts[3]
			seedChan = osc.chan('gaia/canvas/lexicon/%s/seed' % word)
			seed = seedChan.eval() if seedChan is not None else 0.0
			seen.add(word)
			entry = self._lexicon.get(word)
			if entry is None:
				entry = {'alpha': 0.0}
				self._lexicon[word] = entry
			entry['seed'] = seed
			entry['seed_reduced'] = int(seed) % self.SEED_MOD
			entry['count'] = ch.eval()
			entry['lastSeenFrame'] = absTime.frame
			entry['alpha'] += (1.0 - entry['alpha']) * self.APPEAR_RATE

		for word in list(self._lexicon.keys()):
			if word in seen:
				continue
			entry = self._lexicon[word]
			entry['alpha'] *= self.DECAY_RATE
			if entry['alpha'] < self.EPSILON:
				del self._lexicon[word]

	def GetLexiconSlots(self):
		items = sorted(self._lexicon.items(), key=lambda kv: (-kv[1]['count'], kv[1].get('lastSeenFrame', 0)))
		slots = []
		for word, e in items[:self.MAX_LEXICON_SLOTS]:
			slots.append((
				e['seed_reduced'] / float(self.SEED_MOD),
				min(e['count'] / 20.0, 1.0),
				e['alpha'],
			))
		while len(slots) < self.MAX_LEXICON_SLOTS:
			slots.append((0.0, 0.0, 0.0))
		return slots

	def _nameHue(self, name):
		# gaia/people/{name} carries no Gaia-provided seed (unlike
		# objects/lexicon/dream words) - this is a locally-computed stable
		# color key, not a violation of the "never rehash Gaia's seed" rule,
		# since there is no seed here to rehash. Same name always yields the
		# same hue, which is all the identity guarantee this needs.
		h = 0
		for ch in name:
			h = (h * 131 + ord(ch)) % 2147483647
		return (h % 10000) / 10000.0

	def _hsv2rgb(self, h, s, v):
		i = int(h * 6.0)
		f = h * 6.0 - i
		p = v * (1.0 - s)
		q = v * (1.0 - f * s)
		t = v * (1.0 - (1.0 - f) * s)
		i = i % 6
		if i == 0:
			return (v, t, p)
		if i == 1:
			return (q, v, p)
		if i == 2:
			return (p, v, t)
		if i == 3:
			return (p, q, v)
		if i == 4:
			return (t, p, v)
		return (v, p, q)

	def UpdatePeople(self):
		osc = self._osc()
		if osc is None:
			return
		seen = set()
		for ch in osc.chans('gaia/people/*/present'):
			parts = ch.name.split('/')
			if len(parts) < 4:
				continue
			name = parts[2]
			present = ch.eval() > 0.5
			affChan = osc.chan('gaia/people/%s/affinity' % name)
			confChan = osc.chan('gaia/people/%s/confidence' % name)
			affinity = affChan.eval() if affChan is not None else 0.0
			confidence = confChan.eval() if confChan is not None else 0.0
			entry = self._people.get(name)
			if entry is None:
				entry = {'alpha': 0.0, 'hue': self._nameHue(name)}
				self._people[name] = entry
			entry['affinity'] = affinity
			entry['confidence'] = confidence
			if present:
				seen.add(name)
				entry['lastSeenFrame'] = absTime.frame
				entry['alpha'] += (1.0 - entry['alpha']) * self.APPEAR_RATE

		for name in list(self._people.keys()):
			if name in seen:
				continue
			entry = self._people[name]
			entry['alpha'] *= self.DECAY_RATE
			if entry['alpha'] < self.EPSILON:
				del self._people[name]

	def RecordCanvasValue(self, address, value):
		"""Called once per OSC message from event_names_in for EVERY
		/gaia/canvas/* address (port 7001). address includes the
		'gaia/canvas/' prefix, matching oscin1's old channel names."""
		self._canvas[address] = value

	def GetCanvas(self, address, default=0.0):
		v = self._canvas.get(address, default)
		return v if isinstance(v, (int, float)) else default

	def GetCanvasString(self, address, default=''):
		v = self._canvas.get(address, default)
		return v if isinstance(v, str) else default

	def GetCanvasKeys(self, prefix):
		"""All /gaia/canvas/* addresses seen so far starting with prefix -
		lets a consumer scan a dynamically-indexed family (e.g.
		voiceCommands/{i}/*) the same way canvas CHOP channels already
		support via chans(pattern), for string-valued entries which have
		no CHOP channel."""
		return [k for k in self._canvas.keys() if k.startswith(prefix)]

	def GetCanvasNumeric(self):
		"""(name, value) pairs for every numeric canvas entry seen so far -
		feeds canvas_bridge's Script CHOP."""
		return [(k, v) for k, v in self._canvas.items() if isinstance(v, (int, float))]

	def _commitRecognition(self, camera, name, confidence):
		entry = self._recognitions.get(camera)
		if entry is None:
			entry = {'alpha': 0.0}
			self._recognitions[camera] = entry
		entry['name'] = name
		entry['hue'] = self._nameHue(name)
		entry['confidence'] = max(0.0, min(1.0, confidence))
		entry['lastSeenFrame'] = absTime.frame
		entry['alpha'] += (1.0 - entry['alpha']) * self.APPEAR_RATE

	def RecordRecognitionField(self, field, value):
		"""Fields for one recognition arrive as separate messages in the
		same burst, order not guaranteed - buffer the latest value of each
		and commit whenever both person+camera are known."""
		self._pending_recognition[field] = value
		person = self._pending_recognition.get('person')
		camera = self._pending_recognition.get('camera')
		if not person or not camera:
			return
		confidence = self._pending_recognition.get('confidence', 0.0)
		self._commitRecognition(camera, person, float(confidence))

	def RecordEnrollmentField(self, field, value):
		self._pending_enrollment[field] = value
		name = self._pending_enrollment.get('name')
		camera = self._pending_enrollment.get('camera')
		if not name or not camera:
			return
		self._commitRecognition(camera, name, 1.0)

	def DecayRecognitions(self):
		"""Only decays a room after RECOGNITION_GRACE_FRAMES of silence -
		person_recognized re-fires continuously while someone stays in
		frame, so this keeps presence reading as continuous."""
		for room in list(self._recognitions.keys()):
			entry = self._recognitions[room]
			if absTime.frame - entry.get('lastSeenFrame', 0) <= self.RECOGNITION_GRACE_FRAMES:
				continue
			entry['alpha'] *= self.DECAY_RATE
			if entry['alpha'] < self.EPSILON:
				del self._recognitions[room]

	def GetRecognitionSlots(self):
		"""Fixed ROOMS-length slots (one marker per room) for the outer
		individual-object visual (recognition_geo) - unlike
		GetRecognitionFlash (single most-recent aggregate, used by the
		old wash), this shows every room with an active recognition
		simultaneously. Returns len(ROOMS) tuples of (r, g, b,
		intensity), in ROOMS order so the shader can derive each
		marker's angle from its slot index directly."""
		out = []
		for room in self.ROOMS:
			entry = self._recognitions.get(room)
			if entry is None:
				out.append((0.0, 0.0, 0.0, 0.0))
				continue
			r, g, b = self._hsv2rgb(entry['hue'], 0.6, 1.0)
			intensity = entry['alpha'] * (0.4 + 0.6 * entry.get('confidence', 0.0))
			out.append((r, g, b, intensity))
		return out

	def RecordPlantNoteField(self, field, value):
		"""AV Herbarium plays a note per pluck (can be several/sec with
		arpeggiated presets) - genuinely percussive. Each note arrives as
		5 separate OSC messages (note, velocity, channel, room, ts, per
		the Gaia integration doc) - commits once note+velocity+room are
		all buffered, spawning one ring-buffer slot per note. Clears the
		buffer immediately after committing so the trailing channel/ts
		messages of the SAME burst don't each re-trigger another commit
		(previously burned 3-5 ring slots on a single real note - the
		cause of several near-identical slots clustering together and
		the outer ring looking frozen instead of showing distinct,
		independently-timed sparks)."""
		self._pending_plant[field] = value
		note = self._pending_plant.get('note')
		velocity = self._pending_plant.get('velocity')
		room = self._pending_plant.get('room')
		if note is None or velocity is None or not room:
			return
		hue = (float(note) % 12.0) / 12.0  # pitch class -> hue wheel

		slot = self._plantSlots[self._plantSlotCursor]
		slot['active'] = True
		slot['hue'] = hue
		slot['vel'] = max(0.0, min(1.0, float(velocity) / 127.0))
		slot['roomNorm'] = self._roomNorm(room)
		slot['bornFrame'] = absTime.frame
		self._plantSlotCursor = (self._plantSlotCursor + 1) % self.PLANT_SLOT_COUNT
		self._pending_plant.clear()

	def GetPlantSlots(self):
		"""
		One independently-timed fading spark per recent plant_note, for the
		outer particle visual (plantnotes_geo) - unlike GetPlantNoteFlash
		(single most-recent-per-room aggregate, used by the ambient wash),
		this can show several simultaneous/overlapping notes at once.
		Returns PLANT_SLOT_COUNT tuples of (r, g, b, brightness, roomNorm)
		in a fixed cursor order that texelFetch relies on.
		"""
		out = []
		for slot in self._plantSlots:
			if not slot['active']:
				out.append((0.0, 0.0, 0.0, 0.0, 0.0))
				continue
			age = absTime.frame - slot['bornFrame']
			lifeAlpha = max(0.0, 1.0 - age / float(self.PLANT_SLOT_LIFE_FRAMES))
			if lifeAlpha <= 0.0:
				slot['active'] = False
				out.append((0.0, 0.0, 0.0, 0.0, 0.0))
				continue
			r, g, b = self._hsv2rgb(slot['hue'], 0.75, 1.0)
			out.append((r, g, b, slot['vel'] * lifeAlpha, slot['roomNorm']))
		return out

	# Room activity string -> a rough 0-1 "energy level", ordered by how
	# lively that state implies. Unknown/missing values fall back to
	# 'idle' rather than 0, matching the "never a bare zero" rule.
	ACTIVITY_LEVEL = {
		'empty': 0.0,
		'idle': 0.15,
		'resting': 0.25,
		'sitting': 0.4,
		'present': 0.65,
		'working': 1.0,
	}

	def GetRoomEnvironment(self):
		"""
		Real per-room environmental data for the soul sphere's room-sector
		groups (replaces the old purely-decorative per-point hash jitter).
		Returns ROOMS-length tuples of (tempNorm, hasTemp, darkness,
		presenceNorm, activityLevel):
		  tempNorm    - temperature mapped 15-32C -> 0-1, clamped. Defaults
		                to 0.5 (a neutral ~23C) when no sensor is present -
		                never a bare 0, per the "must have at least one
		                positive value" rule from the noise1/glsl_soulfx fix.
		  hasTemp     - 1.0 if a real sensor reading exists this tick, else
		                0.0 - lets the shader/legend distinguish real data
		                from the neutral fallback.
		  darkness    - 0/1 as sent by Gaia, defaulting to 0 (bright/unknown)
		                when absent.
		  presenceNorm - presence_count / 3, clamped 0-1.
		  activityLevel - ACTIVITY_LEVEL[activity string], defaulting to
		                'idle' (0.15) when the room has no activity field
		                this tick - drives that sector's animation energy.
		"""
		canvas = self._canvasChop()
		out = []
		for room in self.ROOMS:
			if canvas is None:
				out.append((0.5, 0.0, 0.0, 0.0, 0.15))
				continue
			tempChan = canvas.chan('gaia/canvas/rooms/%s/temperature' % room)
			darkChan = canvas.chan('gaia/canvas/rooms/%s/darkness' % room)
			presChan = canvas.chan('gaia/canvas/rooms/%s/presence_count' % room)
			if tempChan is not None:
				temp = tempChan.eval()
				tempNorm = max(0.0, min(1.0, (temp - 15.0) / 17.0))
				hasTemp = 1.0
			else:
				tempNorm = 0.5
				hasTemp = 0.0
			darkness = darkChan.eval() if darkChan is not None else 0.0
			presence = presChan.eval() if presChan is not None else 0.0
			presenceNorm = max(0.0, min(1.0, presence / 3.0))
			activity = self.GetCanvasString('gaia/canvas/rooms/%s/activity' % room, 'idle')
			activityLevel = self.ACTIVITY_LEVEL.get(activity, 0.15)
			out.append((tempNorm, hasTemp, darkness, presenceNorm, activityLevel))
		return out

	# OpenHAB item name prefix per room - no explicit "room" field on
	# light entries (unlike bricks/rooms), so mapping is by name. "Sala"
	# is the canonical group for salotto (same color as Luce_Salotto_*,
	# just double-exposed under two item names - Sala has the complete
	# power+brightness+color set). Corridoio currently has no
	# color-capable light (brightness/alert only) - deliberately left
	# unmapped so GetRoomLighting reports it honestly as off/no-color
	# rather than guessing.
	LIGHT_PREFIX = {
		'salotto': 'Sala',
		'soggiorno': 'Soggiorno',
		'ingresso': 'luce_Ingresso',
	}

	def _hsbToRgb(self, h, s, b):
		"""h: 0-360, s/b: 0-100 (OpenHAB Hue HSB convention)."""
		h = (h % 360.0) / 360.0
		s = max(0.0, min(1.0, s / 100.0))
		v = max(0.0, min(1.0, b / 100.0))
		return self._hsv2rgb(h, s, v)

	def GetRoomLighting(self):
		"""
		Real Hue light color per room, for the soul sphere's room-sector
		secondary tint (see glsl_soulfx_compute) - only applied when the
		room's light is actually on, per the user's request 2026-08-05.
		Returns ROOMS-length tuples of (r, g, b, powerOn). Rooms with no
		mapped light (corridoio) or no data this tick get (0,0,0,0) -
		powerOn=0 tells the shader to skip the tint entirely rather than
		blend in a fabricated color.
		"""
		out = []
		for room in self.ROOMS:
			prefix = self.LIGHT_PREFIX.get(room)
			if prefix is None:
				out.append((0.0, 0.0, 0.0, 0.0))
				continue
			powerVal = self.GetCanvas('gaia/canvas/lights/%s_Potenza/power' % prefix, 0.0)
			colorStr = self.GetCanvasString('gaia/canvas/lights/%s_Colore/color' % prefix, '')
			if powerVal < 0.5 or not colorStr:
				out.append((0.0, 0.0, 0.0, 0.0))
				continue
			try:
				h, s, b = [float(x) for x in colorStr.split(',')]
			except (ValueError, TypeError):
				out.append((0.0, 0.0, 0.0, 0.0))
				continue
			r, g, bl = self._hsbToRgb(h, s, b)
			out.append((r, g, bl, 1.0))
		return out

	def GetAffinityWash(self):
		# Weighted-average identity color of whoever is currently present -
		# weight is alpha (presence, eased not snapped) times confidence
		# (an uncertain recognition contributes less); the aggregate
		# intensity is the weighted-average affinity, so a stranger
		# (Ospite, affinity=0) barely tints the scene while a person Gaia
		# knows well glows in proportion to the bond actually built over
		# time - the affinity value drives HOW MUCH the scene personalizes,
		# not just whether someone is in the room.
		total_w = 0.0
		r = g = b = 0.0
		aff_w = 0.0
		aff_sum = 0.0
		for name, e in self._people.items():
			w = e['alpha'] * (0.3 + 0.7 * max(0.0, min(1.0, e['confidence'])))
			if w <= 0.0:
				continue
			cr, cg, cb = self._hsv2rgb(e['hue'], 0.55, 1.0)
			r += cr * w
			g += cg * w
			b += cb * w
			total_w += w
			aff_w += w
			aff_sum += max(0.0, min(1.0, e['affinity'])) * w
		if total_w > 0.0:
			r /= total_w
			g /= total_w
			b /= total_w
			intensity = (aff_sum / aff_w) if aff_w > 0.0 else 0.0
		else:
			r = g = b = 0.0
			intensity = 0.0
		return (r, g, b, intensity)
