import sys, os
import traceback

# ---- REQUIRED FOR PYINSTALLER + TORCH ----
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
# ----------------------------------------

import tkinter as tk
from gui import YOLOApp


def launch():
    try:
        root = tk.Tk()
        root.withdraw()
        root.update_idletasks()
        root.deiconify()

        YOLOApp(root)
        root.mainloop()

    except Exception:
        print("\n===== APPLICATION CRASHED =====\n")
        traceback.print_exc()
        print("\nPress ENTER to close...")
        input()   # ⬅ keeps console open


if __name__ == "__main__":
    launch()
