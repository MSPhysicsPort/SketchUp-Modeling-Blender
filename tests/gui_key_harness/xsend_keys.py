"""Send real X key events to the Blender window (ctypes + libX11 only).
Usage: python3 xsend_keys.py <display> <ready_file> <keys> [wait_after]
keys: comma-separated single chars, e.g. "l,esc,e,esc".
"""
import ctypes, sys, time, os

libX11 = ctypes.CDLL("libX11.so.6")
libX11.XOpenDisplay.restype = ctypes.c_void_p
libX11.XOpenDisplay.argtypes = [ctypes.c_char_p]
libX11.XKeysymToKeycode.restype = ctypes.c_uint
libX11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
libX11.XFetchName.restype = ctypes.c_int
libX11.XFetchName.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_char_p)]
libX11.XQueryTree.restype = ctypes.c_int

class XKeyEvent(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_int),
        ("serial", ctypes.c_ulong),
        ("send_event", ctypes.c_int),
        ("display", ctypes.c_void_p),
        ("window", ctypes.c_ulong),
        ("root", ctypes.c_ulong),
        ("subwindow", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("x", ctypes.c_int), ("y", ctypes.c_int),
        ("x_root", ctypes.c_int), ("y_root", ctypes.c_int),
        ("state", ctypes.c_uint),
        ("keycode", ctypes.c_uint),
        ("same_screen", ctypes.c_int),
    ]

KEYSYMS = {"esc": 0xFF1B, "tab": 0xFF09, "space": 0x20,
            "f1": 0xFFBE, "f2": 0xFFBF, "f3": 0xFFC0, "f4": 0xFFC1, "f5": 0xFFC2,
            "return": 0xFF0D}
for ch in "abcdefghijklmnopqrstuvwxyz0123456789":
    KEYSYMS[ch] = ord(ch)

def main():
    display_name, ready_file, keys = sys.argv[1], sys.argv[2], sys.argv[3].split(",")
    wait_after = float(sys.argv[4]) if len(sys.argv) > 4 else 1.2
    deadline = time.time() + 40
    while not (os.path.exists(ready_file) and "READY" in open(ready_file).read()):
        if time.time() > deadline:
            print("SENDER: ready timeout"); return 1
        time.sleep(0.3)
    dpy = libX11.XOpenDisplay(display_name.encode())
    assert dpy, "cannot open display"
    root = libX11.XDefaultRootWindow(dpy)
    # Find the Blender window.
    win = None
    for _ in range(50):
        root_ret = ctypes.c_ulong(); parent_ret = ctypes.c_ulong()
        children = ctypes.POINTER(ctypes.c_ulong)(); n = ctypes.c_uint()
        libX11.XQueryTree(dpy, root, ctypes.byref(root_ret), ctypes.byref(parent_ret),
                          ctypes.byref(children), ctypes.byref(n))
        for i in range(n.value):
            w = children[i]
            name = ctypes.c_char_p()
            if libX11.XFetchName(dpy, w, ctypes.byref(name)) and name.value:
                if b"Blender" in name.value:
                    win = w
                    break
        libX11.XFree(children)
        if win:
            break
        time.sleep(0.3)
    assert win, "Blender window not found"
    print("SENDER: window 0x%x" % win)
    libX11.XSetInputFocus(dpy, win, 2, 0)  # RevertToParent, CurrentTime
    libX11.XWarpPointer(dpy, 0, win, 0, 0, 0, 0, 640, 500)
    libX11.XFlush(dpy)
    time.sleep(1.5)
    for key in keys:
        code = libX11.XKeysymToKeycode(dpy, KEYSYMS[key])
        for ev_type in (2, 3):  # KeyPress, KeyRelease
            ev = XKeyEvent()
            ev.type = ev_type
            ev.display = dpy
            ev.window = win
            ev.root = root
            ev.x, ev.y, ev.x_root, ev.y_root = 640, 500, 640, 500
            ev.keycode = code
            ev.same_screen = 1
            libX11.XSendEvent(dpy, win, 0, 3, ctypes.byref(ev))
            libX11.XFlush(dpy)
            time.sleep(0.15)
        print("SENDER: sent %s" % key)
        time.sleep(wait_after)
    print("SENDER: done")
    return 0

sys.exit(main())
