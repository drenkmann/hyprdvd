import os

__version__ = '0.4.2'

SOCKET_PATH = f'{os.environ['XDG_RUNTIME_DIR']}/hypr/{os.environ['HYPRLAND_INSTANCE_SIGNATURE']}/.socket2.sock'

RESIZE = 0.4