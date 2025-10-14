import os

__version__ = '0.2.0'

SOCKET_PATH = f"{os.environ['XDG_RUNTIME_DIR']}/hypr/{os.environ['HYPRLAND_INSTANCE_SIGNATURE']}/.socket2.sock"

RESIZE = 0.4