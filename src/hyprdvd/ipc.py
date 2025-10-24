import json, os, socket

def hypr_json(cmd: str):
    """Call Hyprland IPC JSON command (socket2) and return parsed JSON."""
    # eg: $XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/.socket2.sock
    rt = os.environ.get("XDG_RUNTIME_DIR")
    sig = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not rt or not sig:
        raise RuntimeError("Not in a Hyprland session (missing XDG_RUNTIME_DIR or HYPRLAND_INSTANCE_SIGNATURE)")
    path = os.path.join(rt, "hypr", sig, ".socket2.sock")
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(path)
    s.send((cmd + "\n").encode("utf-8"))
    chunks = []
    while True:
        data = s.recv(65536)
        if not data:
            break
        chunks.append(data)
        if len(data) < 65536:
            break
    s.close()
    return json.loads(b"".join(chunks).decode("utf-8"))
