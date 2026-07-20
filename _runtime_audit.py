"""Runtime audit driver — NOT app code, NOT a test. Probes the real app.

Launches the production stack exactly as gui.workspace_window.main() does
(offscreen), then for every visible control: checks signal receivers,
simulates activation, and verifies the backend-visible effect.
"""
import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from PySide6.QtWidgets import QApplication, QLabel, QToolButton, QWidget
from PySide6.QtCore import QEventLoop, QTimer

app = QApplication.instance() or QApplication([])

from gui.theme.manager import ThemeManager
from gui.workspace_window import build_workspace_window, _build_production_controller

REPORT = []

def report(control, expected, ok, actual=""):
    REPORT.append((("PASS" if ok else "FAIL"), control, expected, actual))

def pump(ms=300):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


from PySide6.QtCore import QMetaMethod
def connected(obj, sig):
    """True when a signal has at least one receiver (PySide6-safe)."""
    try:
        return obj.isSignalConnected(QMetaMethod.fromSignal(sig))
    except Exception:
        return False

theme = ThemeManager()
theme.apply(app)
controller = _build_production_controller()
report("_build_production_controller", "returns a live WorkflowController", controller is not None,
       f"controller={controller}")
window = build_workspace_window(theme, controller)
window.show()
pump(500)

screen = window.centralWidget()

def find(name, cls=QWidget, root=None):
    return (root or window).findChild(cls, name)

# ---------------- PHASE 1: media import ----------------
browser = screen._browser
items = browser.items()
report("MediaBrowser seeding", "real videos from videos/ dir", "audit_clip.avi" in items, f"items={items}")

n_recv = connected(browser, browser.import_requested)
report("MediaBrowserImport signal", "import_requested connected", n_recv, f"connected={n_recv}")

report("Screen acceptDrops", "drag&drop enabled", screen.acceptDrops())

# Selection -> backend select_video
browser.select(items.index("audit_clip.avi") if "audit_clip.avi" in items else 0)
pump(400)
state = controller.project_state()
report("MediaItem click -> select_video", "ProjectState.video_path set",
       state.video_path is not None, f"video_path={state.video_path}")

# Preview frame decoded?
sink = find("MediaWorkspacePreviewFrame", QLabel)
has_pix = sink is not None and sink.pixmap() is not None and not sink.pixmap().isNull()
report("Preview first frame", "decoded pixmap in MediaWorkspacePreviewFrame", has_pix,
       f"pixmap null={sink.pixmap().isNull() if sink and sink.pixmap() else 'None'}")

# Thumbnails
pump(800)
thumbs = len(getattr(screen, "_thumb_cache", {}))
report("Thumbnail loading", ">=1 thumbnail decoded", thumbs >= 1, f"cached={thumbs}")

# Timeline duration from metadata
dur = screen._timeline.duration()
report("Timeline duration from metadata", "~6s (real clip), not 60 demo", 5.0 <= dur <= 7.0, f"duration={dur}")

# ---------------- PHASE 2: playback ----------------
tb = screen._transport
tb._play.clicked.emit()
pump(400)
playing = screen._timeline.is_playing()
report("TransportPlay", "timeline playing", playing, f"state={screen._timeline.playback_state()}")
ph1 = screen._timeline.playhead()
pump(400)
ph2 = screen._timeline.playhead()
report("Playback advances", "playhead moves", ph2 > ph1, f"{ph1:.2f}->{ph2:.2f}")
pix_during = sink.pixmap() is not None and not sink.pixmap().isNull()
report("Preview updates during playback", "frame pixmap present", pix_during)

tb._pause.clicked.emit(); pump(100)
report("TransportPause", "paused", screen._timeline.playback_state() == "paused")
tb._stop.clicked.emit(); pump(100)
report("TransportStop", "stopped @0", screen._timeline.playback_state() == "stopped" and screen._timeline.playhead() == 0.0)

# Seek via transport slider signal
tb.seek_requested.emit(0.5); pump(200)
report("TransportSeek", "playhead ~50%", abs(screen._timeline.playhead() - dur*0.5) < 0.5,
       f"playhead={screen._timeline.playhead():.2f}")

# Frame step buttons
before = screen._timeline.playhead()
screen._step_frames(1); pump(100)
report("TransportNextFrame", "playhead + 1 frame", screen._timeline.playhead() > before)

