# me - this DAT
# par - the Par object that has changed
# val - the current value
# prev - the previous value
# 
# Make sure the corresponding toggle is enabled in the Parameter Execute DAT.
import urllib.parse

def onValueChange(par, val, prev):

	# manually changing the address on the component parameters
	if par.name == 'Address':
		currentURL = op('info1')['url',1].val
		if val != currentURL:
			op('webrender1').par.url.mode = ParMode.EXPRESSION

	return

def onPulse(par):

	# go back and forward in the history can be a direct call to the BOM History Object
	if par.name == 'Goback':
		op('webrender1').executeJavaScript('window.history.back()')
	elif par.name == 'Goforward':
		op('webrender1').executeJavaScript('window.history.forward()')
		
	# similarily reloading can be done via BOM Location Object
	elif par.name == 'Reload':
		op('webrender1').executeJavaScript('location.reload()')
		
	# create a url friendly searchterm and push to various locations
	elif par.name == 'Search':
		searchPage = parent.WebBrowser.par.Searchpage.eval()
		searchTerm = urllib.parse.quote_plus(parent.WebBrowser.par.Searchterm.eval())
		
		searchUrl = op('pageSearch').row(searchPage)
		engine = 'https://www.derivative.ca/wiki099/index.php?title=&fulltext=Search&search='
		if searchUrl:
			engine = searchUrl[2].val
			
		parent().par.Address = '{0}{1}'.format(engine,searchTerm)
		
	# send javascript directly to the webpage	
	elif par.name == 'Sendjavascript':
		javaScript = parent.WebBrowser.par.Javascript.eval()
		op('webrender1').executeJavaScript(javaScript)

	# pulse the restart on the webrender TOP in case it stopped responding
	elif par.name == 'Restart':
		op('webrender1').par.autorestartpulse.pulse()

	return
	