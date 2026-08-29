def onCook(scriptOp):
	t = op('timer_dream')
	ctrl = op('event_ctrl')

	frac = t['timer_fraction'].eval()
	running = t['running'].eval()
	done = t['done'].eval()

	fade = ctrl.par.Dreamfadeseconds.eval()
	hold = ctrl.par.Dreamholdseconds.eval()
	total = fade * 2.0 + hold
	fade_in_frac = (fade / total) if total > 0 else 0.0
	hold_end_frac = ((fade + hold) / total) if total > 0 else 1.0

	if running < 0.5:
		# Covers both "never started" (ready) and "finished" (done) states -
		# the dream must be fully hidden in either case, not just pre-start.
		vis = 0.0
	elif frac < fade_in_frac:
		vis = (frac / fade_in_frac) if fade_in_frac > 0 else 1.0
	elif frac < hold_end_frac:
		vis = 1.0
	else:
		remaining_frac = 1.0 - hold_end_frac
		vis = 1.0 - ((frac - hold_end_frac) / remaining_frac) if remaining_frac > 0 else 0.0
		vis = max(0.0, vis)

	scriptOp.clear()
	c = scriptOp.appendChan('dreamvis')
	scriptOp.numSamples = 1
	c[0] = vis
	return
