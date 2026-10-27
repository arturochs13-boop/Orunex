import cv2
import os

img_path = r"c:\Users\artur\Downloads\Project_Orunex\orunex_outputs\debug\profile_after_1774911414.png"
out_path = r"c:\Users\artur\Downloads\Project_Orunex\src\_orunex_libs\guest_btn.png"

img = cv2.imread(img_path)
# Crop the Guest Mode button
# Typical 1920x1200 max windows, bottom left button is roughly x:10 to 180, y:1030 to 1120
crop = img[1040:1110, 20:180]

cv2.imwrite(out_path, crop)
print(f"Template saved to {out_path}")
