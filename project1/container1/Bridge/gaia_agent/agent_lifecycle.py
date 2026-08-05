def onCreate():
	op('gaia_device_agent').module.start()
	return

# NOTA (fix 2026-08-05): onStart RIMOSSO da qui apposta. Il toggle "Start"
# non sopravvive al roundtrip .tox di questo COMP (verificato dal vivo piu'
# volte: torna sempre a False dopo un reload), quindi il trigger per il
# vero avvio di TD vive altrove, in Bridge/gaia_startup (NON esternalizzato,
# fuori da qualunque sottoalbero tox) che chiama .module.start() su questo
# stesso modulo. onCreate qui resta per la ricreazione a runtime
# (project.save() strip/restore, copia/incolla) -- quel toggle invece regge.

def onFrameStart(frame):
	op('gaia_device_agent').module.drain_inbox()
	return

def onExit():
	op('gaia_device_agent').module.stop()
	return
