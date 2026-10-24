import threading
from pathlib import Path

import AppKit
import rumps
from PyObjCTools import AppHelper

import listen
from overlay import create_toast_controller


ASSET_DIR = Path(__file__).parent / "couch-commander-assets"
STATUS_ICON_SIZE = 18


class CouchCommanderApp(rumps.App):
    def __init__(self):
        appkit_app = AppKit.NSApplication.sharedApplication()
        appkit_app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
        print(
            "AppKit activation policy set to Accessory "
            f"onMainThread={AppKit.NSThread.isMainThread()}",
            flush=True,
        )
        super().__init__(
            "Couch Commander",
            icon=str(ASSET_DIR / "sloth_sleep.png"),
            template=False,
            quit_button=None,
            menu=["Start listening", "Stop listening", "Test overlay", "Quit"],
        )
        self._scale_status_icon()
        self._toast = None
        self._listener_thread = None
        self._stop_event = None
        self._listener_lock = threading.Lock()

    def _ensure_toast(self):
        """Create the overlay lazily on the main thread.

        rumps never calls applicationDidFinishLaunching_ on rumps.App, so the
        overlay is built the first time it's needed instead.
        """
        if self._toast is not None:
            return self._toast
        if not AppKit.NSThread.isMainThread():
            raise RuntimeError("Overlay controller must be created on the AppKit main thread.")
        AppKit.NSApplication.sharedApplication().setActivationPolicy_(
            AppKit.NSApplicationActivationPolicyAccessory
        )
        self._toast = create_toast_controller()
        print("Overlay controller created on AppKit main thread.", flush=True)
        return self._toast

    def _show_toast(self, state, details):
        try:
            self._ensure_toast().show_state(state, **details)
        except Exception as error:
            print(f"Overlay error: {error}", flush=True)

    def post_toast(self, state, **details):
        AppHelper.callAfter(self._show_toast, state, details)

    @rumps.clicked("Test overlay")
    def test_overlay(self, _sender):
        AppHelper.callAfter(self._show_test_overlay)

    def _show_test_overlay(self):
        if not AppKit.NSThread.isMainThread():
            raise RuntimeError("Overlay must be shown on the AppKit main thread.")
        self._ensure_toast().show_state(
            "test",
            title="Overlay test",
            subtitle="Visible for 3 seconds",
            duration=3.0,
        )

    def _scale_status_icon(self):
        image = self._icon_nsimage
        if image is not None:
            image.setSize_(AppKit.NSMakeSize(STATUS_ICON_SIZE, STATUS_ICON_SIZE))

    @rumps.clicked("Start listening")
    def start_listening(self, _sender):
        with self._listener_lock:
            if self._listener_thread is not None and self._listener_thread.is_alive():
                return
            stop_event = threading.Event()
            worker = threading.Thread(
                target=self._run_listener,
                args=(stop_event,),
                name="CouchCommanderListener",
                daemon=True,
            )
            self._stop_event = stop_event
            self._listener_thread = worker
            worker.start()
        print("Starting voice listener.", flush=True)

    @rumps.clicked("Stop listening")
    def stop_listening(self, _sender):
        with self._listener_lock:
            stop_event = self._stop_event
        if stop_event is not None:
            stop_event.set()
            print("Stopping voice listener.", flush=True)

    def _run_listener(self, stop_event):
        try:
            listen.listen_forever(
                debug=False,
                stop_event=stop_event,
                on_state=self.post_toast,
            )
        except Exception as error:
            print(f"Voice listener stopped with an error: {error}", flush=True)
        finally:
            AppHelper.callAfter(self._listener_stopped, stop_event)

    def _listener_stopped(self, stop_event):
        with self._listener_lock:
            if self._stop_event is stop_event:
                self._listener_thread = None
                self._stop_event = None
        print("Voice listener stopped.", flush=True)

    @rumps.clicked("Quit")
    def quit_app(self, _sender):
        self.stop_listening(None)
        rumps.quit_application()


def main():
    CouchCommanderApp().run()


if __name__ == "__main__":
    main()
