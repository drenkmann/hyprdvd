import time
import json
import math
import random

from hyprdvd.settings import RESIZE
from .utils import hyprctl
from .hyprDVD import HyprDVD

def run_screensaver(manager, poll_interval=0.02):
	'''Run the screensaver: save cursor and current workspace windows, float and animate them until cursor moves.

	This function makes a few reasonable assumptions about available hyprctl commands:
	- `hyprctl(['cursorpos'])` returns cursor coordinates as: "<x> <y>" or similar.
	- `clients -j` returns a list of client dicts with keys: 'address', 'at', 'size', 'workspace', 'focused'.

	If those commands differ on your system we can adapt parsing accordingly.
	'''

	# 1) Save cursor position
	saved_cursor = None
	try:
		out = hyprctl(['cursorpos']).stdout.strip()
		if out:
			parts = out.replace(',', ' ').split()
			if len(parts) >= 2:
				saved_cursor = (int(float(parts[0])), int(float(parts[1])))
	except Exception:
		# If cursor query fails, we'll still proceed but we can't detect movement
		saved_cursor = None

	# 2) Collect current workspace clients
	clients = json.loads(hyprctl(['clients', '-j']).stdout)
	focused = next((c for c in clients if c.get('focused')), None)
	if focused:
		workspace_id = focused['workspace']['id']
	else:
		# fallback: ask hyprctl for the active workspace
		try:
			out = hyprctl(['activeworkspace']).stdout.strip()
			# hyprctl activeworkspace output is expected to contain the id; try to parse any integers
			parts = out.replace(',', ' ').split()
			ints = [int(p) for p in parts if p.lstrip('-').isdigit()]
			workspace_id = ints[0] if ints else None
		except Exception:
			workspace_id = None

	if workspace_id is None:
		print('Could not determine current workspace — aborting screensaver')
		return

	clients_in_ws = [c for c in clients if c.get('workspace', {}).get('id') == workspace_id]

	# 3) Save original states and make windows floating
	saved_windows = []

	# Compute non-overlapping sizes/positions for all windows in the workspace.
	# We'll place them on a grid (cols x rows) that fits all windows. Each window
	# will be at most a ration set in settings of the screen size and centered within its cell.
	N = len(clients_in_ws)
	computed = {}
	if N > 0:
		monitors = json.loads(hyprctl(['monitors', '-j']).stdout)
		screen_width = None
		screen_height = None
		for monitor in monitors:
			if monitor['activeWorkspace']['id'] == int(workspace_id):
				transform = monitor['transform'] in [1, 3, 5, 7]
				screen_width = monitor['width'] if not transform else monitor['height']
				screen_height = monitor['height'] if not transform else monitor['width']
				break
		if screen_width is None or screen_height is None:
			if monitors:
				monitor = monitors[0]
				transform = monitor['transform'] in [1, 3, 5, 7]
				screen_width = monitor['width'] if not transform else monitor['height']
				screen_height = monitor['height'] if not transform else monitor['width']

		cols = max(1, math.ceil(math.sqrt(N * (screen_width / screen_height)))) if screen_height > 0 else max(1, math.ceil(math.sqrt(N)))
		rows = math.ceil(N / cols)

		cell_w = screen_width / cols
		cell_h = screen_height / rows

		max_w = min(int(screen_width * RESIZE), int(cell_w * 0.9))
		max_h = min(int(screen_height * RESIZE), int(cell_h * 0.9))

		for i, c in enumerate(clients_in_ws):
			col = i % cols
			row = i // cols
			w = max(1, max_w)
			h = max(1, max_h)
			x = int(col * cell_w + (cell_w - w) / 2)
			y = int(row * cell_h + (cell_h - h) / 2)
			computed[c.get('address')] = {'size': [w, h], 'at': [x, y]}

	# assign computed sizes/positions when making windows floating
	for c in clients_in_ws:
		addr = c.get('address')
		if not addr:
			continue
		comp = computed.get(addr, {})
		anim_size = comp.get('size', c.get('size'))
		# Add some randomness to the position so windows don't align perfectly
		base_at = comp.get('at', c.get('at'))
		if base_at:
			# Use a unique random generator per window to avoid same offsets
			rng = random.Random(str(addr))
			cell_w = max(1, cell_w)
			cell_h = max(1, cell_h)
			w, h = anim_size
			max_dx = int(cell_w * 0.1)
			max_dy = int(cell_h * 0.1)
			retries = 0
			while True:
				dx = rng.randint(-max_dx, max_dx)
				dy = rng.randint(-max_dy, max_dy)
				x = base_at[0] + dx
				y = base_at[1] + dy
				# Ensure window is fully on screen
				if 0 <= x <= screen_width - w and 0 <= y <= screen_height - h:
					anim_at = [x, y]
					break
				retries += 1
				if retries > 100:
					# fallback to clamped position if too many retries
					x = min(max(0, x), screen_width - w)
					y = min(max(0, y), screen_height - h)
					anim_at = [x, y]
					break

		# save minimal state including original client values so we can restore them
		saved_windows.append({
			'address': addr,
			'at': anim_at,
			'size': anim_size,
			'orig_at': c.get('at'),
			'orig_size': c.get('size'),
			'floating': c.get('floating', False),
		})

		# Make floating and ensure size/position match animation values
		hyprctl(['dispatch', 'setfloating', f'address:{addr}'])
		if anim_size:
			hyprctl(['dispatch', 'resizewindowpixel', 'exact', str(anim_size[0]), str(anim_size[1]), f',address:{addr}'])
		if anim_at:
			hyprctl(['dispatch', 'movewindowpixel', 'exact', str(anim_at[0]), str(anim_at[1]), f',address:{addr}'])

		# Add to manager so it will be animated, pass pixel size to HyprDVD
		manager.windows.append(HyprDVD.from_client(c, manager, size=anim_size))

	if not manager.windows:
		print('No windows found in current workspace to animate')
		return

	print(f'Running screensaver on workspace {workspace_id} with {len(manager.windows)} windows')

	# 4) Animate until cursor moves
	try:
		while True:
			# check cursor movement
			moved = False
			if saved_cursor is not None:
				try:
					out = hyprctl(['cursorpos']).stdout.strip()
					parts = out.replace(',', ' ').split()
					if len(parts) >= 2:
						cur = (int(float(parts[0])), int(float(parts[1])))
						if cur != saved_cursor:
							moved = True
				except Exception:
					# unable to read cursor; do not treat as moved
					pass

			if moved:
				print('Cursor moved — restoring windows and exiting screensaver')
				break

			# otherwise update animation
			manager.update_windows()
			time.sleep(poll_interval)
	finally:
		# 5) restore saved windows to original positions/sizes/floating state
		# Restore window sizes/positions and floating state to their ORIGINAL
		# values (orig_at / orig_size) when available, while keeping them
		# floating. Collect original area so we can tile largest->smallest.
		batch_cmds = []
		addr_area = []
		for w in saved_windows:
			addr = w['address']
			orig_size = w.get('orig_size') or w.get('size')
			orig_at = w.get('orig_at') or w.get('at')
			if orig_size:
				hyprctl(['dispatch', 'resizewindowpixel', 'exact', str(orig_size[0]), str(orig_size[1]), f',address:{addr}'])
			if orig_at:
				hyprctl(['dispatch', 'movewindowpixel', 'exact', str(orig_at[0]), str(orig_at[1]), f',address:{addr}'])
			# restore floating state
			if not w.get('floating'):
				hyprctl(['dispatch', 'setfloating', 'no', f'address:{addr}'])

			# compute area for ordering (fallback to animation size if orig_size missing)
			area = 0
			try:
				s = orig_size or w.get('size')
				area = int((s[0] or 0) * (s[1] or 0))
			except Exception:
				area = 0
			addr_area.append((addr, area))

		# Now tile from largest to smallest by building a batched list of
		# focus+settiled commands in that order and executing them once.
		if addr_area:
			addr_area.sort(key=lambda x: x[1], reverse=True)
			for addr, _ in addr_area:
				batch_cmds.append(f'dispatch focuswindow address:{addr}')
				batch_cmds.append(f'dispatch settiled address:{addr}')
			if batch_cmds:
				hyprctl(['--batch', ';'.join(batch_cmds)])

		print('Restored windows. Screensaver finished.')
		# set the cuttle cursor to the saved position
		hyprctl(['dispatch', 'movecursor', str(saved_cursor[0]), str(saved_cursor[1])])