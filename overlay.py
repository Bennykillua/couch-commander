from pathlib import Path

import AppKit
import objc
from Foundation import NSObject, NSTimer
from PyObjCTools import AppHelper


ASSET_DIR = Path(__file__).parent / "couch-commander-assets"
PANEL_WIDTH = 360
PANEL_HEIGHT = 110
PANEL_RADIUS = 28
SHOW_SECONDS = 2.0
TEST_SHOW_SECONDS = 3.0


class MintBackgroundView(AppKit.NSView):
    def drawRect_(self, rect):
        bounds = self.bounds()
        path = AppKit.NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            bounds, PANEL_RADIUS, PANEL_RADIUS
        )
        gradient = AppKit.NSGradient.alloc().initWithStartingColor_endingColor_(
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
                186 / 255, 236 / 255, 212 / 255, 1
            ),
            AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
                226 / 255, 240 / 255, 230 / 255, 1
            ),
        )
        gradient.drawInBezierPath_angle_(path, -90)


class NearestNeighborImageView(AppKit.NSImageView):
    def drawRect_(self, rect):
        image = self.image()
        if image is None:
            return
        context = AppKit.NSGraphicsContext.currentContext()
        context.setImageInterpolation_(AppKit.NSImageInterpolationNone)
        image.drawInRect_fromRect_operation_fraction_(
            self.bounds(),
            AppKit.NSZeroRect,
            AppKit.NSCompositingOperationSourceOver,
            1.0,
        )


