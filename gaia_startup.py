"""
Trigger per il vero avvio di TD (apertura .toe) — vive alla RADICE del
progetto (fuori da /project1/container1, l'albero gestito da Embody),
stesso livello di /window1 e /perform, stessa ragione per cui usa path
assoluti (pattern gia' in uso in questo progetto per gli operatori di
radice, vedi /window1.par.winop e /perform.par.winop).

FIX 2026-08-05 (secondo tentativo): un Execute DAT creato DENTRO
Bridge (project1/container1/Bridge) ma mai esternalizzato viene
CANCELLATO dal ciclo strip/restore di Embody e mai ricreato — verificato
dal vivo (la prima versione di questo trigger, dentro Bridge, e' sparita
del tutto al primo restart_td). Fuori dall'albero gestito, esternalizzato
come .tox a se stante (stesso schema di /gaia_control_window), dovrebbe
reggere.

Il toggle "Start" resta un problema noto A PARTE su
gaia_agent/agent_lifecycle e gaia_control/control_lifecycle (dentro i
loro sottoalberi tox annidati, per cui usano onCreate) — qui va
verificato se, essendo un tox indipendente non annidato, sopravvive.

start()/module.start() di entrambi i moduli sono idempotenti (guardia su
_running), quindi chiamarli qui in aggiunta a onCreate e' sicuro.
"""

def onStart():
	op('/project1/container1/Bridge/gaia_agent/gaia_device_agent').module.start()
	op('/project1/container1/Bridge/gaia_control/td_service_control').module.start()
	return
