"""
OSC In DAT Callbacks

me - this DAT

peer - a Peer object describing the originating message
  peer.close()	#close the connection
  peer.owner  #the operator to whom the peer belongs
  peer.address	#network address associated with the peer
  peer.port	   #network port associated with the peer
"""

from typing import List, Any

# Everything under /gaia/canvas/... (tick continuous + one-shot events) now
# arrives here on port 7001 (2026-08-04 migration) - oscin1 (port 7000)
# only carries the raw flatten firehose (/gaia/... without canvas) and
# mocap now. Any address here is string-capable, unlike oscin1's CHOP.
_RECOGNIZED_PREFIX = '/gaia/canvas/event/person_recognized/'
_ENROLLED_PREFIX = '/gaia/canvas/event/face_enrolled/'
_PLANT_NOTE_PREFIX = '/gaia/canvas/event/plant_note/'


def onReceiveOSC(dat: oscinDAT, rowIndex: int, message: str, 
				 byteData: bytes, timeStamp: float, address: str, 
				 args: List[Any], peer: Peer):
	"""
	Called when an OSC message is received.

	Args:
		dat: The DAT that received a message
		rowIndex: The row number the message was placed into
		message: ASCII representation of the data
		byteData: Byte array of the message
		timeStamp: Arrival time component of the OSC message
		address: Address component of the OSC message
		args: List of values contained within the OSC message
		peer: Peer object describing the originating message
	"""
	if not args:
		return
	registry = op('registry')
	if registry is None:
		return
	value = args[0]

	if address.startswith('/gaia/canvas/') and not address.startswith('/gaia/canvas/diary/'):
		# Generic store for everything (soul, rooms, lights, bricks,
		# lexicon, dream, thought, tts, lastMemory, ts) - canvas_bridge
		# re-exposes the numeric subset as CHOP channels for existing
		# oscin1-style consumers. diary is EXCLUDED: it's a deeply nested
		# structure (~30 sub-fields x 20 entries = 600+ messages per 2s
		# tick) not meant for display (the doc says so explicitly - use
		# thought/tts/lastMemory/memories for readable text), and storing
		# it unbounded was likely contributing to OSC-volume-related
		# instability.
		registry.RecordCanvasValue(address[1:], value)

	if address.startswith(_RECOGNIZED_PREFIX):
		field = address[len(_RECOGNIZED_PREFIX):]
		registry.RecordRecognitionField(field, value)
	elif address.startswith(_ENROLLED_PREFIX):
		field = address[len(_ENROLLED_PREFIX):]
		registry.RecordEnrollmentField(field, value)
	elif address.startswith(_PLANT_NOTE_PREFIX):
		field = address[len(_PLANT_NOTE_PREFIX):]
		registry.RecordPlantNoteField(field, value)
	return
