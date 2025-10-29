# 🧠 Smartboard AI Gesture Control

A **desktop smartboard** built with **PyQt5**, **OpenCV**, and **MediaPipe**, enabling you to draw and erase using **hand gestures** or **mouse + keyboard** input.

---

## ✨ Features
- ✋ **All fingers up** → Eraser Mode  
- 👉 **Index finger up** → Move cursor  
- ✌️ **Index + Middle finger up** → Draw  
- 🖱️ **Mouse support** when gestures are off  
- 🎛️ Keyboard shortcuts:
  - `G` → Toggle gesture control  
  - `E` → Toggle eraser  
  - `C` → Clear canvas  
  - `S` → Save current board  

---

## 🧩 Tech Stack
- Python 3.10+
- OpenCV for camera + image handling
- MediaPipe for hand tracking
- PyQt5 for desktop UI
- NumPy for canvas operations

---

## 🖥️ How to Run

```bash

# Install dependencies
pip install -r requirements.txt

# Run the app
python smartboard.py
