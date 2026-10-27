import cv2
import pytesseract
import os

img_path = r"c:\Users\artur\Downloads\Project_Orunex\orunex_outputs\debug\profile_after_1774911414.png"
if not os.path.exists(img_path):
    print("File not found.")
    exit()

img = cv2.imread(img_path)
gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

tesseract_path = r"c:\Users\artur\Downloads\Project_Orunex\resources\Tesseract-OCR\tesseract.exe"
if os.path.exists(tesseract_path):
    pytesseract.pytesseract.tesseract_cmd = tesseract_path

data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)

print("Searching for guest/invitado/mode...")
for i in range(len(data['text'])):
    text = str(data['text'][i]).lower()
    if 'guest' in text or 'mode' in text or 'invitado' in text:
        left = data['left'][i]
        top = data['top'][i]
        width = data['width'][i]
        height = data['height'][i]
        conf = data['conf'][i]
        print(f"[{conf}] '{data['text'][i]}' at X:{left}, Y:{top}, W:{width}, H:{height}")
