import random
import math
import json

from .utils import hyprctl
from .settings import RESIZE

class HyprDVD:
	'''Class for a single bouncing window.'''
	def __init__(self, event_data, manager, size=None):
		self.address = f'0x{event_data[0]}'
		self.workspace_id = int(event_data[1])
		self.manager = manager

		self.requested_size = size

		self.get_screen_size()
		self.set_window_size()

		self.velocity_x = 2
		self.velocity_y = 2

		self.set_window_start()

	@classmethod
	def from_client(cls, client, manager, size=None):
		'''Create a HyprDVD instance from a hyprctl client dict.'''
		addr = client.get('address', '')
		addr_stripped = addr.replace('0x', '') if addr.startswith('0x') else addr
		ev = [addr_stripped, str(client['workspace']['id'])]
		instance = cls(ev, manager, size=size)
		# override position/size with actual client values so the screensaver
		# starts from the original locations
		try:
			instance.window_x, instance.window_y = client['at']
			instance.window_width, instance.window_height = client['size']
		except Exception:
			# If client data doesn't have expected fields, leave defaults
			pass
		return instance

	def set_window_size(self):
		'''Set the size of the window relative to the screen size'''
		# If a requested size was provided, use it. Values <=1 are ratios of the
		# screen; values >1 are treated as absolute pixel sizes.
		if self.requested_size:
			try:
				rw, rh = self.requested_size
				if rw <= 1 and rh <= 1:
					self.window_width = math.ceil(self.screen_width * float(rw))
					self.window_height = math.ceil(self.screen_height * float(rh))
				else:
					self.window_width = int(rw)
					self.window_height = int(rh)
				return
			except Exception:
				# fallback to default if provided size is invalid
				pass

		resize = RESIZE
		self.window_width = math.ceil(self.screen_width * resize)
		self.window_height = math.ceil(self.screen_height * resize)

	def set_window_start(self):
		'''Set a random direction'''
		if random.randrange(1, 100) % 2 == 0:
			self.velocity_x *= -1
		if random.randrange(101, 200) % 2 == 0:
			self.velocity_y *= -1

		hyprctl(['dispatch', 'setfloating', f'address:{self.address}'])
		hyprctl(['dispatch', 'resizewindowpixel', 'exact',
				 str(self.window_width), str(self.window_height), f',address:{self.address}'])

	def get_screen_size(self):
		'''Get the screen size'''
		monitors_json = json.loads(hyprctl(['monitors', '-j']).stdout)
		for monitor in monitors_json:
			if monitor['activeWorkspace']['id'] == int(self.workspace_id):
				transform = monitor['transform'] in [1, 3, 5, 7]
				self.screen_width = monitor['width'] if not transform else monitor['height']
				self.screen_height = monitor['height'] if not transform else monitor['width']
				break

	def get_window_position_and_size(self, clients):
		'''Get the window position and size'''
		window = next((w for w in clients if w['address'] == self.address), None)

		if not window:
			return False

		self.window_x, self.window_y = window['at']
		self.window_width, self.window_height = window['size']
		return True

	def update(self):
		'''Update window position'''
		self.window_x += self.velocity_x
		self.window_y += self.velocity_y