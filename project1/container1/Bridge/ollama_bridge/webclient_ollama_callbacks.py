"""
webclientDAT callbacks

POST to Ollama's /api/generate (stream=false -> single JSON object response),
bypassing Node-RED for the live demo. Parses 'response' and writes it into
raw_ollama, which text_ollama displays.
"""
from typing import Dict, Any
import json

def onConnect(dat: webclientDAT, id: int):
	return

def onDisconnect(dat: webclientDAT, id: int):
	return

def onResponse(dat: webclientDAT, statusCode: Dict[str, Any],
			   headerDict: Dict[str, str], data: bytes, id: int):
	if statusCode['code'] != 200:
		try:
			body = data.decode('utf-8', errors='replace')
		except Exception:
			body = ''
		op('raw_ollama').text = 'Errore Ollama: HTTP %s %s - %s' % (statusCode['code'], statusCode.get('message', ''), body)
		return
	try:
		obj = json.loads(data.decode('utf-8'))
	except Exception as e:
		op('raw_ollama').text = 'Errore nel parsing della risposta Ollama: %s' % e
		return
	op('raw_ollama').text = obj.get('response', '(risposta vuota)')
	return

def onError(dat: webclientDAT, id: int, url: str, error: Exception):
	debug(error)
	op('raw_ollama').text = 'Errore di connessione a Ollama (%s): %s' % (url, error)
	return
