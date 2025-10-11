from socket import socket, AF_UNIX, SOCK_STREAM
from .settings import SOCKET_PATH
from .utils	import hyprctl
import json
import time

class hyprdvd():
	'''Main class for hyprdvd.'''
	def __init__(self, event_data):
		self.address = f'0x{event_data[0]}'
		self.workspace_id = int(event_data[1])

		self.get_screen_size()
		self.border_size = int(hyprctl(['getoption', 'general:border_size']).stdout.split()[1])

		self.window_width = 700
		self.window_height = 400

		self.velocity_x = 2
		self.velocity_y = 2

		self.get_window_position()

		hyprctl(['dispatch', 'setfloating', 'title:^(DVD)$'])
		hyprctl(['dispatch', 'resizewindowpixel', 'exact', 
						str(self.window_width), str(self.window_height), ',title:^(DVD)$'
		])
		hyprctl(['dispatch', 'movewindowpixel', 'exact', 
						str(self.border_size) , str(self.border_size), ',title:^(DVD)$'
		])

		self.loop()

	def loop(self):
		'''Main loop'''
		while True:
			self.get_window_position()
			print('hey')
			if self.window_y + self.window_height + self.border_size + self.velocity_y > self.screen_height or \
			self.window_y + self.velocity_y < 0:
				self.velocity_y *= -1

			if self.window_x + self.window_width + self.border_size + self.velocity_x > self.screen_width or \
			self.window_x + self.velocity_y < 0:
				self.velocity_x *= -1

			hyprctl(['dispatch', 'movewindowpixel', 'exact', 
							str(self.window_x + self.velocity_x) , str(self.window_y + self.velocity_y), ',title:^(DVD)$'
			])


	def get_screen_size(self):
		'''Get the screen size'''
		monitors_json = json.loads(hyprctl(['monitors', '-j']).stdout)
		for monitor in monitors_json:
			if monitor['activeWorkspace']['id'] == int(self.workspace_id):
				transform = monitor['transform'] in [1, 3, 5, 7]
				self.screen_width = monitor['width'] if not transform else monitor['height']
				self.screen_height = monitor['height'] if not transform else monitor['width']
				break

	def get_window_position(self):
		'''Get the window position'''
		clients = json.loads(hyprctl(['clients', '-j']).stdout)
		workspace_windows = [c for c in clients if c['workspace']['id'] == self.workspace_id]
		window = next((w for w in workspace_windows if w['title'] == 'DVD'), None)

		self.window_x, self.window_y = window['at']

def main():
	'''Main function of the script.'''

	# Connect to Hyprland's socket and listen for events.
	with socket(AF_UNIX, SOCK_STREAM) as sock:
		sock.connect(SOCKET_PATH)
		while True:
			event = sock.recv(1024).decode().strip().split('\n')[0]
			if event:
				event_type, event_data = event.split('>>', 1)
				event_data = event_data.split(',')
				if event_type == 'openwindow' and event_data[3] == 'DVD':
					hyprdvd(event_data)