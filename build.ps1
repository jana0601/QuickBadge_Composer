python -m venv .venv_build
.\.venv_build\Scripts\python -m pip install -r requirements.txt
.\.venv_build\Scripts\pyinstaller --noconfirm --onefile --windowed --name qr_overlay app/main.py

