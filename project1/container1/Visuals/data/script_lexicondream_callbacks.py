"""
Script DAT Callbacks

me - this DAT

scriptOp - the OP which is cooking
"""


def onCook(scriptOp: scriptDAT):
	"""
	Builds one row per line of text, one module at a time, each gated by a
	toggle on text_ctrl so the operator can pick what's on screen instead
	of always showing everything at once.

	Lexicon words have no accented/proper-name field (only count+seed), so
	the word text comes from the OSC address slug (accents stripped by
	Gaia for address-safety, e.g. "curiosit" not "curiosita").

	Dream words, thought, tts and lastMemory are plain strings on port
	7001 - read from registry._canvas (canvas_bridge is numeric-only).
	"""
	scriptOp.clear()

	registry = op('../registry')
	canvas = op('../canvas_bridge')
	ctrl = op('../text_ctrl')
	if registry is None or canvas is None:
		return

	def enabled(name, default=True):
		if ctrl is None:
			return default
		p = getattr(ctrl.par, name, None)
		return p.eval() if p is not None else default

	if enabled('Showlexicon'):
		words = {}
		for ch in canvas.chans('gaia/canvas/lexicon/*/count'):
			parts = ch.name.split('/')
			if len(parts) < 5:
				continue
			words[parts[3]] = ch.eval()
		if words:
			top = sorted(words.items(), key=lambda kv: -kv[1])[:5]
			scriptOp.appendRow(['Lessico: ' + ', '.join(w for w, _ in top)])

	if enabled('Showdream'):
		dreamSlugs = sorted({
			ch.name.split('/')[4]
			for ch in canvas.chans('gaia/canvas/dream/words/*/seed')
			if len(ch.name.split('/')) >= 5
		})[:5]
		dreamWords = [
			registry.GetCanvasString('gaia/canvas/dream/words/%s/name' % slug, slug)
			for slug in dreamSlugs
		]
		if dreamWords:
			mood = registry.GetCanvasString('gaia/canvas/dream/mood', '')
			label = 'Ultimo sogno (%s): ' % mood if mood else 'Ultimo sogno: '
			scriptOp.appendRow([label + ', '.join(dreamWords)])

	if enabled('Showthought'):
		thought = registry.GetCanvasString('gaia/canvas/thought', '')
		if thought:
			scriptOp.appendRow(['Pensiero: ' + thought[:90]])

	if enabled('Showtts'):
		# Gaia added a nested gaia/canvas/tts/text (2026-08-04), alongside
		# the original flat gaia/canvas/tts - prefer the new one, fall
		# back to the old for whichever has actually arrived. ttsRoom is
		# null/absent when said via Echo to "all rooms".
		tts = registry.GetCanvasString('gaia/canvas/tts/text', '') or registry.GetCanvasString('gaia/canvas/tts', '')
		if tts:
			room = registry.GetCanvasString('gaia/canvas/ttsRoom', '')
			label = 'Voce (%s): ' % room if room else 'Voce: '
			scriptOp.appendRow([label + tts[:90]])

	if enabled('Showmemory'):
		mem = registry.GetCanvasString('gaia/canvas/lastMemory', '')
		if mem:
			scriptOp.appendRow(['Ricordo: ' + mem[:90]])

	return


def onGetCookLevel(scriptOp: scriptDAT) -> CookLevel:
	"""
	Sets the scriptOp's cook level, the conditions necessary to cause a cook.
	"""
	return CookLevel.ALWAYS
