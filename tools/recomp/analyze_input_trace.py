"""Summarize captured mouse/HID traces without interpreting game camera state."""
import argparse
import csv
import json
import math
from pathlib import Path


def summarize(path):
    frames = captured = moving = lifts = idle_lifts = 0
    maximum_touch_step = maximum_mouse_step = 0.0
    previous = None
    with path.open(newline='', encoding='utf-8') as stream:
        for row in csv.DictReader(stream):
            frames += 1
            active = row['captured'] == 'true' and row['replay'] == 'false'
            if not active:
                previous = None
                continue
            captured += 1
            mouse = math.hypot(float(row['mouse_dx']), float(row['mouse_dy']))
            moving += mouse > 0
            maximum_mouse_step = max(maximum_mouse_step, mouse)
            touch = ((int(row['touch_x']), int(row['touch_y']))
                     if row['touch_down'] == 'true' else None)
            if previous is not None:
                if touch is None:
                    lifts += 1
                    idle_lifts += mouse == 0
                else:
                    maximum_touch_step = max(maximum_touch_step,
                                             math.dist(previous, touch))
            previous = touch
    return dict(frames=frames, captured_frames=captured, moving_frames=moving,
                touch_lifts=lifts, lifts_without_new_mouse_motion=idle_lifts,
                maximum_mouse_delta=maximum_mouse_step,
                maximum_consecutive_touch_delta=maximum_touch_step,
                limitation='HID evidence only; no camera/reticle state or automatic land/flight detection')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.trace), indent=2))