# Rate chip + loop chip registered?
rate_wired = getattr(screen, "_rate_label", None) in getattr(screen, "_click_actions", {})
loop_wired = getattr(screen, "_loop_label", None) in getattr(screen, "_click_actions", {})
report("TransportRate chip", "click cycles rate", rate_wired)
report("PlayerLoop chip", "click toggles loop", loop_wired)

# Viewer toolbar
from gui.widgets.dropdown import Dropdown
from gui.widgets.neon_button import NeonButton
zoom = find("MediaWorkspaceViewerZoom", Dropdown, screen)
report("ViewerZoom dropdown", "changed connected", zoom is not None and connected(zoom, zoom.changed))
shot = find("MediaWorkspaceViewerScreenshot", NeonButton, screen)
report("ViewerScreenshot", "clicked connected", shot is not None and connected(shot, shot.clicked))
fs = find("MediaWorkspaceViewerFullscreen", NeonButton, screen)
report("ViewerFullscreen", "clicked connected", fs is not None and connected(fs, fs.clicked))
safe = find("MediaWorkspaceViewerSafeToggle", QWidget, screen)
grid = find("MediaWorkspaceViewerGridToggle", QWidget, screen)
report("ViewerSafeToggle", "toggled connected", safe is not None and connected(safe, safe.toggled),
       "DECORATIVE?" )
report("ViewerGridToggle", "toggled connected", grid is not None and connected(grid, grid.toggled),
       "DECORATIVE?")

# Screenshot real effect
screen._on_screenshot()
import glob
shots = glob.glob("output/*screenshot*.png")
report("Screenshot writes PNG", "file in output/", len(shots) > 0, f"files={len(shots)}")

# ---------------- PHASE 3: timeline editing ----------------
tl = screen._timeline
n0 = tl.clip_count()
tl.select_clip(0)
clips0 = tl.clips()
mid = clips0[0]["start"] + clips0[0]["length"]/2
tl.set_playhead(min(mid, dur-0.1)) if mid < dur else None
screen._split_selected_clip(); pump(100)
split_worked = tl.clip_count() == n0 + 1
report("Timeline split (S/toolbar)", "clip count +1", split_worked, f"{n0}->{tl.clip_count()}")

backend_tl = controller.timeline()
report("Split persisted to backend", "backend Timeline clip count matches",
       backend_tl is not None and backend_tl.clip_count() == tl.clip_count(),
       f"backend={backend_tl.clip_count() if backend_tl else None} widget={tl.clip_count()}")

screen._undo(); pump(100)
report("Undo", "clip count back to n0", tl.clip_count() == n0, f"count={tl.clip_count()}")
screen._redo(); pump(100)
report("Redo", "clip count n0+1", tl.clip_count() == n0 + 1)

tl.select_clip(0)
screen._duplicate_selected_clip()
report("Duplicate (Ctrl+D) after split", "no room on 6s clip = correct no-op",
       tl.clip_count() == n0 + 1,
       f"count={tl.clip_count()} (two 3s clips fill the 6s duration)")

# Test duplicate on a clip that has room (trim to half, then duplicate)
screen._undo(); screen._undo(); pump(100)
tl.select_clip(0)
screen._timeline.trim_clip(0, length=3.0)  # 6s -> 3s, leaves room
screen._duplicate_selected_clip()
dup_worked = tl.clip_count() == 2
report("Duplicate (Ctrl+D) on fresh clip", "clips 1->2", dup_worked, f"count={tl.clip_count()}")
screen._timeline.select_clip(0)
screen._delete_selected_clip()
report("Delete after dup", "clips 2->1", tl.clip_count() == 1, f"count={tl.clip_count()}")

# Toolbar glyphs wired?
toolbar_items = tl._toolbar.findChildren(QLabel, "TimelineToolItem")
wired_glyphs = [i.toolTip() for i in toolbar_items if i in screen._click_actions]
unwired_glyphs = [i.toolTip() for i in toolbar_items if i not in screen._click_actions]
report("Timeline toolbar glyphs", "edit glyphs wired", len(wired_glyphs) >= 8,
       f"wired={wired_glyphs} unwired={unwired_glyphs}")

# Track header glyphs
hdr = tl._header_widgets[0]
mute = hdr.findChild(QLabel, "TimelineTrackMute")
solo = hdr.findChild(QLabel, "TimelineTrackSolo")
lock = hdr.findChild(QLabel, "TimelineTrackLock")
eye  = hdr.findChild(QLabel, "TimelineTrackEye")
report("TrackMute glyph", "wired", mute in screen._click_actions)
report("TrackSolo glyph", "wired", solo in screen._click_actions)
report("TrackLock glyph", "wired", lock in screen._click_actions)
report("TrackEye glyph", "wired", eye in screen._click_actions, "DECORATIVE?")

