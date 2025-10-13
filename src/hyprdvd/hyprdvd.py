from socket import socket, AF_UNIX, SOCK_STREAM
import json
import random
import math
import time
from .settings import SOCKET_PATH
from .utils import hyprctl

class HyprDVD:
	"""Class for a single bouncing window."""
	def __init__(self, event_data):
		self.address = f'0x{event_data[0]}'
		self.workspace_id = int(event_data[1])

		self.get_screen_size()
		self.border_size = int(hyprctl(['getoption', 'general:border_size']).stdout.split()[1])

		self.set_window_size()

		self.velocity_x = 2
		self.velocity_y = 2

		self.set_window_start()

	def set_window_size(self):
		"""Set the size of the window relative to the screen size"""
		resize = 0.4
		self.window_width = math.ceil(self.screen_width * resize)
		self.window_height = math.ceil(self.screen_height * resize)

	def set_window_start(self):
		"""Set a random direction"""
		if random.randrange(1, 100) % 2 == 0:
			self.velocity_x *= -1
		if random.randrange(101, 200) % 2 == 0:
			self.velocity_y *= -1

		hyprctl(['dispatch', 'setfloating', f'address:{self.address}'])
		hyprctl(['dispatch', 'resizewindowpixel', 'exact',
				 str(self.window_width), str(self.window_height), f',address:{self.address}'])

	def get_screen_size(self):
		"""Get the screen size"""
		monitors_json = json.loads(hyprctl(['monitors', '-j']).stdout)
		for monitor in monitors_json:
			if monitor['activeWorkspace']['id'] == int(self.workspace_id):
				transform = monitor['transform'] in [1, 3, 5, 7]
				self.screen_width = monitor['width'] if not transform else monitor['height']
				self.screen_height = monitor['height'] if not transform else monitor['width']
				break

	def get_window_position_and_size(self):
		"""Get the window position and size"""
		clients = json.loads(hyprctl(['clients', '-j']).stdout)
		window = next((w for w in clients if w['address'] == self.address), None)

		if not window:
			return False

		self.window_x, self.window_y = window['at']
		self.window_width, self.window_height = window['size']
		return True

	def update(self):
		"""Update window position"""
		self.window_x += self.velocity_x
		self.window_y += self.velocity_y

	def move(self):
		"""Move window to its new position"""
		hyprctl(['dispatch', 'movewindowpixel', 'exact',
				 str(self.window_x), str(self.window_y), f',address:{self.address}'])

class HyprDVDManager:
	"""Manages all HyprDVD windows."""
	def __init__(self):
		self.windows = []
		self.animation_enabled_workspaces = {}

	def add_window(self, event_data):
		"""Add a new window to manage"""
		window = HyprDVD(event_data)

		attempts = 0
		while attempts < 100:
			random_x = random.randrange(0, window.screen_width - window.window_width)
			random_y = random.randrange(0, window.screen_height - window.window_height)

			overlapping = False
			for other_window in self.windows:
				if (window.workspace_id == other_window.workspace_id and
						random_x < other_window.window_x + other_window.window_width and
						random_x + window.window_width > other_window.window_x and
						random_y < other_window.window_y + other_window.window_height and
						random_y + window.window_height > other_window.window_y):
					overlapping = True
					break
			if not overlapping:
				hyprctl(['dispatch', 'movewindowpixel', 'exact',
						 str(random_x), str(random_y), f',address:{window.address}'])
				self.windows.append(window)
				self.handle_animation(window.workspace_id, True)
				return

			attempts += 1

		# If no space is found after 100 attempts, close the window
		hyprctl(['dispatch', 'closewindow', f'address:{window.address}'])

	def check_collisions(self):
		"""Check for collisions between windows and with screen borders."""
		for i, window in enumerate(self.windows):
			# Screen border collision
			if not 0 < window.window_x < window.screen_width - window.window_width:
				window.velocity_x *= -1
			if not 0 < window.window_y < window.screen_height - window.window_height:
				window.velocity_y *= -1

			# Other window collision
			for other_window in self.windows[i+1:]:
				if (
					window.workspace_id == other_window.workspace_id and
					window.window_x < other_window.window_x + other_window.window_width and
					window.window_x + window.window_width > other_window.window_x and
					window.window_y < other_window.window_y + other_window.window_height and
					window.window_y + window.window_height > other_window.window_y
				):

					overlap_x = min(window.window_x + window.window_width, other_window.window_x + other_window.window_width) - max(window.window_x, other_window.window_x)
					overlap_y = min(window.window_y + window.window_height, other_window.window_y + other_window.window_height) - max(window.window_y, other_window.window_y)

					if overlap_x < overlap_y:
						window.velocity_x, other_window.velocity_x = other_window.velocity_x, window.velocity_x
					else:
						window.velocity_y, other_window.velocity_y = other_window.velocity_y, window.velocity_y



	def update_windows(self):
		"""Update all window positions and move them."""
		for window in self.windows:
			if not window.get_window_position_and_size():
				self.windows.remove(window)
				self.handle_animation(window.workspace_id, False)
				continue
			window.update()

		self.check_collisions()

		for window in self.windows:
			window.move()

	def handle_animation(self, workspace_id, is_enabled):
		"""Handle animations for the workspace."""
		if is_enabled:
			if workspace_id not in self.animation_enabled_workspaces:
				self.animation_enabled_workspaces[workspace_id] = hyprctl(['getoption', 'animations:enabled']).stdout.split()[1]
			hyprctl(['keyword', 'animations:enabled', 'no'])
		else:
			if workspace_id in self.animation_enabled_workspaces:
				hyprctl(['keyword', 'animations:enabled', self.animation_enabled_workspaces.pop(workspace_id)])

def main():
	"""Main function of the script."""
	manager = HyprDVDManager()

	# Connect to Hyprland's socket and listen for events.
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
			except BlockingIOError:
				pass

			if manager.windows:
				manager.update_windows()

			time.sleep(0.01) # Control the loop speed

if __name__ == "__main__":
	main()