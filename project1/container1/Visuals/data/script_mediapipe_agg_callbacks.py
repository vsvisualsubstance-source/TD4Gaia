"""
Script CHOP Callbacks

me - this DAT

scriptOp - the OP which is cooking
"""

from typing import Any

# No one detected anywhere -> treat as "at rest" (eyes open), not dim.
EYES_OPEN_FALLBACK = 0.9


def onSetupParameters(scriptOp: scriptCHOP):
	return


def onPulse(par: Any):
	return


def _liveValues(src, pattern, counts):
	vals = []
	for c in src.chans(pattern):
		parts = c.name.split('/')
		room, idx = parts[3], int(parts[6])
		if idx < counts.get(room, 0):
			vals.append(c[0])
	return vals


def onCook(scriptOp: scriptCHOP):
	scriptOp.clear()
	scriptOp.numSamples = 1

	src = scriptOp.inputs[0] if scriptOp.inputs else None
	smiles, mouths, eyes = [], [], []

	if src:
		counts = {c.name.split('/')[3]: c[0] for c in src.chans('gaia/vision/rooms/*/mediapipe/people_count')}
		smiles = _liveValues(src, 'gaia/vision/rooms/*/mediapipe/people/*/smile_score', counts)
		mouths = _liveValues(src, 'gaia/vision/rooms/*/mediapipe/people/*/mouth_open', counts)
		eyes = _liveValues(src, 'gaia/vision/rooms/*/mediapipe/people/*/eyes_open', counts)

	scriptOp.appendChan('global_smile_max').vals = [max(smiles) if smiles else 0.0]
	scriptOp.appendChan('global_mouth_max').vals = [max(mouths) if mouths else 0.0]
	scriptOp.appendChan('global_eyes_min').vals = [min(eyes) if eyes else EYES_OPEN_FALLBACK]
	return


def onGetCookLevel(scriptOp: scriptCHOP) -> CookLevel:
	return CookLevel.AUTOMATIC