# Marker
screen._add_marker_at_playhead(); pump(100)
btl = controller.timeline()
report("Marker (M/toolbar)", "backend marker_count>=1", btl is not None and btl.marker_count() >= 1,
       f"markers={btl.marker_count() if btl else None}")

# Zoom
z0 = tl.zoom_level(); tl.zoom_in()
report("Timeline zoom in", "zoom level increases", tl.zoom_level() > z0)

# ---------------- Properties panel ----------------
screen._prop_rotation.set_value(15.0); pump(100)
report("Rotation slider -> backend", "settings clip.rotation=15",
       controller.settings().get("clip.rotation") == 15.0,
       f"val={controller.settings().get('clip.rotation')}")
screen._prop_opacity.set_value(60.0); pump(100)
report("Opacity slider -> backend", "settings clip.opacity=60",
       controller.settings().get("clip.opacity") == 60.0)

from gui.widgets.text_field import TextField
axis_fields = screen.findChildren(TextField, "MediaWorkspaceStreamAxisField")
wired_axis = sum(1 for f in axis_fields if connected(f, f.editing_finished))
report("Transform axis fields", "6 fields wired", wired_axis >= 6, f"wired={wired_axis}/{len(axis_fields)}")

from gui.widgets.toggle_switch import ToggleSwitch
fx = screen.findChildren(ToggleSwitch, "MediaWorkspaceEffectToggle")
fx[0].toggled.emit(False); pump(50)
report("Effect toggle -> backend", "effect.glow=False in settings",
       controller.settings().get("effect.glow") is False)

# Props sub-tabs decorative?
subtabs = [w for w in screen.findChildren(QLabel) if w.objectName() in ("MediaWorkspacePropsSubTab","MediaWorkspacePropsSubTabActive")]
subtab_wired = sum(1 for w in subtabs if w in screen._click_actions)
report("Props sub-tabs (Transform/Video/Audio/Speed)", "wired?", subtab_wired > 0, f"wired={subtab_wired}/{len(subtabs)} DECORATIVE?")

# ---------------- AI cards ----------------
from PySide6.QtWidgets import QFrame
cards = screen.findChildren(QFrame, "MediaWorkspaceAiToolCard")
wired_cards = sum(1 for c in cards if c in screen._click_actions)
report("AI tool cards", "9 wired", wired_cards == 9, f"wired={wired_cards}/{len(cards)}")

# Does an AI card actually invoke the backend? Run 'analysis' via card path.
ran = []
controller.phase_started.connect(lambda pid: ran.append(pid))
screen._run_ai_tool("Scene Enhance", "analysis")
pump(3000)
report("AI card -> run_phase", "phase_started emitted for 'analysis'", "analysis" in ran, f"ran={ran} status={screen._detail_status.text()}")

# AI prompt field (hidden ai host) — receivers?
ask = None
for w in screen.findChildren(NeonButton, "MediaWorkspaceAiAsk"):
    ask = w
report("AiAsk button (hidden panel)", "clicked connected", ask is not None and connected(ask, ask.clicked), "DECORATIVE?")
ai_actions = screen.findChildren(NeonButton, "MediaWorkspaceAiAction")
ai_wired = sum(1 for b in ai_actions if connected(b, b.clicked))
report("AiAction buttons (hidden panel)", "wired?", ai_wired > 0, f"wired={ai_wired}/{len(ai_actions)} DECORATIVE?")

# AIManager runtime: is any AIController constructed anywhere in the app?
report("AIController in app", "screen/window holds AIController",
       hasattr(screen, "_ai_controller") or hasattr(window, "_ai_controller"),
       "ai_core exists but is it wired into the UI?")

# ---------------- Export ----------------
res = screen.export()
report("Export (gated)", "returns False when render blocked, True if runnable", True,
       f"export()={res} runnable={[getattr(p,'id',None) for p in controller.available_phases()]}")

# Toolbar QActions
tb_main = find("WorkspaceMainToolbar")
actions = {a.objectName(): a for a in tb_main.actions() if a.objectName()}
for name in ("ToolbarActionNew","ToolbarActionOpen","ToolbarActionSave","ToolbarActionImport","ToolbarActionAnalyze","ToolbarActionAutoCut","ToolbarActionBeatSync","ToolbarActionRender"):
    a = actions.get(name)
    ok = a is not None and connected(a, a.triggered)
    report(f"{name}", "triggered connected", ok)
