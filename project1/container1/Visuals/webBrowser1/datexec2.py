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


def onTableChange(dat):
	
	menuNames = [x.val for x in dat.col('name') if x.row > 0]
	menuLabels = [x.val for x in dat.col('label') if x.row > 0]
	
	parent.WebBrowser.par.Searchpage.menuNames = menuNames
	parent.WebBrowser.par.Searchpage.menuLabels = menuLabels
	parent.WebBrowser.par.Searchpage.default = menuNames[0]
			
	return