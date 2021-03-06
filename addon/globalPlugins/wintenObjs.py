# Windows 10 controls repository
# Copyright 2015-2016 Joseph Lee, released under GPL.

# Adds handlers for various UIA controls found in Windows 10.
# Also adds interceptors for certain keyboard commands.

import sys
import os
import globalPluginHandler
import appModuleHandler # Huge workaround.
import controlTypes
import UIAHandler
import ui
from NVDAObjects.UIA import UIA
from NVDAObjects.behaviors import Dialog
import api
import speech
import nvwave

# Until NVDA Core ticket 5323 is implemented, have our own find app mod from PID handy.
def getAppModuleFromProcessID(processID):
	"""Finds the appModule that is for the given process ID. The module is also cached for later retreavals.
	@param processID: The ID of the process for which you wish to find the appModule.
	@type processID: int
	@returns: the appModule, or None if there isn't one
	@rtype: appModule 
	"""
	with appModuleHandler._getAppModuleLock:
		mod=appModuleHandler.runningTable.get(processID)
		if not mod:
			# #5323: Certain executables contain dots as part of its file name.
			appName=appModuleHandler.getAppNameFromProcessID(processID).replace(".","_")
			mod=appModuleHandler.fetchAppModule(processID,appName)
			if not mod:
				raise RuntimeError("error fetching default appModule")
			appModuleHandler.runningTable[processID]=mod
	return mod

# Looping selectors are used in apps such as Alarms and Clock and Windows Update to select time values.
class LoopingSelectorItem(UIA):

	def event_UIA_elementSelected(self):
		speech.cancelSpeech()
		api.setNavigatorObject(self)
		self.reportFocus()

# Tell Search UI app module to silence NVDA while the following is happenig.
letCortanaListen = False

# We know the following elements are dialogs.
wintenDialogs=("Shell_Dialog", "Popup")

# Extra UIA constants
UIA_ControllerForPropertyId = 30104

# Search fields.
# Some of them raise controller for event, an event fired if another UI element depends on this control.
class SearchField(UIA):

	def event_UIA_controllerFor(self):
		# Only useful if suggestions appear and disappear.
		focus = api.getFocusObject()
		focusControllerFor = focus.controllerFor
		if len(focusControllerFor)>0:
			nvwave.playWaveFile(os.path.join(os.path.dirname(__file__), "suggestion.wav"))
		else:
			# Manually locate live region until NVDA Core implements this.
			obj = focus
			while obj is not None:
				if isinstance(obj, UIA) and obj.UIAElement.cachedClassName == "Popup":
					ui.message(obj.description)
					return
				obj = obj.next
			nvwave.playWaveFile(os.path.join(os.path.dirname(__file__), "suggestion1.wav"))

# General suggestions item handler
# A testbed for NVDA Core ticket 6241.
class SuggestionsListItem(UIA):

	def event_UIA_elementSelected(self):
		focusControllerFor=api.getFocusObject().controllerFor
		if len(focusControllerFor)>0 and focusControllerFor[0].appModule is self.appModule and self.name:
			speech.cancelSpeech()
			api.setNavigatorObject(self)
			self.reportFocus()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def __init__(self):
		super(GlobalPlugin, self).__init__()
		# Hack: Some executables, particular UWA apps have a dot in the middle.
		# Therefore coerce the app module handler to use the modified routine above.
		appModuleHandler.getAppModuleFromProcessID = getAppModuleFromProcessID
		# Cortana listening mode command has changed in Redstone build 14383.
		if sys.getwindowsversion().build >= 14383:
			self.bindGesture("kb:windows+shift+c", "voiceActivation")
		else:
			self.bindGesture("kb:windows+c", "voiceActivation")
		# Listen for controller for events (to be removed once NVDA Core itself supports this).
		if UIA_ControllerForPropertyId not in UIAHandler.UIAPropertyIdsToNVDAEventNames:
			UIAHandler.UIAPropertyIdsToNVDAEventNames[UIA_ControllerForPropertyId] = "UIA_controllerFor"
			# Unfortunately, UIA handler must be restarted in order for changes to take effect (ugly hack, but it's a must until a plug-in model is developed).
			UIAHandler.terminate()
			UIAHandler.initialize()

	def chooseNVDAObjectOverlayClasses(self, obj, clsList):
		# NVDA Core ticket 5231: Announce values in time pickers.
		if isinstance(obj, UIA):
			# Handle both Threshold and Redstone looping selector items.
			if obj.role==controlTypes.ROLE_LISTITEM and "LoopingSelectorItem" in obj.UIAElement.cachedClassName:
				clsList.append(LoopingSelectorItem)
			# Windows that are really dialogs.
			elif obj.UIAElement.cachedClassName in wintenDialogs:
				# But some are not dialogs despite what UIA says (for example, search popup in Store).
				if obj.UIAElement.cachedAutomationID != "SearchPopUp":
					clsList.insert(0, Dialog)
			# Search field that does raise controller for event.
			elif obj.UIAElement.cachedClassName == "TextBox" and obj.UIAElement.cachedAutomationID in ("TextBox",):
				clsList.insert(0, SearchField)
			# Suggestions themselves.
			elif obj.role == controlTypes.ROLE_LISTITEM and isinstance(obj.parent, UIA) and obj.parent.UIAElement.cachedAutomationID == "SuggestionsList":
				clsList.insert(0, SuggestionsListItem)

	# Focus announcement hacks.
	def event_gainFocus(self, obj, nextHandler):
		# Never allow WorkerW thread to send gain focus event (seen in Insider builds but was observed in release builds for some).
		if obj.role == controlTypes.ROLE_PANE and obj.appModule.appModuleName == "explorer" and obj.windowClassName == "WorkerW" and obj.name is None:
			return
		# Non-English locales does not fire item selected event for looping selector unless navigator is first set to it.
		if isinstance(obj, UIA) and obj.UIAElement.cachedClassName == "CustomLoopingSelector":
			api.setNavigatorObject(obj.simpleFirstChild)
		nextHandler()

	def script_voiceActivation(self, gesture):
		gesture.send()
		if sys.getwindowsversion().major == 10:
			global letCortanaListen
			letCortanaListen = True

