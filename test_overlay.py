"""Show the sloth overlay once, with no menu bar or voice involved.

Run: python test_overlay.py
"""
import AppKit
from PyObjCTools import AppHelper

from overlay import create_toast_controller

app = AppKit.NSApplication.sharedApplication()
app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)

state = {}

def step(i):
    toast = state["toast"]
    if i == 0:
        toast.show_state("wake")
        AppHelper.callLater(2.0, step, 1)
    elif i == 1:
        toast.show_state("done", title="Rewinding 30s", text="abeg go back small")
        AppHelper.callLater(2.5, step, 2)
    elif i == 2:
        toast.show_state("none")
        AppHelper.callLater(3.0, step, 3)
    else:
        print("Overlay test finished.", flush=True)
        AppHelper.stopEventLoop()

def start():
    print("Creating overlay...", flush=True)
    state["toast"] = create_toast_controller()
    step(0)

AppHelper.callAfter(start)
AppHelper.runEventLoop()
