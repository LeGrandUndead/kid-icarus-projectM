# Removes the game's own HUD from captures so new HUD mockups sit on clean scenes.
import cv2, numpy as np
src = '/home/claude/work/mock/'
for name in ['air_dialogue_view', 'land_view', 'medusa_view']:
    im = cv2.imread(src + name + '.png')
    mask = np.zeros(im.shape[:2], np.uint8)
    cv2.rectangle(mask, (0, 0), (440, 112), 255, -1)
    if name == 'air_dialogue_view': cv2.rectangle(mask, (250, 60), (340, 145), 255, -1)       # health bar + wing
    cv2.rectangle(mask, (1085, 0), (1359, 135), 255, -1)   # score + tendrils
    # captions are kept: they are the game's subtitles, not HUD
    small = cv2.resize(im, None, fx=0.5, fy=0.5)
    m2 = cv2.resize(mask, None, fx=0.5, fy=0.5)
    fill = cv2.inpaint(small, m2, 12, cv2.INPAINT_TELEA)
    fill = cv2.GaussianBlur(cv2.resize(fill, (im.shape[1], im.shape[0])), (0, 0), 6)
    a = cv2.GaussianBlur(cv2.dilate(mask, np.ones((15,15))).astype(np.float32)/255, (0,0), 10)[..., None]
    out = (fill*a + im*(1-a)).astype(np.uint8)
    out = cv2.resize(out, (1920, 1080), interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(name + '_clean.png', out)
