"""
List COMP Callbacks — UI per devices_table/td_service_control.

Accoppiamento deliberato e stretto con l'ordine colonne di devices_table
(vedi td_service_control.py:_rebuild_table): device_id, name, stanza,
role, service, state, offline — indici 0..6 hardcoded qui di proposito,
non tramite nome colonna (piu' fragile su un Table DAT). Se l'ordine
cambia in _rebuild_table, aggiornare _COL qui.

Aggiunge 3 colonne azione dopo i dati (Play/Stop/Restart), clickabili via
onRadio (fires UNA VOLTA per click, non ogni frame come onSelect).
Riga 0 = header (devices_table la fornisce gia' per le colonne dati,
qui aggiungiamo solo le 3 header vuote per le azioni).

Refresh: control_lifecycle.py pulsa reset ogni volta che
td_service_control.module.drain_inbox() segnala un cambiamento nella
tabella — onInitTable/onInitCell rigirano allora su tutte le celle con i
dati aggiornati.

Larghezza colonna (onInitCol) E altezza riga (onInitRow) ESPLICITE: il
default di TD per una listCOMP e' troppo stretto/basso per fontSizeX=13,
causando testo compresso/sovrapposto. Vanno impostate entrambe insieme.

NOTA STRUTTURALE IMPORTANTE (causa REALE della perdita di contenuto
ripetuta, trovata 2026-08-05): il vecchio container si chiamava
"gaia_control_panel", era stato taggato come tox esterno indipendente in
una sessione precedente e quel file venne poi cancellato (pulizia per
git). Rinominarlo in "ui_panel" NON e' bastato da solo: la vera causa era
che `externalize_op` su un COMP GIA' taggato (come gaia_control, il
genitore) e' un NO-OP silenzioso se richiamato di nuovo -- riporta
"success" ma NON riscrive il file .tox sul disco (verificato: mtime del
file fermo a 1h30 prima nonostante piu' chiamate "riuscite"). Ogni
project.save()/restart_td ricaricava quindi la vecchia .tox con dentro
ancora "gaia_control_panel". Fix reale: usare save_externalization()
(forza la riscrittura) invece di externalize_op() ogni volta che un
genitore GIA' taggato deve ri-sincronizzare le modifiche di un figlio.
Se in futuro un COMP tox-tracciato sembra "dimenticare" le modifiche,
controllare il mtime del file .tox -- se e' piu' vecchio dell'ultima
modifica, e' questo bug, non un problema di annidamento o di nome.
"""

_COL = {"device_id": 0, "name": 1, "stanza": 2, "role": 3, "service": 4, "state": 5, "offline": 6}
_ACTION_LABELS = ["Play", "Stop", "Restart"]
_ACTION_NAMES  = ["enable", "disable", "restart"]
_COL_WIDTHS = [170, 150, 110, 110, 150, 100, 90, 90, 90, 90]  # 7 colonne dati + 3 azione
_ROW_HEIGHT = 30
_FONT_SIZE = 13


def _data_cols():
    table = op('../devices_table')
    return table.numCols if table is not None else len(_COL)


def onInitCell(comp: listCOMP, row: int, col: int,
               attribs: 'ListAttribute'):
    table = op('../devices_table')
    ncols = _data_cols()
    attribs.fontSizeX = _FONT_SIZE
    attribs.wordWrap = False
    attribs.textOffsetX = 6
    if table is None or row >= table.numRows:
        attribs.text = ''
        return
    if col < ncols:
        attribs.text = str(table[row, col])
        if row == 0:
            attribs.fontBold = True
            attribs.bgColor = (0.2, 0.2, 0.2, 1)
        else:
            attribs.bgColor = (0.11, 0.11, 0.11, 1) if row % 2 == 0 else (0.15, 0.15, 0.15, 1)
            if _COL.get('offline') == col and str(table[row, col]) == 'True':
                attribs.textColor = (1, 0.4, 0.4, 1)
        return
    action_idx = col - ncols
    if action_idx >= len(_ACTION_LABELS):
        attribs.text = ''
        return
    if row == 0:
        attribs.text = ''
        attribs.bgColor = (0.2, 0.2, 0.2, 1)
        return
    attribs.text = _ACTION_LABELS[action_idx]
    attribs.textJustify = JustifyType.CENTER
    attribs.bgColor = [(0.15, 0.4, 0.15, 1), (0.4, 0.15, 0.15, 1), (0.35, 0.3, 0.1, 1)][action_idx]
    return


def onInitTable(comp: listCOMP, attribs: 'ListAttribute'):
    return


def onInitRow(comp: listCOMP, row: int, attribs: 'ListAttribute'):
    attribs.rowHeight = _ROW_HEIGHT
    return


def onInitCol(comp: listCOMP, col: int, attribs: 'ListAttribute'):
    if col < len(_COL_WIDTHS):
        attribs.colWidth = _COL_WIDTHS[col]
    return


def onRollover(comp: listCOMP, row: int, col: int, coords, prevRow: int,
               prevCol: int, prevCoords):
    return


def onSelect(comp: listCOMP, startRow: int, startCol: int, startCoords,
             endRow: int, endCol: int, endCoords, start, end):
    return


def onRadio(comp: listCOMP, row: int, col: int, prevRow: int, prevCol: int):
    if row == 0:
        return
    table = op('../devices_table')
    if table is None or row >= table.numRows:
        return
    ncols = _data_cols()
    action_idx = col - ncols
    if action_idx < 0 or action_idx >= len(_ACTION_NAMES):
        return
    device_id = str(table[row, _COL['device_id']])
    service = str(table[row, _COL['service']])
    control = op('../td_service_control')
    if control is not None:
        control.module.send_command(device_id, service, _ACTION_NAMES[action_idx])
    return


def onFocus(comp: listCOMP, row: int, col: int, prevRow: int, prevCol: int):
    return


def onEdit(comp: listCOMP, row: int, col: int, val: str):
    return
