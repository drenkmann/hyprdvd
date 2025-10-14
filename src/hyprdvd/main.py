from socket import socket, AF_UNIX, SOCK_STREAM
import time
import argparse
from .settings import SOCKET_PATH
from .screensaver import run_screensaver
from .hyprDVDManager import HyprDVDManager

def main():
	'''Main function of the script.'''
	parser = argparse.ArgumentParser(prog='hyprdvd')
	parser.add_argument('--screensaver', '-s', action='store_true', help='Run in screensaver mode: take current workspace windows and animate them until the cursor moves')
	args = parser.parse_args()

	manager = HyprDVDManager()

	if args.screensaver:
		run_screensaver(manager)
		return

	# Default behaviour: Connect to Hyprland's socket and listen for events.
	with socket(AF_UNIX, SOCK_STREAM) as sock:
		sock.connect(SOCKET_PATH)
		sock.setblocking(False)

		while True:
			try:
				event = sock.recv(4096).decode().strip()
				if event:
					for line in event.split('\n'):
						event_type, event_data = line.split('>>', 1)
						event_data = event_data.split(',')
						if event_type == 'openwindow' and len(event_data) > 3 and event_data[3] == 'DVD':
							manager.add_window(event_data)
						elif event_type == 'workspace':
							manager.handle_workspace_change(event_data)
						elif event_type == 'activewindow':
							manager.handle_active_window_change(event_data)
			except BlockingIOError:
				pass

			if manager.windows:
				manager.update_windows()

			time.sleep(0.01) # Control the loop speed


if __name__ == "__main__":
	main()
