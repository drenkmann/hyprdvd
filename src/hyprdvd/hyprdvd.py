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

		self.window_width = 700
		self.window_height = 400

		self.velocity = 2

		self.get_window_position()

		print(f'Window position: {self.window_x}, {self.window_y}')

	def loop(self):
		'''Main loop'''
		pass

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