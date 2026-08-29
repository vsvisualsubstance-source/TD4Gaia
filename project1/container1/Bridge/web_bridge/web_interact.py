"""
Panel Execute DAT

me - this DAT

panelValue - the PanelValue object that changed
prev - the previous value of the PanelValue object that changed

Make sure the corresponding toggle is enabled in the Panel Execute DAT.
"""

from typing import Any

def onOffToOn(panelValue: PanelValue):
	"""
	Called when a panel value changes from 0 to non-zero.
	"""
	return

def whileOn(panelValue: PanelValue):
	"""
	Called every frame while a panel value is non-zero.
	"""
	return

def onOnToOff(panelValue: PanelValue):
	"""
	Called when a panel value changes from non-zero to 0.
	"""
	return

def whileOff(panelValue: PanelValue):
	"""
	Called every frame while a panel value is 0.
	"""
	return

def onValueChange(panelValue: PanelValue, prev: Any):
	"""
	Called when a panel value changes.

	Forwards web_panel's pointer (u, v, select) into webrender1.interactMouse()
	so the embedded gaia-web page is actually clickable in the viewer/perform
	window, not just displayed. Re-reads all three live values every time any
	one of them changes (rather than acting on panelValue alone) since
	interactMouse() needs a full u/v/button state every call, not a delta.

	Args:
		panelValue: The PanelValue object that changed
		prev: The previous value of the PanelValue object
	"""
	panel = op('web_panel').panel
	op('webrender1').interactMouse(
		panel.u.val,
		panel.v.val,
		left=bool(panel.select.val),
		pixels=False,
	)
	return
