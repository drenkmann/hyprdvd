import json
import random
from .utils import hyprctl
from .hyprDVD import HyprDVD

class HyprDVDManager:
	'''Manages all HyprDVD windows.'''
	def __init__(self):
		self.windows = []
		self.animation_enabled_workspaces = {}

	def add_window(self, event_data):
		'''Add a new window to manage'''
		window = HyprDVD(event_data, self)

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

	def cleanup_window(self, window):
		'''Cleanup a window and restore animation if it's the last one on the workspace.'''
		if window in self.windows:
			self.windows.remove(window)
			if not any(w.workspace_id == window.workspace_id for w in self.windows):
				self.handle_animation(window.workspace_id, False)

	def check_collisions(self):
		'''Check for collisions between windows and with screen borders.'''
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
		'''Update all window positions and move them.'''
		clients = json.loads(hyprctl(['clients', '-j']).stdout)
		for window in self.windows[:]:
			if not window.get_window_position_and_size(clients):
				self.cleanup_window(window)
				continue
			window.update()

		self.check_collisions()

		batch_command = []
		for window in self.windows:
			batch_command.append(f'dispatch movewindowpixel exact {window.window_x} {window.window_y},address:{window.address}')
		if batch_command:
			hyprctl(['--batch', ';'.join(batch_command)])

	def handle_animation(self, workspace_id, is_enabled):
		'''Handle animations for the workspace.'''
		if is_enabled:
			if workspace_id not in self.animation_enabled_workspaces:
				self.animation_enabled_workspaces[workspace_id] = hyprctl(['getoption', 'animations:enabled']).stdout.split()[1]
			hyprctl(['keyword', 'animations:enabled', 'no'])
		else:
			if workspace_id in self.animation_enabled_workspaces:
				hyprctl(['keyword', 'animations:enabled', self.animation_enabled_workspaces.pop(workspace_id)])

	def handle_workspace_change(self, event_data):
		'''Handle workspace change events.'''
		workspace_id = int(event_data[0])
		if any(w.workspace_id == workspace_id for w in self.windows):
			self.handle_animation(workspace_id, True)
		elif self.animation_enabled_workspaces:
			original_state = next(iter(self.animation_enabled_workspaces.values()))
			hyprctl(['keyword', 'animations:enabled', original_state])

		for w_id in list(self.animation_enabled_workspaces.keys()):
			if w_id != workspace_id and not any(w.workspace_id == w_id for w in self.windows):
				self.handle_animation(w_id, False)

	def handle_active_window_change(self, event_data):
		'''Handle active window change events.'''
		window_address = f'0x{event_data[1]}'
		clients = json.loads(hyprctl(['clients', '-j']).stdout)
		active_window = next((w for w in clients if w['address'] == window_address), None)
		if active_window:
			workspace_id = active_window['workspace']['id']
			if not any(w.address == window_address for w in self.windows):
				self.handle_animation(workspace_id, False)