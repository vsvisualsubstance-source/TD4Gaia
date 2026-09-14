# me - this DAT.
# 
# dat - the changed DAT
# rows - a list of row indices
# cols - a list of column indices
# cells - the list of cells that have changed content
# prev - the list of previous string contents of the changed cells
# 
# Make sure the corresponding toggle is enabled in the DAT Execute DAT.
# 
# If rows or columns are deleted, sizeChange will be called instead of row/col/cellChange.

def onRowChange(dat, rows):
	for i in rows:
		row = dat.row(i)
		if row[0].val == 'url' and parent.WebBrowser.par.Changeaddress :
			parent.WebBrowser.par.Address = row[1].val
		elif row[0].val == 'error':
			parent.WebBrowser.par.Error = row[1].val
		elif row[0].val == 'error_code':
			parent.WebBrowser.par.Errorcode = row[1].val
		elif row[0].val == 'http_status':
			parent.WebBrowser.par.Httpstatus = row[1].val
	return