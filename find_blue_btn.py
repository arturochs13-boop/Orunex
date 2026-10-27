import cv2
import numpy as np
import os

img_path = r"c:\Users\artur\Downloads\Project_Orunex\orunex_outputs\debug\profile_after_1774911414.png"
if not os.path.exists(img_path):
    print("File not found")
    exit()

img = cv2.imread(img_path)

# Convert to HSV to find Google Blue #1a73e8
hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

# Blue color range
lower_blue = np.array([100, 150, 150])
upper_blue = np.array([140, 255, 255])

mask = cv2.inRange(hsv, lower_blue, upper_blue)
contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

best_c = None
max_area = 0
for c in contours:
    area = cv2.contourArea(c)
    if area > max_area and area < 10000: # filter out huge backgrounds
        max_area = area
        best_c = c

if best_c is not None:
    x, y, w, h = cv2.boundingRect(best_c)
    print(f"Largest blue element (Guest Mode icon) found at X:{x}, Y:{y}, W:{w}, H:{h}")
    # Center of the button
    cx = x + w // 2
    cy = y + h // 2
    print(f"Center click: ({cx}, {cy})")
else:
    print("No blue element found.")