class ToastController(NSObject):
    def init(self):
        self = objc.super(ToastController, self).init()
        if self is None:
            return None
        self.panel = None
        self.dismiss_timer = None
        self.fade_timer = None
        self.fade_started = None
        self.fade_duration = 0.18
        self._build_panel()
        return self

    def _build_panel(self):
        style = AppKit.NSWindowStyleMaskBorderless | AppKit.NSWindowStyleMaskNonactivatingPanel
        self.panel = AppKit.NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            AppKit.NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT),
            style,
            AppKit.NSBackingStoreBuffered,
            False,
        )
        self.panel.setReleasedWhenClosed_(False)
        self.panel.setFloatingPanel_(True)
        self.panel.setHidesOnDeactivate_(False)
        self.panel.setBecomesKeyOnlyIfNeeded_(True)
        self.panel.setIgnoresMouseEvents_(True)
        self.panel.setHasShadow_(True)
        self.panel.setLevel_(AppKit.NSScreenSaverWindowLevel)
        self.panel.setCollectionBehavior_(
            AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
            | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary
            | AppKit.NSWindowCollectionBehaviorStationary
        )
        self.panel.setOpaque_(False)
        self.panel.setBackgroundColor_(AppKit.NSColor.clearColor())

        content = AppKit.NSView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT)
        )
        content.setWantsLayer_(True)
        content.layer().setCornerRadius_(PANEL_RADIUS)
        content.layer().setMasksToBounds_(True)
        self.background = MintBackgroundView.alloc().initWithFrame_(
            AppKit.NSMakeRect(0, 0, PANEL_WIDTH, PANEL_HEIGHT)
        )
        self.background.setAutoresizingMask_(
            AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable
        )
        content.addSubview_(self.background)

        self.image_view = NearestNeighborImageView.alloc().initWithFrame_(
            AppKit.NSMakeRect(16, 12, 112, 86)
        )
        self.image_view.setImageScaling_(AppKit.NSImageScaleProportionallyUpOrDown)
        self.image_view.setImageAlignment_(AppKit.NSImageAlignCenter)
        content.addSubview_(self.image_view)

        self.title_field = self._make_label(
            AppKit.NSMakeRect(142, 62, 200, 26), 19, True, "#20332A"
        )
        self.subtitle_field = self._make_label(
            AppKit.NSMakeRect(142, 20, 200, 38), 13, False, "#66736C"
        )
        self.subtitle_field.setLineBreakMode_(AppKit.NSLineBreakByWordWrapping)
        self.subtitle_field.setUsesSingleLineMode_(False)
        self.subtitle_field.setMaximumNumberOfLines_(2)
        self.subtitle_field.cell().setWraps_(True)
        self.subtitle_field.cell().setTruncatesLastVisibleLine_(False)
        content.addSubview_(self.title_field)
        content.addSubview_(self.subtitle_field)
        self.panel.setContentView_(content)
        self._position_panel()

    def _make_label(self, frame, size, bold, hex_color):
        field = AppKit.NSTextField.alloc().initWithFrame_(frame)
        field.setBezeled_(False)
        field.setDrawsBackground_(False)
        field.setEditable_(False)
        field.setSelectable_(False)
        field.setTextColor_(self._color(hex_color))
        font = (
            AppKit.NSFont.boldSystemFontOfSize_(size)
            if bold
            else AppKit.NSFont.systemFontOfSize_(size)
        )
        field.setFont_(font)
        field.setLineBreakMode_(AppKit.NSLineBreakByTruncatingTail)
        return field

    @staticmethod
    def _color(hex_color):
        value = hex_color.lstrip("#")
        red, green, blue = (int(value[index : index + 2], 16) / 255 for index in (0, 2, 4))
        return AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(
            red, green, blue, 1
        )

    def _position_panel(self):
        screen = AppKit.NSScreen.mainScreen()
        if screen is None:
            raise RuntimeError("No main screen is available for the overlay.")
        visible = screen.visibleFrame()
        width = min(PANEL_WIDTH, visible.size.width)
        height = min(PANEL_HEIGHT, visible.size.height)
        x = visible.origin.x + visible.size.width - width - 24
        y = visible.origin.y + visible.size.height - height - 24
        x = max(visible.origin.x, min(x, visible.origin.x + visible.size.width - width))
        y = max(visible.origin.y, min(y, visible.origin.y + visible.size.height - height))
        self.panel.setContentSize_(AppKit.NSMakeSize(width, height))
        self.panel.setFrameOrigin_(AppKit.NSMakePoint(x, y))
        frame = self.panel.frame()
        inside_visible = (
            frame.origin.x >= visible.origin.x
            and frame.origin.y >= visible.origin.y
            and frame.origin.x + frame.size.width <= visible.origin.x + visible.size.width
            and frame.origin.y + frame.size.height <= visible.origin.y + visible.size.height
        )
        print(
            "Overlay frame: "
            f"x={frame.origin.x:.0f}, y={frame.origin.y:.0f}, "
            f"w={frame.size.width:.0f}, h={frame.size.height:.0f}; "
            f"visibleFrame={visible}; withinVisibleFrame={inside_visible}; "
            f"level={self.panel.level()}; mainThread={AppKit.NSThread.isMainThread()}",
            flush=True,
        )

    def show_state(self, state, title=None, subtitle="", text=None, duration=None):
        images = {
            "wake": "sloth_listen.png",
            "done": "sloth_done.png",
            "none": "sloth_sleep.png",
            "cancelled": "sloth_sleep.png",
        }
        titles = {
            "wake": "What should I do?",
            "none": "Didn’t catch that",
            "cancelled": "Didn’t catch that",
        }
        subtitles = {
            "wake": "say your command now",
            "none": "try again",
            "cancelled": "try again",
        }
        image_path = ASSET_DIR / images.get(state, "sloth_sleep.png")
        image = AppKit.NSImage.alloc().initWithContentsOfFile_(str(image_path))
        self.image_view.setImage_(image)
        self.title_field.setStringValue_(title or titles.get(state, "Couch Commander"))
        if state == "done" and text:
            subtitle = text
        if state == "done" and subtitle:
            subtitle = f'“{subtitle}”'
        self.subtitle_field.setStringValue_(subtitle or subtitles.get(state, ""))
        self._position_panel()

        if self.dismiss_timer is not None:
            self.dismiss_timer.invalidate()
            self.dismiss_timer = None
        if self.fade_timer is not None:
            self.fade_timer.invalidate()
            self.fade_timer = None

        self.panel.setAlphaValue_(0)
        self.panel.orderFrontRegardless()
        self._start_fade_in()
        print(
            f"Overlay shown: state={state}, frame={self.panel.frame()}, "
            f"visible={self.panel.isVisible()}, mainThread={AppKit.NSThread.isMainThread()}",
            flush=True,
        )
        if state == "wake":
            return
        duration = TEST_SHOW_SECONDS if duration is None and state == "test" else duration
        duration = SHOW_SECONDS if duration is None else duration
        self.dismiss_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            duration,
            self,
            "dismissToast:",
            None,
            False,
        )

    def _start_fade_in(self):
        self.fade_started = AppKit.NSProcessInfo.processInfo().systemUptime()
        self.fade_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1 / 60,
            self,
            "fadeInTick:",
            None,
            True,
        )

    def fadeInTick_(self, timer):
        elapsed = AppKit.NSProcessInfo.processInfo().systemUptime() - self.fade_started
        alpha = min(1.0, elapsed / self.fade_duration)
        self.panel.setAlphaValue_(alpha)
        if alpha >= 1:
            timer.invalidate()
            self.fade_timer = None

    def dismissToast_(self, timer):
        timer.invalidate()
        self.dismiss_timer = None
        self.fade_started = AppKit.NSProcessInfo.processInfo().systemUptime()
        self.fade_timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1 / 60,
            self,
            "fadeOutTick:",
            None,
            True,
        )

    def fadeOutTick_(self, timer):
        elapsed = AppKit.NSProcessInfo.processInfo().systemUptime() - self.fade_started
        alpha = max(0.0, 1.0 - elapsed / self.fade_duration)
        self.panel.setAlphaValue_(alpha)
        if alpha <= 0:
            timer.invalidate()
            self.fade_timer = None
            self.panel.orderOut_(None)


def create_toast_controller():
    return ToastController.alloc().init()


def post_toast(controller, state, **details):
    AppHelper.callAfter(controller.show_state, state, **details)
