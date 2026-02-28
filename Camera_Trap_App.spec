# Camera_Trap_App.spec
# ==================================
import os

project_root = os.getcwd()
block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[
        ('cublasLt64_12.dll', '.'),
        ('cudart64_12.dll', '.'),
        ('cudnn64_9.dll', '.'),
        ('cusparse64_12.dll', '.'),
        ('nvrtc64_120_0.dll', '.'),
        ('opencv_world4120.dll', '.'),
        ('onnxruntime.dll', '.'),
        ('onnxruntime_providers_cuda.dll', '.'),
        ('onnxruntime_providers_shared.dll', '.'),
    ],
    
    datas = [
        (os.path.join(project_root, "yolov5"), "yolov5"),
        (os.path.join(project_root, "best.pt"), "."),
        (os.path.join(project_root, "species.pt"), "."),
        (os.path.join(project_root, "species_labels.txt"), "."),
        (os.path.join(project_root, "bg.png"), "."),
        (os.path.join(project_root, "bg_otp.png"), "."),
        (os.path.join(project_root, "Idock Logo_1.png"), "."),
        (os.path.join(project_root, "idock_icon.ico"), "."),
    ],
    hiddenimports=[
        "onnx2torch",
        "onnx2torch.node_converters",
        "onnx2torch.utils",
        "onnx2torch.onnx_graph",
        "onnx2torch.convert",
        "torch",
        "torchvision",
        "cv2",
        "numpy",
        "PIL",
        "yolov5",
        "yolov5.models",
        "yolov5.utils",
        "yolov5.utils.general",
        "yolov5.utils.torch_utils",
        "yolov5.models.common",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # 🔑 CRITICAL
    name='Camera_Trap_App',
    debug=False,
    strip=False,
    upx=False,
    console=False,
    icon='idock_icon.ico'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name='Camera_Trap_App'
)
