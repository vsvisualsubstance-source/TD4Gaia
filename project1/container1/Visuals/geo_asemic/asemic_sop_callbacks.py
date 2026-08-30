"""
Script SOP Callbacks

me - this DAT

scriptOp - the OP which is cooking
"""


def onCook(scriptOp: scriptSOP):
	"""
	Builds a thickened ribbon (quad strip) per visible, partially- or
	fully-revealed asemic glyph stroke this frame. Real geometry instead
	of GL line width - line width is unreliable across render backends
	(notably clamped to 1px on macOS Metal, this project's target).

	Topology only truly changes when AsemicExt spawns a new sentence
	(on-change ingestion in asemic.Tick()); the per-point reveal/alpha/
	dash-length recompute here is cheap float math run every cook for a
	smooth native-framerate write animation, per GAIA_INTERFACE.md
	"Vocabolario Asemico"'s tick/reveal split.

	NOTE: a plain relative op('../../asemic') resolves to None from
	inside a Script SOP's cook specifically (confirmed empirically -
	works fine from every other callback DAT type in this project, and
	from a plain execute_python call). parent(2) is the reliable fix.
	"""
	scriptOp.clear()
	scriptOp.pointAttribs.create('Cd')
	asemic = parent(2).op('asemic')
	if asemic is None:
		return
	asemic.Tick()
	for pts, r, g, b, alpha, hw in asemic.GetGlyphGeometry():
		_appendRibbon(scriptOp, pts, r, g, b, alpha, hw)
	return


def _appendRibbon(scriptOp, pts, r, g, b, alpha, hw):
	n = len(pts)
	if n < 2:
		return
	col = (r, g, b, alpha)
	for i in range(n - 1):
		x0, y0 = pts[i]
		x1, y1 = pts[i + 1]
		dx, dy = x1 - x0, y1 - y0
		length = (dx * dx + dy * dy) ** 0.5
		if length < 1e-6:
			continue
		nx, ny = -dy / length * hw, dx / length * hw
		quad = [
			(x0 - nx, y0 - ny),
			(x0 + nx, y0 + ny),
			(x1 + nx, y1 + ny),
			(x1 - nx, y1 - ny),
		]
		poly = scriptOp.appendPoly(4, closed=True, addPoints=True)
		for vi, (px, py) in enumerate(quad):
			poly[vi].point.P = (px, py, 0.0)
			poly[vi].point.Cd = col
	return


def onGetCookLevel(scriptOp: scriptSOP) -> CookLevel:
	"""Every frame - the write/hold/fade animation needs native
	framerate; topology-rebuild cost is bounded by AsemicExt's
	on-change gate, not by this cook level."""
	return CookLevel.ALWAYS
