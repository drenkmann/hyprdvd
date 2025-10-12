from socket import socket, AF_UNIX, SOCK_STREAM
from multiprocessing import Process
import json
import random
import math
from .settings import SOCKET_PATH
from .utils	import hyprctl

class hyprdvd():
	'''Main class for hyprdvd.'''
	def __init__(self, event_data):
		self.address = f'0x{event_data[0]}'
		self.workspace_id = int(event_data[1])

		self.get_screen_size()
		self.border_size = int(hyprctl(['getoption', 'general:border_size']).stdout.split()[1])

		self.set_window_size()

		self.velocity_x = 2
		self.velocity_y = 2

		self.set_window_start()
		self.loop()

		if self.get_animation_option:
			hyprctl(['keyword', 'animations:enabled', 'yes'])
		else:
			hyprctl(['keyword', 'animations:enabled', 'no'])

	def loop(self):
		'''Main loop'''
		while True:
			if not self.get_window_position_and_size():
				break
			self.handle_animation()

			if self.window_y + self.window_height + self.border_size + self.velocity_y > self.screen_height or \
			self.window_y + self.velocity_y < 0:
				self.velocity_y *= -1

			if self.window_x + self.window_width + self.border_size + self.velocity_x > self.screen_width or \
			self.window_x + self.velocity_y < 0:
				self.velocity_x *= -1

			hyprctl(['dispatch', 'movewindowpixel', 'exact', 
							str(self.window_x + self.velocity_x) , str(self.window_y + self.velocity_y), f',address:{self.address}'
			])

	def set_window_size(self):
		'''Set the size of the window relative to the screen size'''
		resize = 0.4

		self.window_width = math.ceil(self.screen_width * resize)
		self.window_height = math.ceil(self.screen_height * resize)

	def set_window_start(self):
		'''Set a random positon and direction'''
		random_x = random.randrange(0, self.screen_width - self.window_width)
		random_y = random.randrange(0, self.screen_height - self.window_height)

		if random.randrange(1, 100) % 2 == 0:
			self.velocity_x *= -1

		if random.randrange(101, 200) % 2 == 0:
			self.velocity_y *= -1

		hyprctl(['dispatch', 'setfloating', f'address:{self.address}'])
		hyprctl(['dispatch', 'resizewindowpixel', 'exact', 
						str(self.window_width), str(self.window_height), f',address:{self.address}'
		])
		hyprctl(['dispatch', 'movewindowpixel', 'exact', 
						str(random_x) , str(random_y), f',address:{self.address}'
		])

	def get_screen_size(self):
		'''Get the screen size'''
		monitors_json = json.loads(hyprctl(['monitors', '-j']).stdout)
		for monitor in monitors_json:
			if monitor['activeWorkspace']['id'] == int(self.workspace_id):
				transform = monitor['transform'] in [1, 3, 5, 7]
				self.screen_width = monitor['width'] if not transform else monitor['height']
				self.screen_height = monitor['height'] if not transform else monitor['width']
				# TODO: set correct screen size for side monitors
				# self.screen_x = monitor['x']
				# self.screen_y = monitor['y']
				break

	def get_window_position_and_size(self):
		'''Get the window position'''
		clients = json.loads(hyprctl(['clients', '-j']).stdout)
		workspace_windows = [c for c in clients if c['workspace']['id'] == self.workspace_id]
		window = next((w for w in workspace_windows if w['address'] == self.address), None)

		if not window:
			return False

		self.window_x, self.window_y = window['at']
		self.window_width, self.window_height = window['size'] # If window get resized
		return True

	def get_animation_option(self):
		'''Get the animation option value'''
		self.animation_option = hyprctl(['getoption', 'animations:enabled']).stdout.split()[1]

	def handle_animation(self):
		'''Handle the animation'''
		if self.get_active_workspace() == self.workspace_id:
			hyprctl(['keyword', 'animations:enabled', 'no'])
		else:
			hyprctl(['keyword', 'animations:enabled', 'yes'])

	def get_active_workspace(self):
		'''Get the active workspace'''
		return json.loads(hyprctl(['activeworkspace', '-j']).stdout)['id']


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
					process = Process(target=hyprdvd, args=(event_data,))
					process.start()