🎯 Camera Trap Application


🔧 Steps to Create the Executable (.exe)

This guide explains how to generate the Windows executable using PyInstaller.

📁 1️⃣ Prepare the Project Folder

    Before building the executable, ensure all required files are placed in the same folder.
    
    Your project folder must contain:
    
    ✅ All Python files (.py)
    
    ✅ All required .dll files
    
    ✅ Model weight files:
    
    best.pt
    
    species.pt
    
    ✅ species_labels.txt
    
    ✅ All required image files (.jpg, .png)
    
    ✅ Camera_Trap_App.spec (Very Important)

🛠 2️⃣ Install PyInstaller

    Open Command Prompt or Terminal and install PyInstaller:
    
    pip install pyinstaller
📂 3️⃣ Navigate to Project Directory

    Move to your project folder:
    
    cd C:\RESQ\2.0\v2
    
    (Replace the path with your actual project location if different.)

🚀 4️⃣ Build the Executable

    Run the following command:
    
    pyinstaller Camera_Trap_App.spec --clean
    
    The --clean option ensures a fresh build.

📦 5️⃣ After Build Completion

    Once the process completes successfully, two new folders will be created:
    
    /build
    /dist
    
    Inside the /dist folder, you will find:
    
    /Camera_Trap_App
    
    Inside this folder, the generated .exe file will be available.

⚠ 6️⃣ Important: Runtime File Requirements

    To successfully run the .exe, you must copy the following files into:
    
    /dist/Camera_Trap_App
    Required Files:
    
    All .dll files
    
    best.pt
    
    species.pt
    
    species_labels.txt
    
    All required .jpg and .png image files
    
    These files must be in the same folder as the .exe file.
    
    🗂 Final Folder Structure Example
    dist/
     └── Camera_Trap_App/
          ├── Camera_Trap_App.exe
          ├── best.pt
          ├── species.pt
          ├── species_labels.txt
          ├── *.dll files
          ├── *.jpg / *.png files
    ▶ Running the Application
    
    After placing all required files in the Camera_Trap_App folder:
    
    👉 Double-click Camera_Trap_App.exe to start the application.

📌 Notes

    Ensure all model and DLL files are compatible with your system.
    
    Missing files will cause the application to fail at runtime.
    
    Always rebuild using --clean if you face issues.
