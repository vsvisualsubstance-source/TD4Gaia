_prev = {'levelup': None, 'dreamnew': None}

def onCook(scriptOp):
	osc = op('../canvas_bridge')  # gaia/canvas/* moved to port 7001, 2026-08-04
	ctrl = op('event_ctrl')

	def aggregate(prefix):
		total = 0.0
		if osc is not None:
			for ch in osc.chans(prefix + '/*'):
				total += ch.eval()
		return total

	# Real OSC one-shot events (never fired yet - see project notes) OR a
	# manual toggle flip on event_ctrl. Both routes go through the same
	# prev-vs-current change detector below, tolerant of either a pulse or
	# an incrementing counter encoding since the real wire format is unknown.
	levelup_raw = aggregate('gaia/canvas/event/level_up') + (1000.0 if ctrl.par.Simlevelup.eval() else 0.0)
	dreamnew_raw = aggregate('gaia/canvas/event/dream_new') + (1000.0 if ctrl.par.Simdreamnew.eval() else 0.0)

	levelup_changed = 1.0 if (_prev['levelup'] is not None and levelup_raw != _prev['levelup']) else 0.0
	dreamnew_rose = 1.0 if (_prev['dreamnew'] is not None and dreamnew_raw > _prev['dreamnew']) else 0.0

	_prev['levelup'] = levelup_raw
	_prev['dreamnew'] = dreamnew_raw

	# Manual test path for person_recognized - feeds the registry every
	# frame while the toggle is on, exactly mirroring how the real event
	# re-fires continuously while someone stays recognized. Toggle off
	# lets it decay naturally.
	registry = op('registry')
	if registry is not None and ctrl.par.Simrecognized.eval():
		registry.RecordRecognitionField('person', 'TestPerson')
		registry.RecordRecognitionField('camera', 'salotto')
		registry.RecordRecognitionField('confidence', 0.9)

	# Directly (re)start the dream timer here rather than relying on the
	# Timer CHOP's input-trigger, which was found not to restart reliably
	# once already in the "done" state - explicit Initialize+Start always
	# works regardless of the timer's current state.
	if dreamnew_rose > 0.5:
		timer = op('timer_dream')
		if timer is not None:
			timer.par.initialize.pulse()
			timer.par.start.pulse()

	scriptOp.clear()
	c1 = scriptOp.appendChan('levelup_edge')
	c2 = scriptOp.appendChan('dreamnew_edge')
	scriptOp.numSamples = 1
	c1[0] = levelup_changed
	c2[0] = dreamnew_rose
	return
