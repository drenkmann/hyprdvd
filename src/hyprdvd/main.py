from socket import socket, AF_UNIX, SOCK_STREAM
import time
import argparse

from .settings import SOCKET_PATH, __version__
from .screensaver import run_screensaver
from .hyprDVDManager import HyprDVDManager

def main():
	'''Main function of the script.'''
	parser = argparse.ArgumentParser(
		prog='hyprdvd',
		description='HyprDVD: Bouncing windows for Hyprland',
		epilog='Run without arguments and open a window with title "DVD" to see it bounce!'
	)

	parser.add_argument('-s', '--screensaver',
		action='store_true',
		help='Run in screensaver mode: take current workspace windows and animate them until the cursor moves'
	)
	parser.add_argument('--size',
		action='store',
		help='Set the size of the bouncing windows (WIDTHxHEIGHT)'
	)

	parser.add_argument('--workspaces',
		help='comma-seperated workspace IDs',
		type=str,
		default=None
	)

	parser.add_argument('--exit-on',
		choices=["pointer", "signal"],
		default='pointer'
	)



	parser.add_argument('-v', '--version', action='version', version=f'HyprDVD v{__version__}')
	args = parser.parse_args()

	# Parse the size argument (format: WIDTHxHEIGHT)
	size = None
	if args.size:
		try:
			width, height = args.size.split('x')
			size = (int(width), int(height))
		except ValueError:
			print(f'Error: Invalid size format {args.size}. Use WIDTHxHEIGHT format (e.g., 100x100)')
			return

	manager = HyprDVDManager(size=size)

	if args.screensaver:
		run_screensaver(
			manager,
			size=size,
			workspaces = args.workspaces,
			exit_on=args.exit_on
		)
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
