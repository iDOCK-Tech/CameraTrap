### Camera Trap Application
Steps to Create Executable (.exe)

Follow the steps below carefully to generate the .exe file using PyInstaller.

📌 Step 1: Prepare Project Folder

Ensure that all required files are placed in the same folder.

The folder must contain:

All Python files (.py)

All required .dll files

All model weight files (.pt)

best.pt

species.pt

species_labels.txt

All required image files (.jpg, .png)

Camera_Trap_App.spec (IMPORTANT)

📌 Step 2: Install PyInstaller

Open your terminal or command prompt and run:

pip install pyinstaller
📌 Step 3: Navigate to Project Folder

Move to your project directory:

cd path\to\your\project\folder

Example:

cd C:\RESQ\2.0\v2
📌 Step 4: Build the Executable

Run the following command:

pyinstaller Camera_Trap_App.spec --clean
📌 Step 5: After Build Completes

After the process finishes successfully, two new folders will be created:

/build

/dist

Inside the /dist folder, you will find:

/Camera_Trap_App

Inside this folder, the .exe file will be available.

📌 Step 6: Prepare Runtime Files

To successfully run the .exe, you must copy the following files into the:

/dist/Camera_Trap_App
Required Files:

All .dll files

Model weights:

best.pt

species.pt

species_labels.txt

All .jpg and .png image files

⚠ These files must be present in the same folder as the .exe file for the application to run correctly.

✅ Final Folder Structure Example
dist/
 └── Camera_Trap_App/
      ├── Camera_Trap_App.exe
      ├── best.pt
      ├── species.pt
      ├── species_labels.txt
      ├── *.dll files
      ├── *.jpg / *.png files
🚀 You Are Ready to Run

Double-click the .exe file inside the Camera_Trap_App folder to start the application.
