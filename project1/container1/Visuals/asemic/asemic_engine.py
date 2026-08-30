"""
Deterministic word -> glyph algorithm - verbatim port of the reference
implementation confirmed in GAIA_INTERFACE.md ("Vocabolario Asemico",
2026-08-26), itself ported from pi/screen/asemic_engine.py in the Gaia
repo (parity-tested there against web/asemic.js). Same seed -> same
glyph on every surface - do not "improve" fnv1a/mulberry32/glyph_for,
per the doc's own rule: "L'algoritmo E' la lingua".

sample_stroke() is NOT a verbatim port (the reference body lives in the
separate Gaia repo, not reachable from this TD project) - it is our own
implementation of the documented technique ("quadratiche verso i punti
medi, per un disegno morbido"): a quadratic Bezier through each
segment's midpoints. This is presentation-only (stroke smoothing); it
does not affect the determinism, which lives entirely in glyph_for's
control points.
"""


def fnv1a(text):
	h = 2166136261
	for ch in text.lower():
		h ^= ord(ch)
		h = (h * 16777619) & 0xFFFFFFFF
	return h


def mulberry32(seed):
	state = seed & 0xFFFFFFFF

	def rnd():
		nonlocal state
		state = (state + 0x6D2B79F5) & 0xFFFFFFFF
		t = state
		t = ((t ^ (t >> 15)) * (t | 1)) & 0xFFFFFFFF
		t = (t ^ ((t + (((t ^ (t >> 7)) * (t | 61)) & 0xFFFFFFFF)) & 0xFFFFFFFF)) & 0xFFFFFFFF
		return ((t ^ (t >> 14)) & 0xFFFFFFFF) / 4294967296

	return rnd


def glyph_for(word):
	"""Same construction (same rnd() call ORDER) as web/asemic.js."""
	rnd = mulberry32(fnv1a(word.lower()))
	strokes = []
	n_strokes = min(5, 2 + len(word) // 3 + (1 if rnd() < 0.3 else 0))
	for _ in range(n_strokes):
		pts = []
		n_pts = 2 + int(rnd() * 3)
		x = 0.05 + rnd() * 0.30
		y = 0.18 + rnd() * 0.64
		for _i in range(n_pts):
			pts.append((x, y))
			x += 0.16 + rnd() * 0.34
			y = max(0.04, min(0.96, y + (rnd() - 0.5) * 0.75))
		strokes.append(pts)
	# The ternary short-circuits in JS - the diacritic-point rnd() calls
	# are consumed ONLY if the first test passes. Python's conditional
	# expression short-circuits the same way, so this reproduces it.
	dot = {'x': 0.2 + rnd() * 0.6, 'y': 0.06 if rnd() < 0.5 else 0.97} if rnd() < 0.28 else None
	return {'strokes': strokes, 'dot': dot, 'bar': rnd() < 0.18, 'wide': 0.75 + rnd() * 0.45}


def sample_stroke(pts, samples_per_segment=8):
	"""Smooths an ordered control-point list into a denser polyline using
	quadratic Beziers through each segment's midpoint. Not a verbatim
	port - see module docstring."""
	if len(pts) < 3:
		return list(pts)
	mids = [((pts[i][0] + pts[i + 1][0]) / 2.0, (pts[i][1] + pts[i + 1][1]) / 2.0) for i in range(len(pts) - 1)]
	out = [pts[0]]
	for i in range(len(mids) - 1):
		p0, p1, p2 = mids[i], pts[i + 1], mids[i + 1]
		for t in range(1, samples_per_segment + 1):
			u = t / float(samples_per_segment)
			x = (1 - u) ** 2 * p0[0] + 2 * (1 - u) * u * p1[0] + u ** 2 * p2[0]
			y = (1 - u) ** 2 * p0[1] + 2 * (1 - u) * u * p1[1] + u ** 2 * p2[1]
			out.append((x, y))
	out.append(pts[-1])
	return out
