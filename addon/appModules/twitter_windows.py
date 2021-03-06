# WinTenApps/Twitter.windows.py
# Part of Windows 10 App Essentials collection
# Copyright 2015 Joseph Lee, released under GPL.

# Provides workarounds for Twitter app.

import appModuleHandler
import controlTypes
from NVDAObjects.UIA import UIA

class AppModule(appModuleHandler.AppModule):

	def event_NVDAObject_init(self, obj):
		# Somehow, UIA places various Twitter buttons as child of the button itself (quite odd).
		try:
			if isinstance(obj, UIA) and obj.role == controlTypes.ROLE_BUTTON and obj.name == "":
				obj.name = obj.firstChild.name
		except AttributeError:
			pass
