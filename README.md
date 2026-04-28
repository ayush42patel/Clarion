# 🧠 Clarion AI Smart Blackboard

An AI-powered smart whiteboard application built with computer vision, gesture control, OCR, and LLM integration. This project transforms a webcam into an interactive teaching interface with real-time drawing, recognition, and AI-assisted explanations.

---

## 🚀 Features

### ✍️ Smart Drawing System
- Draw using:
  - Mouse input
  - Hand gestures (via webcam)
- Smooth stroke interpolation
- Adjustable pen & eraser thickness

### 🖐️ Gesture Control (MediaPipe)
- ✌️ Two fingers → Draw  
- 🖐️ Open hand → Erase  
- ☝️ One finger → Move pointer  

---

### 🧠 AI-Powered Analysis
- Extracts:
  - Written text (OCR via EasyOCR)
  - Shapes (Triangle, Circle, Rectangle, Square)
- Sends structured prompt to LLM (Groq API)
- Generates:
  - Explanations
  - Answers
  - Concept breakdowns

---

### 📝 Typing Mode
- Press `Q` to toggle typing
- Type directly on canvas
- Press `Enter` to commit text

---

### 📂 Session Management
- Save sessions automatically:
  - Canvas image
  - AI explanation
  - Metadata (JSON)
- Sidebar to switch between sessions

---

### 📄 Export Notes
- Export AI-generated explanation + board snapshot
- Saves as PDF using ReportLab

---

### ↩️ Undo / Redo
- Supports undo (Ctrl + Z)
- History stack with limit

---

## 🛠️ Tech Stack

| Layer | Technology |
|------|--------|
| UI | PyQt5 |
| Computer Vision | OpenCV |
| Hand Tracking | MediaPipe |
| OCR | EasyOCR |
| AI Model | Groq (LLaMA 3.1) |
| PDF Export | ReportLab |
| Backend Logic | Python |

---

## 📦 Installation

### 1. Clone Repository
```bash
git clone https://github.com/your-username/clarion-ai-blackboard.git
cd clarion-ai-blackboard
```
### 2. Create Virtual Environment
``` bash
python -m venv venv
```

### 3. Activate:

```bash
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Setup Environment Variables

```bash
Create a .env file:

GROQ_API_KEY=your_api_key_here
```

### 5. Run the Application
```bash
python main.py
```
---

## 🎮 Controls

### ⌨️ Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Q` | Toggle typing mode |
| `C` | Clear canvas |
| `S` | Save canvas |
| `G` | Toggle gesture |
| `E` | Toggle eraser |
| `Ctrl + Z` | Undo |

---

### 🖱️ Mouse Controls

- Click + drag → Draw  
- Right click → Alternate draw  

---

## 🧠 AI Workflow

1. Capture board state  
2. Extract:
   - Text (OCR)  
   - Shapes (Computer Vision)  
3. Build structured prompt  
4. Send to LLM  
5. Display explanation  

---

## 📁 Project Structure

```bash
clarion-ai-blackboard/
│
├── main.py
├── sessions/
│ ├── session_YYYYMMDD_HHMMSS/
│ │ ├── board.png
│ │ ├── explanation.txt
│ │ └── session.json
│
├── temp_board.png
├── .env
├── requirements.txt
└── README.md
```
---

## ⚡ Performance Notes

- **OCR optimized with:**
  - Thresholding  
  - Dilation (better stroke detection)  

- **Shape detection uses:**
  - Contour approximation  

- **Gesture smoothing uses:**
  - Exponential moving average  

---

## 🔮 Future Improvements

- 🌐 Web version (React + FastAPI)  
- 🔐 User authentication  
- 📊 Session analytics  
- 📖 Read original content mode  
- 🌍 Multi-language OCR  
- 🧠 Learning history tracking  

---

## ⚠️ Known Limitations

- OCR accuracy depends on:
  - Writing clarity  
  - Stroke thickness  

- Gesture tracking may vary with lighting  

- GPU acceleration not enabled by default  

---

## 🤝 Contributing

Pull requests are welcome.  
For major changes, please open an issue first.

---

## 👨‍💻 Authors

- **Adarsh Kumar Srivatava**  
- **Ayush Patel**  
- **Parveen Chaudhary**
