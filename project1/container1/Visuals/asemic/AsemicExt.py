class AsemicExt:
	"""
	Vocabolario Asemico - turns Gaia's canvas text (thoughts, speech,
	memories, dreams, voice commands, plant notes, level-ups) into
	deterministic asemic glyphs, per GAIA_INTERFACE.md "Vocabolario
	Asemico" (proposed 2026-08-26, confirmed end-to-end by both sides,
	never actually built until now).

	Two-tier design, per the confirmed spec: topology (which strokes
	exist) only rebuilds when a source's text actually changes (Tick(),
	cheap string comparisons - the expensive glyph_for() call only runs
	on real change); the reveal/hold/fade animation recomputes every
	cook at native TD frame rate (GetGlyphGeometry()), independent of
	ingestion cadence - mirrors web/asemic.js's split between say() (one-
	shot) and its per-frame render loop.
	"""

	MAX_SENTENCES = 10
	MAX_WORDS = 26
	WRITE_MS = 700.0
	STAGGER_MS = 350.0
	ORTHO_W = 2.0
	ASPECT = 1280.0 / 720.0

	# width/hold/fade CONFIRMED from web/asemic.js (GAIA_INTERFACE.md).
	# bandY is our own TD-side vertical placement (canvas band, TD Y-up
	# bottom-origin - dream/rune have no confirmed band, given a neutral
	# mid position).
	INK = {
		'out':   {'width': 1.7, 'holdMs': 9000.0,  'fadeMs': 5000.0, 'bandY': 0.76},
		'in':    {'width': 2.2, 'holdMs': 9000.0,  'fadeMs': 5000.0, 'bandY': 0.37, 'r': 88 / 255.0,  'g': 166 / 255.0, 'b': 255 / 255.0},
		'dream': {'width': 1.6, 'holdMs': 75000.0, 'fadeMs': 9000.0, 'bandY': 0.50, 'r': 190 / 255.0, 'g': 135 / 255.0, 'b': 255 / 255.0},
		'herb':  {'width': 1.9, 'holdMs': 9000.0,  'fadeMs': 5000.0, 'bandY': 0.56, 'r': 120 / 255.0, 'g': 240 / 255.0, 'b': 110 / 255.0},
		'rune':  {'width': 2.4, 'holdMs': 9000.0,  'fadeMs': 5000.0, 'bandY': 0.50, 'r': 255 / 255.0, 'g': 214 / 255.0, 'b': 90 / 255.0},
	}

	# MIDI note % 12 -> solfege syllable, per GAIA_INTERFACE.md's "nota
	# MIDI -> parola solfeggio (do,dodiesis,re,...)".
	SOLFEGE = ['do', 'dodiesis', 're', 'rediesis', 'mi', 'fa', 'fadiesis', 'sol', 'soldiesis', 'la', 'ladiesis', 'si']

	# Concurrent sentences per ink were all drawing at the SAME bandY/
	# wordU, stacking illegibly on top of each other - worst with 'herb'
	# (AV Herbarium notes can arrive several/sec, per
	# GaiaRegistryExt.RecordPlantNoteField's own docstring). Each ink now
	# round-robins through a fixed set of vertical lanes; spawning a new
	# sentence immediately evicts whatever currently occupies that same
	# lane (rather than letting them overlap until both happen to fade).
	LANES = {'out': 3, 'in': 2, 'dream': 2, 'herb': 4, 'rune': 1}
	LANE_SPACING = 0.14

	def __init__(self, ownerComp):
		self.ownerComp = ownerComp
		self._sentences = []
		self._glyphCache = {}
		self._lastSeen = {}
		self._laneCursor = {}
		self.ORTHO_H = self.ORTHO_W / self.ASPECT

	def onDestroyTD(self):
		pass

	def onInitTD(self):
		pass

	def _registry(self):
		return self.ownerComp.op('../registry')

	def _engine(self):
		return self.ownerComp.op('./asemic_engine').module

	def _ctrl(self):
		return self.ownerComp.op('../text_ctrl')

	def _moodColor(self):
		# const_moodcolor (Visuals) divides the same channel by 255 -
		# confirmed by matching its live evaluated color against the
		# "curiosity" mood entry (190,135,255) in GAIA_INTERFACE.md.
		registry = self._registry()
		if registry is None:
			return (0.0, 1.0, 0.8)
		r = registry.GetCanvas('gaia/canvas/soul/mood_rgb/r', 0.0) / 255.0
		g = registry.GetCanvas('gaia/canvas/soul/mood_rgb/g', 255.0) / 255.0
		b = registry.GetCanvas('gaia/canvas/soul/mood_rgb/b', 204.0) / 255.0
		return (r, g, b)

	def _inkColor(self, ink):
		style = self.INK[ink]
		if ink == 'out':
			return self._moodColor()
		return (style['r'], style['g'], style['b'])

	def _say(self, text, ink):
		text = (text or '').strip()
		if not text:
			return
		words = text.split()[:self.MAX_WORDS]
		if not words:
			return
		engine = self._engine()
		glyphs = []
		for word in words:
			key = word.lower()
			glyph = self._glyphCache.get(key)
			if glyph is None:
				glyph = engine.glyph_for(key)
				self._glyphCache[key] = glyph
			glyphs.append(glyph)
		style = self.INK[ink]
		nLanes = self.LANES.get(ink, 1)
		lane = self._laneCursor.get(ink, 0) % nLanes
		self._laneCursor[ink] = lane + 1
		# Evict whatever currently occupies this ink+lane - a new sentence
		# always wins over a stale one rather than drawing on top of it.
		self._sentences = [s for s in self._sentences if not (s['ink'] == ink and s['lane'] == lane)]
		self._sentences.append({
			'ink': ink,
			'lane': lane,
			'glyphs': glyphs,
			'spawnMs': absTime.seconds * 1000.0,
			'holdMs': style['holdMs'],
			'fadeMs': style['fadeMs'],
		})
		if len(self._sentences) > self.MAX_SENTENCES:
			self._sentences.pop(0)

	def _checkChanged(self, key, value):
		"""True once per NEW non-empty value, not on every repeated cook
		while the same value persists."""
		if not value:
			return False
		if self._lastSeen.get(key) == value:
			return False
		self._lastSeen[key] = value
		return True

	def Tick(self):
		"""Ingests new Gaia canvas content into fresh sentences. Cheap
		string comparisons only, called every cook from asemic_sop - the
		expensive glyph_for() call only runs on actual new text."""
		ctrl = self._ctrl()
		if ctrl is not None:
			showPar = getattr(ctrl.par, 'Showasemic', None)
			if showPar is not None and not showPar.eval():
				self._purgeExpired()
				return
		registry = self._registry()
		if registry is None:
			return

		thought = registry.GetCanvasString('gaia/canvas/thought', '')
		if self._checkChanged('thought', thought):
			self._say(thought, 'out')

		tts = registry.GetCanvasString('gaia/canvas/tts/text', '') or registry.GetCanvasString('gaia/canvas/tts', '')
		if self._checkChanged('tts', tts):
			self._say(tts, 'out')

		memory = registry.GetCanvasString('gaia/canvas/lastMemory', '')
		if self._checkChanged('lastMemory', memory):
			self._say(memory, 'out')

		dreamMood = registry.GetCanvasString('gaia/canvas/dream/mood', '')
		dreamSlugs = sorted({
			key.split('/')[4]
			for key in registry.GetCanvasKeys('gaia/canvas/dream/words/')
			if key.endswith('/name') and len(key.split('/')) >= 5
		})
		dreamText = ' '.join(
			registry.GetCanvasString('gaia/canvas/dream/words/%s/name' % slug, slug)
			for slug in dreamSlugs
		)
		if self._checkChanged('dream', dreamMood + '|' + dreamText) and dreamText:
			self._say(dreamText, 'dream')

		# voiceCommands: dynamically-indexed like dream/words/*, but
		# string-valued (no CHOP channel) - GetCanvasKeys closes the
		# TD-side gap flagged in GAIA_INTERFACE.md. Takes the
		# highest-indexed entry, same "most recent" semantics as tts.
		vcIndices = sorted({
			key.split('/')[3]
			for key in registry.GetCanvasKeys('gaia/canvas/voiceCommands/')
			if key.endswith('/text') and len(key.split('/')) >= 4
		}, key=lambda s: (len(s), s))
		if vcIndices:
			latest = vcIndices[-1]
			vcText = registry.GetCanvasString('gaia/canvas/voiceCommands/%s/text' % latest, '')
			if self._checkChanged('voiceCommands', latest + '|' + vcText):
				self._say(vcText, 'in')

		# plant_note: MIDI note -> solfege word, one spark per real pluck
		# (ts changing is the event edge, matching RecordPlantNoteField's
		# own per-burst-commit logic in GaiaRegistryExt).
		note = registry.GetCanvas('gaia/canvas/event/plant_note/note', None)
		ts = registry.GetCanvas('gaia/canvas/event/plant_note/ts', None)
		if note is not None and ts is not None and self._checkChanged('plant_note', ts):
			self._say(self.SOLFEGE[int(note) % 12], 'herb')

		# rune/level_up: {level, class, asset} - confirmed wired
		# end-to-end Gaia-side (2026-08-26) but not yet fired live as of
		# that date. Wired here so it activates automatically the first
		# real level-up arrives, no further action needed either side.
		level = registry.GetCanvas('gaia/canvas/event/level_up/level', None)
		runeWord = registry.GetCanvasString('gaia/canvas/event/level_up/asset', '') or registry.GetCanvasString('gaia/canvas/event/level_up/class', '')
		if level is not None and runeWord and self._checkChanged('level_up', '%s|%s' % (level, runeWord)):
			self._say(runeWord, 'rune')

		self._purgeExpired()

	def _purgeExpired(self):
		now = absTime.seconds * 1000.0
		self._sentences = [
			s for s in self._sentences
			if now - s['spawnMs'] < self.WRITE_MS + len(s['glyphs']) * self.STAGGER_MS + s['holdMs'] + s['fadeMs']
		]

	def _toNDC(self, u, v):
		return ((u - 0.5) * self.ORTHO_W, (v - 0.5) * self.ORTHO_H)

	def GetGlyphGeometry(self):
		"""[(ndcPoints, r, g, b, alpha, halfWidthNDC), ...] for every
		visible, partially- or fully-revealed stroke this frame. Called
		every cook by asemic_sop at native frame rate, independent of
		Tick()'s on-change ingestion - see class docstring."""
		engine = self._engine()
		now = absTime.seconds * 1000.0
		out = []
		for s in self._sentences:
			age = now - s['spawnMs']
			ink = s['ink']
			style = self.INK[ink]
			r, g, b = self._inkColor(ink)
			hw = style['width'] * 0.0018
			nLanes = self.LANES.get(ink, 1)
			bandY = style['bandY'] + (s['lane'] - (nLanes - 1) / 2.0) * self.LANE_SPACING
			for wi, glyph in enumerate(s['glyphs']):
				wordAge = age - wi * self.STAGGER_MS
				if wordAge <= 0.0:
					continue
				writeFrac = max(0.0, min(1.0, wordAge / self.WRITE_MS))
				postWrite = wordAge - self.WRITE_MS
				if postWrite <= 0.0:
					alpha = writeFrac
				elif postWrite < style['holdMs']:
					alpha = 1.0
				else:
					alpha = max(0.0, 1.0 - (postWrite - style['holdMs']) / style['fadeMs'])
				if alpha <= 0.0:
					continue
				wordU = 0.05 + wi * 0.09 * glyph['wide']
				for stroke in glyph['strokes']:
					sampled = engine.sample_stroke(stroke)
					count = max(2, int(round(writeFrac * len(sampled))))
					pts = sampled[:count]
					if len(pts) < 2:
						continue
					ndcPts = [self._toNDC(wordU + px * 0.08, bandY + (py - 0.5) * 0.12) for px, py in pts]
					out.append((ndcPts, r, g, b, alpha, hw))
				if writeFrac >= 1.0:
					if glyph.get('dot'):
						dx, dy = self._toNDC(wordU + glyph['dot']['x'] * 0.08, bandY + (glyph['dot']['y'] - 0.5) * 0.12)
						eps = 0.0015
						out.append(([(dx - eps, dy), (dx + eps, dy)], r, g, b, alpha, hw * 1.4))
					if glyph.get('bar'):
						by0 = bandY + 0.07
						p0 = self._toNDC(wordU, by0)
						p1 = self._toNDC(wordU + 0.08 * glyph['wide'], by0)
						out.append(([p0, p1], r, g, b, alpha, hw))
		return out
