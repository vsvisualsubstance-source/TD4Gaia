"""
spec_text: Specification DAT for text_labels (x, y, text; pixels from the
bottom-left of the 1280x720 panel drawn by glsl_panel).
"""

import textwrap

BARS = ['stress', 'calm', 'social', 'curiosity', 'energy', 'lifeindex']
MAX_WORDS = 9
THOUGHT_WIDTH = 44
THOUGHT_LINES = 9


def chanValue(chop: CHOP, name: str, default: float = 0.0) -> float:
	"""Value of a named channel, or default when the channel is missing."""
	c = chop[name] if chop is not None else None
	return float(c.eval()) if c is not None else default


def statusLine(status: CHOP) -> str:
	"""One-line connection summary from the status input."""
	def flag(name: str, on: str, off: str) -> str:
		return on if chanValue(status, name) > 0.5 else off
	age = chanValue(status, 'msg_age', -1.0)
	last = 'nessun messaggio' if age < 0 else 'ultimo msg %d s fa' % int(age)
	return '   '.join([flag('connected', 'MQTT ok', 'MQTT OFF'),
		flag('agent_connected', 'agent ok', 'agent OFF'),
		flag('mocap_active', 'mocap on', 'mocap off'), last])


def onCook(scriptOp: scriptDAT) -> None:
	scriptOp.clear()
	rows = [['x', 'y', 'text']]
	soul = op('in_soul')
	rows.append([60, 674, 'GAIA  preview'])
	rows.append([470, 674, statusLine(op('in_status'))])

	rows.append([60, 614, 'MOOD'])
	for i, name in enumerate(BARS):
		rows.append([80, 300 - i * 40 + 10, '%s  %.2f' % (name, chanValue(soul, name))])

	rows.append([480, 614, 'PAROLA'])
	rows.append([480, 370, 'PENSIERO'])
	thought = op('in_thought')
	text = thought[0, 0].val.strip() if thought is not None and thought.numRows else ''
	for i, line in enumerate(textwrap.wrap(text, THOUGHT_WIDTH)[:THOUGHT_LINES]):
		rows.append([480, 336 - i * 24, line])

	rows.append([960, 614, 'PAROLE'])
	words = op('in_words')
	if words is not None:
		for i, r in enumerate(words.rows()[1:MAX_WORDS + 1]):
			rows.append([960, 580 - i * 26, '%s  %s' % (r[0].val, r[1].val if len(r) > 1 else '')])

	mocap = op('in_mocap')
	rows.append([960, 290, 'MOCAP  (viso nel frame camera)'])
	rows.append([960, 56, 'volti %d   mani %d   pose %d' % (
		chanValue(mocap, 'faces'), chanValue(mocap, 'hands'), chanValue(mocap, 'poses'))])
	for r in rows:
		scriptOp.appendRow(r)
	return


def onSetupParameters(scriptOp: scriptDAT) -> None:
	return


def onPulse(par: Par) -> None:
	return