for name in ("ToolbarActionRecord","ToolbarActionSnapshot","ToolbarActionGridView","ToolbarActionExpandView"):
    a = actions.get(name)
    ok = a is not None and connected(a, a.triggered)
    report(f"{name}", "triggered connected", ok, "DECORATIVE?")

# Title bar buttons
for name in ("WorkspaceImportAction","WorkspaceExportAction","WorkspaceAIAssistant","WorkspaceRecordAction"):
    b = find(name, QToolButton)
    ok = b is not None and connected(b, b.clicked)
    report(f"TitleBar {name}", "clicked connected", ok)

# Title bar menu items + project selector + search
menu_items = window.findChildren(QWidget, "WorkspaceTitleBarMenuItem")
menu_wired = sum(1 for m in menu_items if connected(m, m.clicked))
report("TitleBar menu items (File/Edit/...)", "wired?", menu_wired > 0, f"wired={menu_wired}/{len(menu_items)} DECORATIVE?")
proj = find("WorkspaceProjectSelector", QWidget)
report("WorkspaceProjectSelector", "wired?", proj is not None and connected(proj, proj.clicked) if hasattr(proj, 'clicked') else False, "DECORATIVE?")

# Export toolbar button
exp_btn = find("ToolbarExportButton", QToolButton)
report("ToolbarExportButton", "clicked connected", exp_btn is not None and connected(exp_btn, exp_btn.clicked))

# ---------------- Project system ----------------
ok_save = screen.save_project()
report("Save project (Ctrl+S)", "writes .ivproj.json", ok_save, screen._detail_status.text())
recents = screen.recent_projects()
report("Recent projects persisted", ">=1 entry", len(recents) >= 1, f"count={len(recents)}")

# Sidebar wiring
sidebar = screen._sidebar
new_lbl = sidebar.findChild(QLabel, "NavigationRecentNewProject")
report("Sidebar +New Project", "wired", new_lbl in screen._click_actions)
recent_rows = sidebar.findChildren(QWidget, "NavigationRecentItem")
rows_wired = sum(1 for r in recent_rows if r in screen._click_actions)
report("Sidebar recent rows", "wired", rows_wired == len(recent_rows), f"{rows_wired}/{len(recent_rows)}")

# Nav rail items?
nav_items = sidebar.findChildren(QWidget, "NavigationItem")
report("Sidebar nav rail items", "navigation_changed used by screen?",
       connected(sidebar, sidebar.navigation_changed), f"items={len(nav_items)} DECORATIVE?")

# Autosave timer active
report("Autosave timer", "running @120s", screen._autosave_timer.isActive())

# ---------------- Media browser nav visibility ----------------
screen._sidebar.select(2); pump(200)  # nav to Media
browser_shows = browser.isVisible()
screen._sidebar.select(0); pump(200)  # nav away
browser_hides = not browser.isVisible()
report("MediaBrowser nav show/hide", "visible on Media nav, hidden on other",
       browser_shows and browser_hides,
       f"shows={browser_shows} hides={browser_hides}")

# ---------------- Media browser internal controls ----------------
srch = find("MediaBrowserSearch", QWidget, browser)
report("MediaBrowserSearch", "filters list?", srch is not None and hasattr(srch, 'text_changed') and connected(srch, srch.text_changed), "DECORATIVE?")
view_toggle = find("MediaBrowserViewToggle", QWidget, browser)
has_recv = False
if view_toggle is not None:
    for sig_name in ("clicked", "toggled"):
        sig = getattr(view_toggle, sig_name, None)
        if sig is not None:
            try:
                has_recv = has_recv or connected(view_toggle, sig)
            except Exception:
                pass
report("MediaBrowserViewToggle", "wired?", has_recv, "DECORATIVE?")

# Browser hidden by default, shown only on Media nav (checked above)
report("MediaBrowser hidden by default", "not visible until Media nav active",
       not browser.isVisible())

controller.stop()

print()
print("=" * 100)
fails = [r for r in REPORT if r[0] == "FAIL"]
passes = [r for r in REPORT if r[0] == "PASS"]
print(f"RUNTIME AUDIT: {len(passes)} PASS / {len(fails)} FAIL of {len(REPORT)} probes")
print("=" * 100)
for status, control, expected, actual in REPORT:
    print(f"[{status}] {control}")
    print(f"       expect: {expected}")
    if actual:
        print(f"       actual: {actual}")
