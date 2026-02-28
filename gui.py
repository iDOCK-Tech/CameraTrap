import tkinter as tk
from tkinter import filedialog, messagebox, Canvas
from pathlib import Path
import threading
import math
import time
import os
import subprocess
import sys
import ctypes
import json
import urllib.request
import urllib.error
from PIL import Image, ImageTk, ImageDraw, ImageFilter

from file_utils import is_image, is_video
from detector import run_detection
from config import resource_path

# Backend server configuration
BACKEND_URL = "http://164.68.111.61:5050/"
SESSION_CHECK_INTERVAL = 35000  # Check session every 30 seconds (milliseconds)


class ResolutionScaler:
    """Handle resolution scaling for different screen sizes and DPI"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.scale_factor = 1.0
        self.base_width = 1920
        self.base_height = 1080
        self.dpi_scale = 1.0
        self.screen_width = 1920
        self.screen_height = 1080
    
    def initialize(self, root):
        """Initialize scaling based on screen resolution and DPI"""
        try:
            # Enable DPI awareness on Windows
            if sys.platform == 'win32':
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # Per-monitor DPI aware
                except:
                    try:
                        ctypes.windll.user32.SetProcessDPIAware()
                    except:
                        pass
            
            # Get screen dimensions
            self.screen_width = root.winfo_screenwidth()
            self.screen_height = root.winfo_screenheight()
            
            # Calculate scale factor - ensure minimum of 1.0 for proper sizing
            width_scale = self.screen_width / self.base_width
            height_scale = self.screen_height / self.base_height
            self.scale_factor = max(width_scale, height_scale)
            
            # Ensure scale factor is at least 1.0 for readable UI
            self.scale_factor = max(1.0, min(2.0, self.scale_factor))
            
            # Get DPI scale on Windows
            if sys.platform == 'win32':
                try:
                    self.dpi_scale = ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
                except:
                    self.dpi_scale = 1.0
            
        except Exception as e:
            self.scale_factor = 1.0
            self.dpi_scale = 1.0
    
    def scale(self, value):
        """Scale a value based on resolution"""
        return int(value * self.scale_factor)
    
    def scale_font(self, size):
        """Scale font size - ensure readable fonts"""
        scaled = int(size * self.scale_factor)
        return max(10, scaled)  # Minimum font size of 10
    
    def get_fullscreen_size(self):
        """Get fullscreen dimensions"""
        return self.screen_width, self.screen_height
    
    def get_window_size(self, base_width, base_height):
        """Get scaled window dimensions"""
        return self.scale(base_width), self.scale(base_height)
    
    def get_min_size(self, base_width, base_height):
        """Get scaled minimum window dimensions"""
        return self.scale(base_width), self.scale(base_height)


# Global scaler instance
scaler = ResolutionScaler()


class SelectionCard(tk.Frame):
    """Modern selectable card using standard widgets for reliability"""
    
    def __init__(self, parent, text, value, variable, icon, width=200, height=50, **kwargs):
        super().__init__(parent, bg=ModernColors.SURFACE, highlightthickness=1, 
                         highlightbackground=ModernColors.BORDER, cursor="hand2", **kwargs)
        
        self.text = text
        self.value = value
        self.variable = variable
        self.icon = icon
        
        # Configure frame size and layout
        self.pack_propagate(False)
        self.configure(width=width, height=height)
        
        # Inner layout
        self.inner = tk.Frame(self, bg=ModernColors.SURFACE)
        self.inner.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0, relheight=1.0)
        
        # Radio button (hidden indicator, uses full frame)
        self.rb = tk.Radiobutton(
            self.inner,
            text=f"  {icon}   {text}",
            value=value,
            variable=variable,
            font=("Segoe UI", 12),
            fg=ModernColors.TEXT_SECONDARY,
            bg=ModernColors.SURFACE,
            activebackground=ModernColors.SURFACE_HOVER,
            activeforeground=ModernColors.TEXT_PRIMARY,
            selectcolor=ModernColors.SURFACE_ACTIVE,
            indicatoron=0, # Push button style
            bd=0,
            highlightthickness=0,
            command=self._on_click,
            anchor="w",
            padx=20
        )
        self.rb.pack(fill="both", expand=True)

        # Initial state check
        self._check_state()
        
        # Variable trace
        self.variable.trace_add("write", lambda *args: self._check_state())
        
    def _on_click(self):
        # The radiobutton handles the variable update automatically
        pass

    def _check_state(self):
        # Update colors based on selection
        if self.variable.get() == self.value:
            self.configure(highlightbackground=ModernColors.PRIMARY, highlightthickness=2)
            self.rb.configure(bg=ModernColors.SURFACE_ACTIVE, fg=ModernColors.PRIMARY_DARK, font=("Segoe UI Semibold", 12))
        else:
            self.configure(highlightbackground=ModernColors.BORDER, highlightthickness=1)
            self.rb.configure(bg=ModernColors.SURFACE, fg=ModernColors.TEXT_SECONDARY, font=("Segoe UI", 12))


class CheckboxCard(tk.Frame):
    """Modern checkbox card for multi-selection - same design as SelectionCard"""
    
    def __init__(self, parent, text, value, selected_set, icon, width=200, height=50, on_change=None, **kwargs):
        super().__init__(parent, bg=ModernColors.SURFACE, highlightthickness=1, 
                         highlightbackground=ModernColors.BORDER, cursor="hand2", **kwargs)
        
        self.text = text
        self.value = value
        self.selected_set = selected_set  # A set to track selected values
        self.icon = icon
        self.on_change = on_change
        self.is_selected = tk.BooleanVar(value=False)
        
        # Configure frame size and layout
        self.pack_propagate(False)
        self.configure(width=width, height=height)
        
        # Inner layout
        self.inner = tk.Frame(self, bg=ModernColors.SURFACE)
        self.inner.place(relx=0.5, rely=0.5, anchor="center", relwidth=1.0, relheight=1.0)
        
        # Checkbox styled as button
        self.cb = tk.Checkbutton(
            self.inner,
            text=f"  {icon}   {text}",
            variable=self.is_selected,
            font=("Segoe UI", 12),
            fg=ModernColors.TEXT_SECONDARY,
            bg=ModernColors.SURFACE,
            activebackground=ModernColors.SURFACE_HOVER,
            activeforeground=ModernColors.TEXT_PRIMARY,
            selectcolor=ModernColors.SURFACE_ACTIVE,
            indicatoron=0,  # Push button style
            bd=0,
            highlightthickness=0,
            command=self._on_click,
            anchor="w",
            padx=20
        )
        self.cb.pack(fill="both", expand=True)
        
        # Initial state check
        self._check_state()
        
    def _on_click(self):
        if self.is_selected.get():
            self.selected_set.add(self.value)
        else:
            self.selected_set.discard(self.value)
        self._check_state()
        if self.on_change:
            self.on_change()

    def _check_state(self):
        # Update colors based on selection
        if self.is_selected.get():
            self.configure(highlightbackground=ModernColors.PRIMARY, highlightthickness=2)
            self.cb.configure(bg=ModernColors.SURFACE_ACTIVE, fg=ModernColors.PRIMARY_DARK, font=("Segoe UI Semibold", 12))
        else:
            self.configure(highlightbackground=ModernColors.BORDER, highlightthickness=1)
            self.cb.configure(bg=ModernColors.SURFACE, fg=ModernColors.TEXT_SECONDARY, font=("Segoe UI", 12))

    def set_locked(self, locked):
        """Lock or unlock the checkbox card"""
        if locked:
            self.cb.configure(state="disabled", cursor="")
            self.configure(cursor="")
        else:
            self.cb.configure(state="normal", cursor="hand2")
            self.configure(cursor="hand2")


class ModernColors:
    """Color palette - Futuristic glassy theme with sharp aesthetics"""
    # Primary colors from logo
    PRIMARY = "#00B4D8"          # Bright teal/cyan
    PRIMARY_DARK = "#0077B6"     # Deep ocean blue
    PRIMARY_LIGHT = "#90E0EF"    # Light cyan
    
    # Accent colors
    ACCENT = "#00D4AA"           # Mint green accent
    ACCENT_GLOW = "#48CAE4"      # Glowing cyan
    
    # Background colors - Frosted glass effect
    BG_DARK = "#F0F7FA"          # Ultra light cyan-white
    BG_MEDIUM = "#E3F1F7"        # Slightly deeper cyan-white
    BG_LIGHT = "#D6EBF5"         # Light blue-cyan
    BG_GLASS = "#E8F6FB"         # Frosted glass panel
    
    # Surface colors - Glass cards with depth
    SURFACE = "#FFFFFF"          # Pure white card
    SURFACE_HOVER = "#F5FBFD"    # Subtle hover
    SURFACE_ACTIVE = "#E0F4FA"   # Active state
    SURFACE_GLASS = "#FFFFFFDD"  # Semi-transparent glass
    
    # Text colors
    TEXT_PRIMARY = "#0D1B2A"     # Deep navy text
    TEXT_SECONDARY = "#1B3A4B"   # Dark teal text
    TEXT_MUTED = "#5C7A8A"       # Muted blue-gray
    
    # Status colors - Vibrant
    SUCCESS = "#00D4AA"          # Success green
    WARNING = "#FF9F43"          # Warning orange
    ERROR = "#FF5252"            # Error red
    PROCESSING = "#00B4D8"       # Processing blue
    
    # Border/Glow - Sharp edges
    BORDER = "#B8D8E8"           # Crisp border
    BORDER_SHARP = "#00B4D850"   # Glowing border
    GLOW = "#00B4D830"           # Subtle glow
    SHADOW = "#0077B620"         # Drop shadow


class SplashScreen:
    """Modern splash screen with logo, company name and animated loader"""
    
    def __init__(self, root, on_complete):
        self.root = root
        self.on_complete = on_complete
        self.progress = 0
        self.dots = 0
        
        # Initialize scaler
        scaler.initialize(root)
        
        # Configure window
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        
        # Center on screen with scaling
        width, height = scaler.scale(550), scaler.scale(450)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        x = (screen_w - width) // 2
        y = (screen_h - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        
        # Store dimensions for calculations
        self.width = width
        self.height = height
        
        # Create main canvas
        self.canvas = Canvas(
            self.root, 
            width=width, 
            height=height, 
            bg=ModernColors.BG_DARK, 
            highlightthickness=0
        )
        self.canvas.pack(fill="both", expand=True)
        
        # Draw gradient background
        self._draw_gradient_bg(width, height)
        
        # Load and display logo
        self._load_logo()
        
        # Scaled positions
        center_x = width // 2
        
        # Company name
        self.canvas.create_text(
            center_x, scaler.scale(280),
            text="IDOCK",
            font=("Segoe UI", scaler.scale_font(42), "bold"),
            fill=ModernColors.TEXT_PRIMARY
        )
        
        self.canvas.create_text(
            center_x, scaler.scale(325),
            text="AI Powered-Camera Trap Analysis",
            font=("Segoe UI", scaler.scale_font(13)),
            fill=ModernColors.TEXT_SECONDARY
        )
        
        # Loading bar background - sharper corners (scaled)
        bar_y = scaler.scale(380)
        bar_margin = scaler.scale(125)
        self.bar_start = bar_margin
        self.bar_end = width - bar_margin
        
        self.canvas.create_rectangle(
            self.bar_start, bar_y, self.bar_end, bar_y + scaler.scale(8),
            fill=ModernColors.BG_LIGHT,
            outline=ModernColors.BORDER,
            width=1
        )
        
        # Loading bar progress (will be animated)
        self.progress_bar = self.canvas.create_rectangle(
            self.bar_start + 1, bar_y + 1, self.bar_start + 1, bar_y + scaler.scale(6),
            fill=ModernColors.PRIMARY,
            outline=""
        )
        self.bar_y = bar_y
        
        # Loading text
        self.loading_text = self.canvas.create_text(
            center_x, scaler.scale(410),
            text="Initializing",
            font=("Segoe UI", scaler.scale_font(10)),
            fill=ModernColors.TEXT_MUTED
        )
        
        # Glow particles
        self.particles = []
        self._create_particles()
        
        # Start animation
        self._animate_loading()
    
    def _draw_gradient_bg(self, width, height):
        """Draw a subtle gradient background"""
        # Create gradient effect with rectangles - light to lighter
        for i in range(height):
            # Gradient from light cyan to white
            ratio = i / height
            r = int(200 + ratio * 55)
            g = int(230 + ratio * 25)
            b = int(240 + ratio * 15)
            color = f"#{r:02x}{g:02x}{b:02x}"
            self.canvas.create_line(0, i, width, i, fill=color)
    
    def _load_logo(self):
        """Load and display the company logo"""
        logo_size = scaler.scale(180)
        center_x = self.width // 2
        try:
            logo_path = resource_path("Idock Logo_1.png")
            img = Image.open(logo_path)
            # Resize logo - scaled for visibility
            img = img.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            self.logo_img = ImageTk.PhotoImage(img)
            self.canvas.create_image(center_x, scaler.scale(120), image=self.logo_img)
        except Exception as e:
            # Fallback: draw a placeholder
            half_size = logo_size // 2
            self.canvas.create_oval(
                center_x - half_size, scaler.scale(55),
                center_x + half_size, scaler.scale(205),
                fill="white",
                outline=ModernColors.PRIMARY,
                width=4
            )
            self.canvas.create_text(
                center_x, scaler.scale(130),
                text="iD",
                font=("Segoe UI", scaler.scale_font(48), "bold"),
                fill=ModernColors.PRIMARY
            )
    
    def _create_particles(self):
        """Create floating particles for visual effect"""
        import random
        for _ in range(20):
            x = random.randint(scaler.scale(50), self.width - scaler.scale(50))
            y = random.randint(scaler.scale(50), self.height - scaler.scale(50))
            size = random.randint(2, scaler.scale(6))
            alpha = random.uniform(0.3, 0.7)
            particle = self.canvas.create_oval(
                x, y, x+size, y+size,
                fill=ModernColors.PRIMARY_LIGHT,
                outline=""
            )
            self.particles.append({
                'id': particle,
                'x': x,
                'y': y,
                'dx': random.uniform(-0.5, 0.5),
                'dy': random.uniform(-0.3, -0.8),
                'size': size
            })
    
    def _animate_loading(self):
        """Animate the loading progress"""
        if self.progress < 100:
            self.progress += 2
            
            # Update progress bar with scaled dimensions
            bar_range = self.bar_end - self.bar_start - 2
            bar_width = self.bar_start + 1 + (self.progress / 100 * bar_range)
            self.canvas.coords(self.progress_bar, self.bar_start + 1, self.bar_y + 1, bar_width, self.bar_y + scaler.scale(6))
            
            # Update loading text with animated dots
            self.dots = (self.dots + 1) % 4
            loading_texts = [
                "Initializing",
                "Loading AI Models",
                "Preparing Detection Engine",
                "Almost Ready"
            ]
            text_idx = min(self.progress // 25, 3)
            dots = "." * self.dots
            self.canvas.itemconfig(
                self.loading_text, 
                text=f"{loading_texts[text_idx]}{dots}"
            )
            
            # Animate particles
            self._animate_particles()
            
            self.root.after(50, self._animate_loading)
        else:
            # Complete - transition to main app
            self.root.after(500, self._fade_out)
    
    def _animate_particles(self):
        """Animate floating particles"""
        import random
        for p in self.particles:
            p['y'] += p['dy']
            p['x'] += p['dx']
            
            # Reset particle if it goes off screen
            if p['y'] < 0:
                p['y'] = self.height - scaler.scale(70)
                p['x'] = random.randint(scaler.scale(50), self.width - scaler.scale(50))
            
            self.canvas.coords(
                p['id'],
                p['x'], p['y'],
                p['x'] + p['size'], p['y'] + p['size']
            )
    
    def _fade_out(self):
        """Fade out effect before showing main app"""
        self.on_complete()


class GlassButton(Canvas):
    """Modern glass-effect button with sharp edges and glow"""
    
    def __init__(self, parent, text, command, width=200, height=50, 
                 bg_color=ModernColors.PRIMARY, hover_color=ModernColors.ACCENT,
                 icon=None, **kwargs):
        try:
            parent_bg = parent.cget('bg')
        except:
            parent_bg = ModernColors.SURFACE
        
        super().__init__(
            parent, 
            width=width, 
            height=height, 
            bg=parent_bg,
            highlightthickness=0,
            **kwargs
        )
        
        self.command = command
        self.width = width
        self.height = height
        self.bg_color = bg_color
        self.hover_color = hover_color
        self.text = text
        self.icon = icon
        self.enabled = True
        
        self._draw_button()
        
        # Bind events
        self.bind("<Enter>", self._on_hover)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self.bind("<ButtonRelease-1>", self._on_release)
    
    def _draw_button(self, hover=False, pressed=False):
        self.delete("all")
        
        color = self.hover_color if hover else self.bg_color
        if not self.enabled:
            color = ModernColors.TEXT_MUTED
        
        # Sharp radius for futuristic look
        radius = 8
        
        # Outer glow effect when enabled
        if self.enabled and not pressed:
            self._round_rect(
                2, 2, self.width-2, self.height-2,
                radius=radius+2,
                fill="",
                outline=color,
                width=1
            )
        
        # Main button body
        self._round_rect(
            3, 3, self.width-3, self.height-3,
            radius=radius,
            fill=color if not pressed else ModernColors.SURFACE_ACTIVE,
            outline=""
        )
        
        # Top glass highlight (subtle)
        if self.enabled:
            self.create_rectangle(
                6, 5, self.width-6, self.height//2 - 2,
                fill="",
                outline=""
            )
        
        # Text with shadow for depth
        text_color = "white" if self.enabled else ModernColors.TEXT_MUTED
        
        # Calculate font size based on button height
        font_size = max(13, self.height // 4)
        
        self.create_text(
            self.width//2, self.height//2,
            text=self.text,
            font=("Segoe UI Semibold", font_size),
            fill=text_color
        )
    
    def _round_rect(self, x1, y1, x2, y2, radius=10, **kwargs):
        """Draw a rounded rectangle - sharper corners"""
        points = [
            x1+radius, y1,
            x2-radius, y1,
            x2, y1,
            x2, y1+radius,
            x2, y2-radius,
            x2, y2,
            x2-radius, y2,
            x1+radius, y2,
            x1, y2,
            x1, y2-radius,
            x1, y1+radius,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)
    
    def _on_hover(self, event):
        if self.enabled:
            self._draw_button(hover=True)
            self.config(cursor="hand2")
    
    def _on_leave(self, event):
        self._draw_button()
        self.config(cursor="")
    
    def _on_click(self, event):
        if self.enabled:
            self._draw_button(pressed=True)
    
    def _on_release(self, event):
        if self.enabled:
            self._draw_button(hover=True)
            self.command()
    
    def set_enabled(self, enabled):
        self.enabled = enabled
        self._draw_button()
    
    def set_text(self, text):
        """Update button text"""
        self.text = text
        self._draw_button()
    
    def set_color(self, bg_color, hover_color=None):
        """Update button colors"""
        self.bg_color = bg_color
        self.hover_color = hover_color or bg_color
        self._draw_button()


class ModernEntry(Canvas):
    """Modern styled entry field with sharp glass effect"""
    
    def __init__(self, parent, textvariable, width=400, height=50, placeholder="", **kwargs):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=ModernColors.SURFACE,
            highlightthickness=0,
            **kwargs
        )
        
        self.width = width
        self.height = height
        self.placeholder = placeholder
        
        # Draw background
        self._draw_bg()
        
        # Calculate font size based on height
        font_size = max(13, height // 4)
        
        # Create actual entry widget
        self.entry = tk.Entry(
            self,
            textvariable=textvariable,
            font=("Segoe UI", font_size),
            bg=ModernColors.BG_GLASS,
            fg=ModernColors.TEXT_PRIMARY,
            insertbackground=ModernColors.PRIMARY,
            relief="flat",
            highlightthickness=0,
            width=int(width/10)
        )
        self.create_window(width//2, height//2, window=self.entry, width=width-24)
        
    def _draw_bg(self):
        """Draw the entry background with sharp corners"""
        # Outer border
        self.create_rectangle(
            1, 1, self.width-1, self.height-1,
            fill=ModernColors.BG_GLASS,
            outline=ModernColors.BORDER,
            width=1
        )
        
        # Inner glow line at top
        self.create_line(
            3, 3, self.width-3, 3,
            fill=ModernColors.SURFACE,
            width=1
        )


class CircularProgress(Canvas):
    """Circular progress indicator with modern styling"""
    
    def __init__(self, parent, size=120, thickness=8, **kwargs):
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=ModernColors.SURFACE,
            highlightthickness=0,
            **kwargs
        )
        
        self.size = size
        self.thickness = thickness
        self.progress = 0
        self.center = size // 2
        self.radius = (size - thickness * 2) // 2
        
        self._draw()
    
    def _draw(self):
        self.delete("all")
        
        # Outer glow ring
        self.create_oval(
            self.thickness-2, self.thickness-2,
            self.size - self.thickness+2, self.size - self.thickness+2,
            outline=ModernColors.BORDER,
            width=1
        )
        
        # Background circle
        self.create_oval(
            self.thickness, self.thickness,
            self.size - self.thickness, self.size - self.thickness,
            outline=ModernColors.BG_LIGHT,
            width=self.thickness
        )
        
        # Progress arc with gradient effect
        if self.progress > 0:
            extent = -3.6 * self.progress  # Negative for clockwise
            # Glow arc (slightly larger)
            self.create_arc(
                self.thickness-1, self.thickness-1,
                self.size - self.thickness+1, self.size - self.thickness+1,
                start=90,
                extent=extent,
                outline=ModernColors.PRIMARY_LIGHT,
                width=self.thickness+2,
                style="arc"
            )
            # Main arc
            self.create_arc(
                self.thickness, self.thickness,
                self.size - self.thickness, self.size - self.thickness,
                start=90,
                extent=extent,
                outline=ModernColors.PRIMARY,
                width=self.thickness,
                style="arc"
            )
        
        # Center percentage text
        self.create_text(
            self.center, self.center - 8,
            text=f"{int(self.progress)}%",
            font=("Segoe UI Bold", max(16, self.size // 5)),
            fill=ModernColors.TEXT_PRIMARY
        )
        
        # Sub-text
        self.create_text(
            self.center, self.center + 20,
            text="complete",
            font=("Segoe UI", max(10, self.size // 10)),
            fill=ModernColors.TEXT_MUTED
        )
    
    def set_progress(self, value):
        self.progress = max(0, min(100, value))
        self._draw()


class Visualizer(Canvas):
    """Audio-style visualizer for detection activity"""
    
    def __init__(self, parent, width=300, height=60, bars=20, **kwargs):
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=ModernColors.SURFACE,
            highlightthickness=0,
            **kwargs
        )
        
        self.width = width
        self.height = height
        self.num_bars = bars
        self.bar_width = (width - 20) // bars - 2
        self.bar_heights = [0] * bars
        self.target_heights = [0] * bars
        self.active = False
        
        # Add resize handling to fix width issue
        self.bind("<Configure>", self._on_resize)
        
        self._draw()
    
    def _draw(self):
        self.delete("all")
        
        # Draw sleek background
        self.create_rectangle(
            1, 1, self.width-1, self.height-1,
            fill=ModernColors.BG_GLASS,
            outline=ModernColors.BORDER,
            width=1
        )
        
        # Draw bars with sharp edges
        x = 10
        for i, h in enumerate(self.bar_heights):
            bar_height = max(3, h * (self.height - 16))
            y = self.height - 8 - bar_height
            
            # Color gradient based on height - more vibrant
            if h > 0.7:
                color = ModernColors.ACCENT
            elif h > 0.4:
                color = ModernColors.PRIMARY
            else:
                color = ModernColors.PRIMARY_LIGHT
            
            # Sharp rectangular bars
            self.create_rectangle(
                x, y, x + self.bar_width, self.height - 8,
                fill=color,
                outline=""
            )
            x += self.bar_width + 2
    
    def animate(self):
        """Animate the visualizer bars"""
        import random
        
        if self.active:
            # Generate new target heights
            for i in range(self.num_bars):
                self.target_heights[i] = random.uniform(0.2, 1.0)
        else:
            self.target_heights = [0] * self.num_bars
        
        # Smooth transition
        for i in range(self.num_bars):
            diff = self.target_heights[i] - self.bar_heights[i]
            self.bar_heights[i] += diff * 0.3
        
        self._draw()
        
        if self.active:
            self.after(80, self.animate)
    
    def _on_resize(self, event):
        """Handle resize events"""
        self.width = event.width
        self.height = event.height
        self.bar_width = max(2, (self.width - 20) // self.num_bars - 2)
        self._draw()

    def start(self):
        self.active = True
        self.animate()
    
    def stop(self):
        self.active = False
        self.target_heights = [0] * self.num_bars
        # Fade out animation
        self._fade_out()
    
    def _fade_out(self):
        any_visible = False
        for i in range(self.num_bars):
            if self.bar_heights[i] > 0.01:
                self.bar_heights[i] *= 0.7
                any_visible = True
        
        self._draw()
        
        if any_visible:
            self.after(50, self._fade_out)


class StatusIndicator(Canvas):
    """Status indicator with pulsing animation"""
    
    def __init__(self, parent, size=16, **kwargs):
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=ModernColors.SURFACE,
            highlightthickness=0,
            **kwargs
        )
        
        self.size = size
        self.status = "idle"  # idle, processing, success, error
        self.pulse_size = 0
        self.pulse_dir = 1
        
        self._draw()
    
    def _draw(self):
        self.delete("all")
        
        colors = {
            "idle": ModernColors.TEXT_MUTED,
            "processing": ModernColors.PROCESSING,
            "success": ModernColors.SUCCESS,
            "error": ModernColors.ERROR
        }
        
        color = colors.get(self.status, ModernColors.TEXT_MUTED)
        center = self.size // 2
        
        # Pulse glow for processing
        if self.status == "processing":
            glow_radius = 4 + self.pulse_size
            self.create_oval(
                center - glow_radius, center - glow_radius,
                center + glow_radius, center + glow_radius,
                fill="",
                outline=color,
                width=1
            )
        
        # Main dot
        self.create_oval(
            center - 4, center - 4,
            center + 4, center + 4,
            fill=color,
            outline=""
        )
    
    def set_status(self, status):
        self.status = status
        self._draw()
        
        if status == "processing":
            self._pulse()
    
    def _pulse(self):
        if self.status != "processing":
            return
        
        self.pulse_size += 0.3 * self.pulse_dir
        if self.pulse_size >= 3:
            self.pulse_dir = -1
        elif self.pulse_size <= 0:
            self.pulse_dir = 1
        
        self._draw()
        self.after(50, self._pulse)





class YOLOApp:
    """Main application class with modern UI"""
    
    def __init__(self, root, show_splash=True):
        self.root = root
        
        # Set App User Model ID for Windows Taskbar Icon to separate from Python host
        # This fixes the issue where the taskbar icon remains the default Python feather
        try:
            myappid = 'idock.tech.app.2.0'  # arbitrary string but unique
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except Exception:
            pass
            
        self.stop_flag = threading.Event()
        self.is_running = False
        self.resend_timer_seconds = 0
        self.resend_timer_active = False
        
        # Set window title and icon for branding
        self.root.title("IDOCK Tech Pvt. Ltd.")
        self._set_window_icon()
        
        if show_splash:
            self._show_splash()
        else:
            self._init_main_app()
    
    def _set_window_icon(self):
        """Set the window icon for title bar and taskbar"""
        try:
            # Try .ico file first (best for Windows taskbar)
            ico_path = resource_path("idock_icon.ico")
            if os.path.exists(ico_path):
                self.root.iconbitmap(ico_path)
            else:
                # Convert PNG to ICO on-the-fly for Windows taskbar support
                logo_path = resource_path("Idock Logo_1.png")
                if os.path.exists(logo_path):
                    icon_img = Image.open(logo_path)
                    
                    # Create temporary .ico file with multiple sizes
                    import tempfile
                    temp_ico = os.path.join(tempfile.gettempdir(), "idock_temp_icon.ico")
                    
                    # Create multiple icon sizes for best display
                    icon_sizes = [(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
                    icons = []
                    for size in icon_sizes:
                        resized = icon_img.resize(size, Image.Resampling.LANCZOS)
                        icons.append(resized)
                    
                    # Save as ICO with multiple sizes
                    icons[0].save(temp_ico, format='ICO', sizes=[(s[0], s[1]) for s in icon_sizes], append_images=icons[1:])
                    
                    # Set the icon
                    self.root.iconbitmap(temp_ico)
        except Exception as e:
            print(f"Could not set window icon: {e}")
            # Last resort fallback
            try:
                logo_path = resource_path("Idock Logo_1.png")
                if os.path.exists(logo_path):
                    icon_img = Image.open(logo_path)
                    icon_img = icon_img.resize((32, 32), Image.Resampling.LANCZOS)
                    self.icon_photo = ImageTk.PhotoImage(icon_img)
                    self.root.iconphoto(True, self.icon_photo)
            except:
                pass
    
    def _show_splash(self):
        """Show splash screen before main app"""
        self.splash = SplashScreen(self.root, self._on_splash_complete)
    
    def _on_splash_complete(self):
        """Transition from splash to login screen"""
        # Clear splash screen
        for widget in self.root.winfo_children():
            widget.destroy()
        
        # Show login screen
        self._show_login_screen()
    
    def _make_api_request(self, endpoint, data):
        """Make a POST request to the backend server"""
        try:
            url = f"{BACKEND_URL}{endpoint}"
            json_data = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(
                url,
                data=json_data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=45) as response:
                return json.loads(response.read().decode())
        except urllib.error.URLError as e:
            return {"success": False, "error": "Cannot connect to server. Make sure backend_server.py is running."}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _check_server_health(self):
        """Check if backend server is running"""
        try:
            url = f"{BACKEND_URL}/health"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as response:
                return True
        except:
            return False
    
    def _build_input(self, parent, label_text, var, is_password=False):
        """Helper to build input fields matching m1.py design"""
        f = tk.Frame(parent, bg=ModernColors.SURFACE)
        f.pack(fill="x", pady=6)
        
        tk.Label(f, text=label_text, font=("Segoe UI Bold", 8), fg=ModernColors.TEXT_MUTED, bg=ModernColors.SURFACE).pack(anchor="w")
        
        entry = tk.Entry(
            f, 
            textvariable=var, 
            font=("Segoe UI", 12),
            bg=ModernColors.BG_DARK,
            relief="flat",
            highlightthickness=1,
            highlightbackground=ModernColors.BORDER,
            show="*" if is_password else ""
        )
        entry.pack(fill="x", ipady=8, pady=(5, 0))
        
        if is_password:
             entry.bind('<Return>', lambda e: self._attempt_auth())

    def _show_forgot_password_screen(self):
        """Display forgot password screen with OTP flow"""
        self.auth_mode = "forgot_password"
        
        # Clear/Setup window like OTP screen
        for widget in self.root.winfo_children():
            widget.destroy()

        vcmd = (self.root.register(self._validate_otp_input_length), '%P')
        self.root.configure(bg="#FFFFFF")
        
        # ... (Background setup same as OTP)
        self._setup_background_canvas()

        # Shadow Frame
        shadow_color = "#A0BCCF"
        self.shadow_frame = tk.Frame(self.root, bg=shadow_color, width=550, height=720, bd=0, highlightthickness=0)
        self.shadow_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # Main Card
        card_white = "#FFFFFF"
        self.card = tk.Frame(self.shadow_frame, bg=card_white, padx=50, pady=30, bd=0, highlightthickness=0)
        self.card.place(x=-4, y=-4, width=550, height=720) 
        
        # Logo
        try:
             logo_path = resource_path("Idock Logo_1.png")
             if os.path.exists(logo_path):
                img = Image.open(logo_path)
                img = img.resize((240, 240), Image.Resampling.LANCZOS)
                self.fp_logo_img = ImageTk.PhotoImage(img)
                tk.Label(self.card, image=self.fp_logo_img, bg=card_white, bd=0, highlightthickness=0).pack(pady=(10, 0))
        except:
             pass

        tk.Label(self.card, text="Reset Password", font=("Segoe UI Semibold", 28), fg="#1A1A1A", bg=card_white).pack(pady=(10, 5))
        tk.Label(self.card, text="Enter your email to receive an OTP", font=("Segoe UI", 12), fg="#7A8C94", bg=card_white).pack()

        # Input Area
        input_container = tk.Frame(self.card, bg=card_white, pady=20)
        input_container.pack(fill="x")

        self.fp_email_var = tk.StringVar()
        tk.Label(input_container, text="EMAIL ADDRESS", font=("Segoe UI Bold", 9), fg=ModernColors.TEXT_MUTED, bg=card_white).pack(anchor="w")
        tk.Entry(input_container, textvariable=self.fp_email_var, font=("Segoe UI", 12), bg=ModernColors.BG_DARK, relief="flat", highlightthickness=1, highlightbackground=ModernColors.BORDER).pack(fill="x", ipady=8, pady=(5, 10))

        self.fp_error_var = tk.StringVar()
        self.fp_error_label = tk.Label(self.card, textvariable=self.fp_error_var, font=("Segoe UI", 9), fg=ModernColors.ERROR, bg=card_white)
        self.fp_error_label.pack()

        tk.Button(self.card, text="SEND OTP", command=self._initiate_password_reset, bg="#0077B6", fg="white", font=("Segoe UI Bold", 11), relief="flat", width=30, pady=12, cursor="hand2").pack(pady=20)
        
        # Back Link
        back_lbl = tk.Label(self.card, text="Back to Login", font=("Segoe UI", 10), fg="#7A8C94", bg=card_white, cursor="hand2")
        back_lbl.pack(pady=10)
        back_lbl.bind("<Button-1>", lambda e: self._back_to_login())

    def _initiate_password_reset(self):
        email = self.fp_email_var.get().strip()
        if not email:
            self.fp_error_label.config(fg=ModernColors.ERROR)
            self.fp_error_var.set("Please enter your email")
            return
        
        self.fp_error_label.config(fg=ModernColors.PRIMARY)
        self.fp_error_var.set("Sending OTP...")
        self.root.update()
        
        response = self._make_api_request("/request-otp", {"email": email, "purpose": "password_reset"})
        if response.get("success"):
            self.pending_email = email
            self.pending_otp_test = response.get("otp_for_testing")
            self._show_reset_password_otp_screen()
        else:
            self.fp_error_label.config(fg=ModernColors.ERROR)
            self.fp_error_var.set(response.get("error", "Failed to send OTP"))

    def _show_reset_password_otp_screen(self):
        # reuse OTP screen but point verify to _verify_reset_otp
        self._show_otp_screen(purpose="password_reset")
        # Override the verify command
        self.verify_btn.configure(command=self._verify_reset_otp)
        # Verify on enter key
        self.otp_entry.bind('<Return>', lambda e: self._verify_reset_otp())

    def _verify_reset_otp(self):
        otp = self.otp_var.get()
        if len(otp) != 6:
            self.otp_error_var.set("Please enter a valid 6-digit OTP")
            return

        # Go to New Password Screen (client-side validation passed)
        self._show_new_password_screen(otp)

    def _show_new_password_screen(self, otp):
        # Re-use card layout logic...
        for widget in self.card.winfo_children():
            widget.destroy()
            
        # Logo
        try:
             tk.Label(self.card, image=self.otp_logo_img, bg="#FFFFFF", bd=0).pack(pady=(10, 0)) # Reuse img
        except: pass

        tk.Label(self.card, text="New Password", font=("Segoe UI Semibold", 28), fg="#1A1A1A", bg="#FFFFFF").pack(pady=(10, 5))
        
        container = tk.Frame(self.card, bg="#FFFFFF", pady=20)
        container.pack(fill="x", padx=20)

        self.reset_pass_var = tk.StringVar()
        self.reset_confirm_var = tk.StringVar()
        
        tk.Label(container, text="NEW PASSWORD", font=("Segoe UI Bold", 9), fg=ModernColors.TEXT_MUTED, bg="#FFFFFF").pack(anchor="w")
        tk.Entry(container, textvariable=self.reset_pass_var, font=("Segoe UI", 12), bg=ModernColors.BG_DARK, show="*", relief="flat").pack(fill="x", ipady=8, pady=(5, 10))
        
        tk.Label(container, text="CONFIRM PASSWORD", font=("Segoe UI Bold", 9), fg=ModernColors.TEXT_MUTED, bg="#FFFFFF").pack(anchor="w")
        tk.Entry(container, textvariable=self.reset_confirm_var, font=("Segoe UI", 12), bg=ModernColors.BG_DARK, show="*", relief="flat").pack(fill="x", ipady=8, pady=(5, 10))

        self.rp_error_var = tk.StringVar()
        tk.Label(self.card, textvariable=self.rp_error_var, font=("Segoe UI", 9), fg=ModernColors.ERROR, bg="#FFFFFF").pack()

        tk.Button(self.card, text="RESET PASSWORD", command=lambda: self._finalize_password_reset(otp), bg="#0077B6", fg="white", font=("Segoe UI Bold", 11), relief="flat", width=30, pady=12, cursor="hand2").pack(pady=20)

    def _finalize_password_reset(self, otp):
        p1 = self.reset_pass_var.get()
        p2 = self.reset_confirm_var.get()
        
        if len(p1) < 6:
            self.rp_error_var.set("Password must be at least 6 characters")
            return
        if p1 != p2:
            self.rp_error_var.set("Passwords do not match")
            return
            
        response = self._make_api_request("/reset-password", {
            "email": self.pending_email,
            "otp": otp,
            "password": p1
        })
        
        if response.get("success"):
            messagebox.showinfo("Success", "Password reset successfully. Please login.")
            self._show_login_screen()
        else:
            self.rp_error_var.set(response.get("error", "Reset failed"))

    def _setup_background_canvas(self):
        # Unified background setup for OTP/Forgot Password
        try:
            if sys.platform == "win32":
                self.root.state('zoomed') 
            else:
                self.root.attributes('-fullscreen', True)

            # Ensure we get the actual window size after maximizing
            self.root.update()
            width = self.root.winfo_width()
            height = self.root.winfo_height()
                
            bg_otp_path = resource_path("bg_otp.png")
            
            # Create MAIN CANVAS for everything
            self.main_canvas = Canvas(self.root, width=width, height=height, highlightthickness=0)
            self.main_canvas.place(x=0, y=0, width=width, height=height)

            if os.path.exists(bg_otp_path):
                bg_raw = Image.open(bg_otp_path)
                # Resize to cover screen
                bg_resized = bg_raw.resize((width, height), Image.Resampling.LANCZOS)
                self.bg_otp_photo = ImageTk.PhotoImage(bg_resized)
                self.main_canvas.create_image(0, 0, image=self.bg_otp_photo, anchor="nw")
            else:
                 self._draw_screen_gradient(self.main_canvas, width, height)

            # ADD BUBBLE ANIMATIONS ON TOP
            self.otp_particles = []
            self._create_screen_particles(self.main_canvas, width, height, self.otp_particles)
            self._animate_otp_particles()
            
            return self.main_canvas
        except Exception as e:
            print(f"Error loading background: {e}")
            return None

    def _show_auth_screen(self, mode="login"):
        """Display authentication screen (login or signup) with professional UI"""
        self.auth_mode = mode  # "login" or "signup"
        self.root.overrideredirect(False)
        self.root.attributes('-topmost', False)
        
        # 1. AUTO-RESOLUTION FULL SCREEN
        if sys.platform == "win32":
            self.root.state('zoomed') 
        else:
            self.root.attributes('-fullscreen', True)
            
        self.root.configure(bg=ModernColors.BG_DARK)

        # Paths
        bg_otp_path = resource_path("bg_otp.png")
        bg_image_path = resource_path("bg.png")
        logo_path = resource_path("Idock Logo_1.png")

        # --- BACKGROUND CANVAS WITH BUBBLES ---
        try:
           # Maximize window first to get dimensions
           self.root.update()
           # Use winfo_width/height which reflects the actual window size upon maximize
           screen_width = self.root.winfo_width() 
           screen_height = self.root.winfo_height()
           
           # If window size is weirdly small (start up), use screen size
           if screen_width < 800: screen_width = self.root.winfo_screenwidth()
           if screen_height < 600: screen_height = self.root.winfo_screenheight()

           self.login_canvas = Canvas(self.root, width=screen_width, height=screen_height, highlightthickness=0)
           self.login_canvas.place(x=0, y=0, relwidth=1, relheight=1)

           if os.path.exists(bg_otp_path):
               bg_full_img = Image.open(bg_otp_path)
               bg_full_img = bg_full_img.resize((screen_width, screen_height), Image.Resampling.LANCZOS)
               self.bg_full_photo = ImageTk.PhotoImage(bg_full_img)
               self.login_canvas.create_image(0, 0, image=self.bg_full_photo, anchor="nw")
           else:
               self._draw_screen_gradient(self.login_canvas, screen_width, screen_height)
               
           # ADD BUBBLES
           self.login_particles = []
           self._create_screen_particles(self.login_canvas, screen_width, screen_height, self.login_particles)
           self._animate_login_particles()
           
        except Exception as e:
            print(f"Main background load failed: {e}")
            self.root.configure(bg=ModernColors.BG_DARK)

        # Main Container (Glass Card)
        card_w_rel = 0.7
        card_h_rel = 0.75  # INCREASED HEIGHT FOR SIGNUP/BUTTON VISIBILITY
        
        self.glass_card = tk.Frame(self.root, bg=ModernColors.SURFACE, bd=0)
        self.glass_card.place(relx=0.5, rely=0.5, anchor="center", relwidth=card_w_rel, relheight=card_h_rel)
        
        # Add shadow/border effect
        self.glass_card.configure(highlightbackground=ModernColors.BORDER, highlightthickness=1)

        # LEFT SIDE: THE LEOPARD IMAGE (bg.png)
        self.left_pane = tk.Frame(self.glass_card, bg="black")
        self.left_pane.place(relx=0, rely=0, relwidth=0.45, relheight=1)

        try:
            if os.path.exists(bg_image_path):
                # We size to fit the pane or height
                bg_img = Image.open(bg_image_path)
                # Ensure we scale to cover the pane height (approx card_h_rel * screen_height)
                target_h = int(screen_height * card_h_rel)
                target_w = int(target_h * (bg_img.width / bg_img.height)) # Keep aspect ratio
                
                bg_img = bg_img.resize((target_w, target_h), Image.Resampling.LANCZOS) 
                
                self.bg_photo = ImageTk.PhotoImage(bg_img)
                bg_label = tk.Label(self.left_pane, image=self.bg_photo, bg="black")
                bg_label.pack(fill="both", expand=True) # Center the image in the pane
            else:
                 tk.Label(self.left_pane, text="IDOCK", fg="white", bg=ModernColors.PRIMARY_DARK, font=("Arial", 20)).pack(expand=True)
        except Exception as e:
             tk.Label(self.left_pane, text="IDOCK", fg="white", bg=ModernColors.PRIMARY_DARK, font=("Arial", 20)).pack(expand=True)

        # RIGHT SIDE: THE LOGIN FORM
        self.right_pane = tk.Frame(self.glass_card, bg=ModernColors.SURFACE, padx=40)
        self.right_pane.place(relx=0.45, rely=0, relwidth=0.55, relheight=1)

        # LOGO
        try:
            if os.path.exists(logo_path):
                logo_img = Image.open(logo_path)
                logo_size = 180 if mode == "signup" else 220
                logo_img = logo_img.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
                self.logo_photo = ImageTk.PhotoImage(logo_img)
                tk.Label(self.right_pane, image=self.logo_photo, bg=ModernColors.SURFACE).pack(pady=(1 if mode=="login" else 5))
            else:
                 tk.Label(self.right_pane, text="IDOCK", font=("Arial", 24, "bold"), fg=ModernColors.PRIMARY, bg=ModernColors.SURFACE).pack(pady=(40, 10))
        except:
             tk.Label(self.right_pane, text="IDOCK", font=("Arial", 24, "bold"), fg=ModernColors.PRIMARY, bg=ModernColors.SURFACE).pack(pady=(40, 10))

        # HEADERS
        title_text = "Welcome Back" if mode == "login" else "Create Account"
        tk.Label(self.right_pane, text=title_text, font=("Segoe UI Semibold", 22), fg=ModernColors.TEXT_PRIMARY, bg=ModernColors.SURFACE).pack()
        
        subtitle = "IDOCK Technologies Camera Trap Analysis" if mode == "login" else "Join IDOCK Technologies Analysis Platform"
        tk.Label(self.right_pane, text=subtitle, font=("Segoe UI", 10), fg=ModernColors.TEXT_MUTED, bg=ModernColors.SURFACE).pack(pady=(5, 10))

        # INPUTS
        self.username_var = tk.StringVar()
        self._build_input(self.right_pane, "USERNAME", self.username_var)
        
        # Email (only for signup)
        if mode == "signup":
            self.email_var = tk.StringVar()
            self._build_input(self.right_pane, "EMAIL", self.email_var)

        # Password
        self.password_var = tk.StringVar()
        self._build_input(self.right_pane, "PASSWORD", self.password_var, is_password=True)
        
        # Forgot Password Link (Only Login)
        if mode == "login":
            fp_frame = tk.Frame(self.right_pane, bg=ModernColors.SURFACE)
            fp_frame.pack(fill="x")
            fp_lbl = tk.Label(fp_frame, text="Forgot Password?", font=("Segoe UI", 9), fg=ModernColors.PRIMARY, bg=ModernColors.SURFACE, cursor="hand2")
            fp_lbl.pack(side="right")
            fp_lbl.bind("<Button-1>", lambda e: self._show_forgot_password_screen())

        # Confirm Password (only for signup)
        if mode == "signup":
            self.confirm_password_var = tk.StringVar()
            self._build_input(self.right_pane, "CONFIRM PASSWORD", self.confirm_password_var, is_password=True)
            
        # Error message label
        self.login_error_var = tk.StringVar()
        self.login_error_label = tk.Label(
            self.right_pane,
            textvariable=self.login_error_var,
            font=("Segoe UI", 9),
            fg=ModernColors.ERROR,
            bg=ModernColors.SURFACE,
            wraplength=300
        )
        self.login_error_label.pack(pady=5)
        
        # Primary action button
        btn_text = "ACCESS ACCOUNT" if mode == "login" else "CREATE ACCOUNT"
        
        self.login_btn = tk.Button(
            self.right_pane, 
            text=btn_text, 
            command=self._attempt_auth,
            bg=ModernColors.PRIMARY, 
            fg="white", 
            font=("Segoe UI Bold", 11),
            relief="flat",
            padx=20,
            pady=12,
            cursor="hand2",
            activebackground=ModernColors.PRIMARY_DARK
        )
        self.login_btn.pack(fill="x", pady=(15, 0))
        
        # Toggle to other mode
        toggle_text = "New here? Create Account" if mode == "login" else "Already have an account? Login"
        
        toggle_btn = tk.Label(
            self.right_pane,
            text=toggle_text,
            font=("Segoe UI", 9),
            fg=ModernColors.PRIMARY,
            bg=ModernColors.SURFACE,
            cursor="hand2"
        )
        toggle_btn.pack(pady=10)
        toggle_btn.bind("<Button-1>", lambda e: self._switch_auth_mode())
    
    def _show_login_screen(self):
        """Display login screen - wrapper for _show_auth_screen"""
        self._show_auth_screen(mode="login")
    
    def _switch_auth_mode(self):
        """Switch between login and signup modes"""
        for widget in self.root.winfo_children():
            widget.destroy()
        new_mode = "signup" if self.auth_mode == "login" else "login"
        self._show_auth_screen(mode=new_mode)
    
    def _attempt_auth(self):
        """Handle login or signup attempt via backend server"""
        username = self.username_var.get().strip()
        password = self.password_var.get()
        
        # Validation
        if not username:
            self.login_error_var.set("Please enter a username")
            return
        if not password:
            self.login_error_var.set("Please enter a password")
            return
        
        # Check server connectivity
        if not self._check_server_health():
            self.login_error_var.set("Cannot connect to server. Please ensure backend_server.py is running.")
            return
        
        self.login_error_label.config(fg=ModernColors.PRIMARY)
        self.login_error_var.set("Please wait...")
        self.root.update()
        
        if self.auth_mode == "signup":
            # Signup flow
            email = self.email_var.get().strip()
            confirm_password = self.confirm_password_var.get()
            
            if not email:
                self.login_error_var.set("Please enter your email")
                return
            if password != confirm_password:
                self.login_error_var.set("Passwords do not match")
                return
            if len(password) < 6:
                self.login_error_var.set("Password must be at least 6 characters")
                return
            
            response = self._make_api_request("/signup", {
                "username": username,
                "email": email,
                "password": password
            })
            
            if response.get("success"):
                self.pending_email = email
                self.pending_otp_test = response.get("otp_for_testing")  # For testing without email
                self._show_otp_screen(purpose="signup")
            else:
                self.login_error_var.set(response.get("error", "Signup failed"))
        
        else:
            # Login flow
            response = self._make_api_request("/login", {
                "username": username,
                "password": password
            })
            
            if response.get("success"):
                self.pending_email = response.get("email")
                self.pending_otp_test = response.get("otp_for_testing")  # For testing without email
                self._show_otp_screen(purpose="login")
            else:
                self.login_error_var.set(response.get("error", "Login failed"))
    
    def _attempt_login(self):
        """Legacy method - redirects to _attempt_auth"""
        self._attempt_auth()

    def _draw_screen_gradient(self, canvas, width, height):
        """Draw a subtle gradient background on a canvas"""
        for i in range(height):
            ratio = i / height
            r = int(200 + ratio * 55)
            g = int(230 + ratio * 25)
            b = int(240 + ratio * 15)
            color = f"#{r:02x}{g:02x}{b:02x}"
            canvas.create_line(0, i, width, i, fill=color)

    def _create_screen_particles(self, canvas, width, height, particles_list):
        """Create floating particles/bubbles for visual effect - matches splash screen style"""
        import random
        # More particles with varied sizes for a bubbly effect
        for _ in range(25):
            x = random.randint(20, width - 20)
            y = random.randint(20, height - 20)
            size = random.randint(4, 14)  # Larger bubbles
            
            # Vary colors between primary light and accent glow
            colors = [ModernColors.PRIMARY_LIGHT, ModernColors.ACCENT_GLOW, ModernColors.PRIMARY, "#90E0EF", "#48CAE4"]
            color = random.choice(colors)
            
            # Create bubble with slight transparency effect (lighter fill)
            particle = canvas.create_oval(
                x, y, x+size, y+size,
                fill=color,
                outline=""
            )
            particles_list.append({
                'id': particle,
                'canvas': canvas,
                'x': x,
                'y': y,
                'dx': random.uniform(-0.5, 0.5),
                'dy': random.uniform(-0.8, -0.3),  # Float upward
                'size': size,
                'width': width,
                'height': height
            })

    def _animate_login_particles(self):
        """Animate floating particles on login screen"""
        if not hasattr(self, 'login_canvas') or not self.login_canvas.winfo_exists():
            return
        self._animate_particles_generic(self.login_particles)
        self.root.after(50, self._animate_login_particles)

    def _animate_otp_particles(self):
        """Animate floating particles on OTP screen"""
        if not hasattr(self, 'otp_canvas') or not self.otp_canvas.winfo_exists():
            return
        self._animate_particles_generic(self.otp_particles)
        self.root.after(50, self._animate_otp_particles)

    def _animate_particles_generic(self, particles_list):
        """Generic particle animation logic"""
        import random
        for p in particles_list:
            p['y'] += p['dy']
            p['x'] += p['dx']
            
            # Reset particle if it goes off screen
            if p['y'] < 0:
                p['y'] = p['height'] - 50
                p['x'] = random.randint(30, p['width'] - 30)
            
            try:
                p['canvas'].coords(
                    p['id'],
                    p['x'], p['y'],
                    p['x'] + p['size'], p['y'] + p['size']
                )
            except:
                pass

    def _validate_otp_input_length(self, P):
        """Validate OTP input (m2.py style)"""
        if P == "" or (P.isdigit() and len(P) <= 6):
            return True
        return False

    def _show_otp_screen(self, purpose="login"):
        """Display OTP verification screen with professional UI (m2.py style)"""
        self.otp_purpose = purpose
        
        # 1. Clear previous screen
        for widget in self.root.winfo_children():
            widget.destroy()

        # 2. Setup validation
        vcmd = (self.root.register(self._validate_otp_input_length), '%P')
        
        # 3. Background Setup (using Unified Helper)
        canvas = self._setup_background_canvas()
        if not canvas:
            # Fallback if canvas setup fails? although helper is robust
            pass

        # 4. Shadow Frame (m2.py style) - placed on top of canvas/root
        shadow_color = "#A0BCCF"
        self.shadow_frame = tk.Frame(
            self.root, 
            bg=shadow_color, 
            width=550, 
            height=720,
            bd=0,
            highlightthickness=0
        )
        self.shadow_frame.place(relx=0.5, rely=0.5, anchor="center")
        
        # 5. Main Card Frame
        card_white = "#FFFFFF"
        self.card = tk.Frame(
            self.shadow_frame, 
            bg=card_white, 
            padx=50, 
            pady=30,
            bd=0,
            highlightthickness=0
        )
        self.card.place(x=-4, y=-4, width=550, height=720) 

        # 6. Logo
        logo_path = resource_path("Idock Logo_1.png")
        try:
             if os.path.exists(logo_path):
                img = Image.open(logo_path)
                img = img.resize((240, 240), Image.Resampling.LANCZOS)
                self.otp_logo_img = ImageTk.PhotoImage(img)
                logo_label = tk.Label(self.card, image=self.otp_logo_img, bg=card_white, bd=0, highlightthickness=0)
                logo_label.pack(pady=(10, 0))
        except:
             tk.Label(self.card, text="IDOCK", font=("Arial", 28, "bold"), fg="#0077B6", bg=card_white).pack(pady=40)

        # 7. Headings
        title = "Security Check"
        if purpose == "password_reset":
            title = "Reset Password"
            
        tk.Label(
            self.card, 
            text=title, 
            font=("Segoe UI Semibold", 28), 
            fg="#1A1A1A", 
            bg=card_white,
            bd=0, highlightthickness=0
        ).pack(pady=(10, 5))

        email_display = getattr(self, 'pending_email', 'your email')
        otp_hint = ""
        if hasattr(self, 'pending_otp_test') and self.pending_otp_test:
            otp_hint = f"\n(Test: {self.pending_otp_test})"

        tk.Label(
            self.card, 
            text=f"Enter the 6-digit OTP sent to\n{email_display}{otp_hint}", 
            font=("Segoe UI", 12), 
            fg="#7A8C94", 
            bg=card_white,
            bd=0, highlightthickness=0,
            justify="center"
        ).pack()

        # 8. OTP Input Area
        self.otp_container = tk.Frame(self.card, bg=card_white, pady=30, bd=0, highlightthickness=0)
        self.otp_container.pack()

        self.otp_var = tk.StringVar()
        self.otp_entry = tk.Entry(
            self.otp_container,
            textvariable=self.otp_var,
            font=("Courier", 36, "bold"), 
            justify="center",
            width=8,
            bd=0,
            highlightthickness=0,
            bg=card_white,
            fg="#1A1A1A",
            insertbackground="#0077B6", # Cursor color
            validate='key',
            validatecommand=vcmd
        )
        self.otp_entry.pack()
        self.otp_entry.focus_set() 
        self.otp_entry.bind('<Return>', lambda e: self._verify_otp())
        
        # The visual line underneath
        line = tk.Frame(self.otp_container, bg="#CCD6DD", height=3, width=320, bd=0, highlightthickness=0)
        line.pack(pady=(5, 0))
        
        # Error Label
        self.otp_error_var = tk.StringVar()
        self.otp_error_label = tk.Label(
            self.card,
            textvariable=self.otp_error_var,
            font=("Segoe UI", 10),
            fg=ModernColors.ERROR,
            bg=card_white
        )
        self.otp_error_label.pack(pady=(5, 5))

        # 9. Verify Button
        self.verify_btn = tk.Button(
            self.card, 
            text="VERIFY IDENTITY", 
            command=self._verify_otp,
            bg="#0077B6", 
            fg="white", 
            font=("Segoe UI Bold", 14),
            relief="flat",
            width=30,        
            pady=18,        
            cursor="hand2",
            activebackground="#005F92",
            activeforeground="white",
            bd=0,
            highlightthickness=0
        )
        self.verify_btn.pack(pady=(20, 10))

        # 10. Footer (Resend / Back)
        footer_frame = tk.Frame(self.card, bg=card_white)
        footer_frame.pack(pady=10)
        
        # Resend OTP with timer
        resend_container = tk.Frame(footer_frame, bg=card_white)
        resend_container.pack(side="left", padx=15)
        
        self.resend_lbl = tk.Label(resend_container, text="Resend OTP", font=("Segoe UI", 10, "bold"), fg="#CCCCCC", bg=card_white, cursor="arrow")
        self.resend_lbl.pack(side="left")
        self.resend_lbl.bind("<Button-1>", lambda e: self._resend_otp())
        
        self.resend_timer_lbl = tk.Label(resend_container, text="(30s)", font=("Segoe UI", 9), fg="#7A8C94", bg=card_white)
        self.resend_timer_lbl.pack(side="left", padx=(5, 0))
        
        back_lbl = tk.Label(footer_frame, text="Back to Login", font=("Segoe UI", 10), fg="#7A8C94", bg=card_white, cursor="hand2")
        back_lbl.pack(side="left", padx=15)
        back_lbl.bind("<Button-1>", lambda e: self._back_to_login())
        
        # Start the resend timer (30 seconds)
        self._start_resend_timer()
    
    def _start_resend_timer(self):
        """Start 30-second countdown timer for resend OTP button"""
        self.resend_timer_seconds = 30
        self.resend_timer_active = True
        self._update_resend_timer()
    
    def _update_resend_timer(self):
        """Update the resend timer countdown"""
        if not self.resend_timer_active or not hasattr(self, 'resend_timer_lbl'):
            return
        
        if not self.resend_timer_lbl.winfo_exists():
            self.resend_timer_active = False
            return
        
        if self.resend_timer_seconds > 0:
            # Update timer display
            self.resend_timer_lbl.config(text=f"({self.resend_timer_seconds}s)")
            self.resend_lbl.config(fg="#CCCCCC", cursor="arrow")
            self.resend_timer_seconds -= 1
            self.root.after(1000, self._update_resend_timer)
        else:
            # Enable resend button
            self.resend_timer_lbl.config(text="")
            self.resend_lbl.config(fg="#0077B6", cursor="hand2")
            self.resend_timer_active = False
    
    def _resend_otp(self):
        """Request a new OTP from the server"""
        # Check if timer is still active
        if self.resend_timer_active and self.resend_timer_seconds > 0:
            return
        
        if not hasattr(self, 'pending_email') or not self.pending_email:
            self.otp_error_label.config(fg=ModernColors.ERROR)
            self.otp_error_var.set("Session expired. Please start again.")
            return
        
        self.otp_error_label.config(fg=ModernColors.PRIMARY)
        self.otp_error_var.set("Sending new OTP...")
        self.root.update()
        
        response = self._make_api_request("/request-otp", {
            "email": self.pending_email,
            "purpose": getattr(self, 'otp_purpose', 'login')
        })
        
        if response.get("success"):
            self.pending_otp_test = response.get("otp_for_testing")
            msg = "New OTP sent!"
            if self.pending_otp_test:
                msg += f" (Test: {self.pending_otp_test})"
            self.otp_error_label.config(fg=ModernColors.SUCCESS)
            self.otp_error_var.set(msg)
            # Restart the timer
            self._start_resend_timer()
        else:
            self.otp_error_label.config(fg=ModernColors.ERROR)
            self.otp_error_var.set(response.get("error", "Failed to resend OTP"))
    
    def _back_to_login(self):
        """Go back to login screen"""
        for widget in self.root.winfo_children():
            widget.destroy()
        self._show_auth_screen(mode="login")

    def _verify_otp(self):
        """Verify the entered OTP with the backend server"""
        otp = self.otp_var.get().strip()
        
        # Basic validation
        if len(otp) != 6 or not otp.isdigit():
            self.otp_error_label.config(fg=ModernColors.ERROR)
            self.otp_error_var.set("Please enter a valid 6-digit code")
            return
        
        if not hasattr(self, 'pending_email') or not self.pending_email:
            self.otp_error_label.config(fg=ModernColors.ERROR)
            self.otp_error_var.set("Session expired. Please start again.")
            return
        
        self.otp_error_label.config(fg=ModernColors.TEXT_MUTED)
        self.otp_error_var.set("Verifying...")
        self.root.update()
        
        # Verify with backend server
        response = self._make_api_request("/verify-otp", {
            "email": self.pending_email,
            "otp": otp
        })
        
        if response.get("success"):
            # Success - Store session info and load Main App
            self.otp_error_label.config(fg=ModernColors.SUCCESS)
            purpose = response.get("purpose", "")
            
            # Check if this is a pending approval signup
            if response.get("pending_approval"):
                self.otp_error_var.set("Request submitted! Waiting for admin approval...")
                self.root.update()
                self.root.after(1500, lambda: self._show_pending_approval_message())
                return
            
            # Store session credentials for single-device login
            self.current_username = response.get("username")
            self.session_token = response.get("session_token")
            
            if purpose == "signup":
                self.otp_error_var.set("Account created successfully! Loading...")
            else:
                self.otp_error_var.set("Verified! Loading application...")
            self.root.update()
            self.root.after(1000, self._load_main_app)
        else:
            self.otp_error_label.config(fg=ModernColors.ERROR)
            self.otp_error_var.set(response.get("error", "Verification failed"))
    
    def _show_pending_approval_message(self):
        """Show message that registration is pending admin approval"""
        messagebox.showinfo(
            "Registration Submitted",
            "Your registration request has been submitted!\n\n"
            "You will be able to login once the admin approves your request.\n"
            "You will receive an email notification shortly.\n\n"
            "Please check your email for updates."
        )
        # Go back to login screen
        self._back_to_login()
    
    def _load_main_app(self):
        """Load the main application after successful verification"""
        for widget in self.root.winfo_children():
            widget.destroy()
        self.root.resizable(True, True)
        self._init_main_app()
        
        # Start session validation check (single-device login)
        self._start_session_validation()
    
    def _start_session_validation(self):
        """Start periodic session validation to enforce single-device login"""
        if hasattr(self, 'session_token') and self.session_token:
            self._validate_session()
    
    def _validate_session(self):
        """Check if current session is still valid"""
        if not hasattr(self, 'session_token') or not self.session_token:
            return
        
        try:
            response = self._make_api_request("/validate-session", {
                "username": getattr(self, 'current_username', ''),
                "session_token": self.session_token
            })
            
            if response.get("success") and not response.get("valid", True):
                # Session invalidated (logged in from another device)
                self._handle_session_invalidated(response.get("reason", "Session expired"))
                return
        except Exception as e:
            # Connection error - don't logout, just skip this check
            pass
        
        # Schedule next check
        if hasattr(self, 'root') and self.root.winfo_exists():
            self.root.after(SESSION_CHECK_INTERVAL, self._validate_session)
    
    def _handle_session_invalidated(self, reason):
        """Handle when session is invalidated (logged in from another device)"""
        # Stop any running detection
        if hasattr(self, 'is_running') and self.is_running:
            self.stop_flag.set()
        
        # Clear session data
        self.session_token = None
        self.current_username = None
        
        # Show message and redirect to login
        messagebox.showwarning(
            "Session Ended",
            f"{reason}\n\nYou will be redirected to the login screen."
        )
        
        # Redirect to login
        for widget in self.root.winfo_children():
            widget.destroy()
        self._show_auth_screen(mode="login")
    
    def _confirm_logout(self):
        """Show confirmation dialog before logout"""
        result = messagebox.askyesno(
            "Confirm Logout",
            "Are you sure you want to logout?\n\nAny running detection will be stopped."
        )
        if result:
            self._logout()
    
    def _logout(self):
        """Logout current user and return to login screen"""
        # Stop any running detection
        if hasattr(self, 'is_running') and self.is_running:
            self.stop_flag.set()
        
        # Notify server about logout
        if hasattr(self, 'session_token') and self.session_token:
            try:
                self._make_api_request("/logout", {
                    "username": getattr(self, 'current_username', ''),
                    "session_token": self.session_token
                })
            except:
                pass
        
        # Clear session data
        self.session_token = None
        self.current_username = None
        
        # Return to login screen
        for widget in self.root.winfo_children():
            widget.destroy()
        self._show_auth_screen(mode="login")
    
    def _init_main_app(self):
        """Initialize the main application UI"""
        self.root.overrideredirect(False)
        self.root.attributes('-topmost', False)
        self.root.title("IDOCK Tech Pvt. Ltd.")
        self.root.configure(bg=ModernColors.BG_DARK)
        
        # Set fullscreen mode
        self.root.state('zoomed')  # Windows fullscreen (maximized)
        
        # Alternative: True fullscreen (no title bar) - uncomment if preferred
        # self.root.attributes('-fullscreen', True)
        
        # Bind Escape to exit fullscreen
        self.root.bind('<Escape>', lambda e: self.root.state('normal'))
        self.root.bind('<F11>', lambda e: self._toggle_fullscreen())
        
        # Variables
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.total_var = tk.StringVar(value="0")
        self.progress_var = tk.DoubleVar()
        self.device_var = tk.StringVar(value="Detecting...")
        self.status_var = tk.StringVar(value="Ready")
        self.files_processed_var = tk.StringVar(value="0 / 0")
        self.last_excel_path = None  # Store last generated Excel path
        
        # Detection mode and class selection variables
        self.detection_mode = tk.StringVar(value="")  # "human", "animal", or "specific"
        self.selected_specific_animals = set()  # Set to track selected specific animals (leopard, tiger, hyena, elephant)
        self.specific_animal_classes = ["leopard", "tiger", "hyena", "elephant"]
        
        # Keep for backwards compatibility
        self.selected_classes = set()  # Will be populated based on selection
        self.detection_classes = ["leopard", "tiger", "hyena", "elephant"]
        
        self._build_ui()
    
    def _toggle_fullscreen(self):
        """Toggle between fullscreen and windowed mode"""
        if self.root.state() == 'zoomed':
            self.root.state('normal')
        else:
            self.root.state('zoomed')
    
    def _build_ui(self):
        """Build the main user interface - Professional fullscreen layout"""
        # Main container - minimal padding for fullscreen
        self.main_container = tk.Frame(self.root, bg=ModernColors.BG_DARK)
        self.main_container.pack(fill="both", expand=True, padx=20, pady=10)
        
        main_container = self.main_container  # Local reference
        
        # ========== HEADER - Large and prominent ==========
        header_frame = tk.Frame(main_container, bg=ModernColors.BG_DARK)
        header_frame.pack(fill="x", pady=(0, 10))
        
        # Logo and title - LEFT side
        title_frame = tk.Frame(header_frame, bg=ModernColors.BG_DARK)
        title_frame.pack(side="left", fill="y")
        
        # Load LARGER logo
        try:
            logo_path = resource_path("Idock Logo_1.png")
            img = Image.open(logo_path)
            logo_size = 150  # Fixed large size for visibility
            img = img.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
            self.header_logo = ImageTk.PhotoImage(img)
            logo_label = tk.Label(title_frame, image=self.header_logo, bg=ModernColors.BG_DARK)
            logo_label.pack(side="left", padx=(0, 25))
        except:
            # Fallback text logo
            tk.Label(
                title_frame,
                text="IDOCK",
                font=("Segoe UI Bold", 48),
                fg=ModernColors.PRIMARY,
                bg=ModernColors.BG_DARK
            ).pack(side="left", padx=(0, 25))
        
        title_text = tk.Frame(title_frame, bg=ModernColors.BG_DARK)
        title_text.pack(side="left", fill="y", pady=10)
        
        tk.Label(
            title_text,
            text="IDOCK AI",
            font=("Segoe UI Bold", 36),
            fg=ModernColors.TEXT_PRIMARY,
            bg=ModernColors.BG_DARK
        ).pack(anchor="w")
        
        tk.Label(
            title_text,
            text="Camera Trap Analysis System",
            font=("Segoe UI", 15),
            fg=ModernColors.TEXT_SECONDARY,
            bg=ModernColors.BG_DARK
        ).pack(anchor="w")
        
        # Device indicator - RIGHT side
        device_frame = tk.Frame(
            header_frame, 
            bg=ModernColors.SURFACE,
            padx=18,
            pady=10,
            highlightbackground=ModernColors.BORDER,
            highlightthickness=1
        )
        device_frame.pack(side="right", pady=10)
        
        tk.Label(
            device_frame,
            text="Device:",
            font=("Segoe UI", 11),
            fg=ModernColors.TEXT_MUTED,
            bg=ModernColors.SURFACE
        ).pack(side="left", padx=(0, 8))
        
        self.status_indicator = StatusIndicator(device_frame, size=16)
        self.status_indicator.pack(side="left", padx=(0, 8))
        
        tk.Label(
            device_frame,
            textvariable=self.device_var,
            font=("Segoe UI Semibold", 12),
            fg=ModernColors.TEXT_PRIMARY,
            bg=ModernColors.SURFACE
        ).pack(side="left")
        
        # User info and Logout button - RIGHT side (before device frame)
        user_frame = tk.Frame(
            header_frame, 
            bg=ModernColors.SURFACE,
            padx=15,
            pady=8,
            highlightbackground=ModernColors.BORDER,
            highlightthickness=1
        )
        user_frame.pack(side="right", pady=10, padx=(0, 15))
        
        # Show username
        username_display = getattr(self, 'current_username', 'User')
        tk.Label(
            user_frame,
            text=f"👤 {username_display}",
            font=("Segoe UI", 11),
            fg=ModernColors.TEXT_PRIMARY,
            bg=ModernColors.SURFACE
        ).pack(side="left", padx=(0, 12))
        
        # Logout button
        logout_btn = tk.Label(
            user_frame,
            text="🚪 Logout",
            font=("Segoe UI", 10),
            fg=ModernColors.ERROR,
            bg=ModernColors.SURFACE,
            cursor="hand2"
        )
        logout_btn.pack(side="left")
        logout_btn.bind("<Button-1>", lambda e: self._confirm_logout())
        logout_btn.bind("<Enter>", lambda e: logout_btn.config(fg="#FF0000"))
        logout_btn.bind("<Leave>", lambda e: logout_btn.config(fg=ModernColors.ERROR))
        
        # ========== MAIN CONTENT - UNIFIED DASHBOARD LAYOUT ==========
        
        # Center wrapper to keep everything centered and professional
        content_wrapper = tk.Frame(main_container, bg=ModernColors.BG_DARK)
        content_wrapper.pack(fill="both", expand=True)
        
        # Inner content frame with max width constraints for aesthetic centering
        self.content_frame = tk.Frame(content_wrapper, bg=ModernColors.BG_DARK)
        self.content_frame.place(relx=0.5, rely=0.5, anchor="center", relwidth=0.95, relheight=0.95)
        
        # === TOP DASHBOARD CARD (File + Class + Progress) ===
        dashboard_card = tk.Frame(self.content_frame, bg=ModernColors.SURFACE, padx=30, pady=20)
        dashboard_card.pack(fill="x", pady=(0, 15))
        self._style_panel(dashboard_card)
        
        # Uses Grid layout for 3 main sections
        dashboard_card.columnconfigure(0, weight=40) # File Selection
        dashboard_card.columnconfigure(1, weight=0) # Separator
        dashboard_card.columnconfigure(2, weight=30) # Class Selection
        dashboard_card.columnconfigure(3, weight=0) # Separator
        dashboard_card.columnconfigure(4, weight=30) # Progress
        
        # --- SECTION 1: FILE SELECTION ---
        file_section = tk.Frame(dashboard_card, bg=ModernColors.SURFACE)
        file_section.grid(row=0, column=0, sticky="nsew", padx=(0, 20))
        
        tk.Label(
            file_section,
            text="📂 FILE SELECTION",
            font=("Segoe UI Bold", 15),
            fg=ModernColors.PRIMARY,
            bg=ModernColors.SURFACE
        ).pack(anchor="w", pady=(0, 15))
        
        # Input Section
        self._create_folder_section_large(
            file_section,
            "Input Folder",
            "Select folder containing images/videos",
            self.input_var,
            self.browse_input,
            icon="📁"
        )
        
        # File counter
        counter_frame = tk.Frame(file_section, bg=ModernColors.SURFACE)
        counter_frame.pack(fill="x", pady=(8, 15))
        
        tk.Label(
            counter_frame,
            text="Files Found:",
            font=("Segoe UI", 11),
            fg=ModernColors.TEXT_MUTED,
            bg=ModernColors.SURFACE
        ).pack(side="left")
        
        tk.Label(
            counter_frame,
            textvariable=self.total_var,
            font=("Segoe UI Bold", 16),
            fg=ModernColors.PRIMARY,
            bg=ModernColors.SURFACE
        ).pack(side="left", padx=(8, 0))
        
        # Output Section
        self._create_folder_section_large(
            file_section,
            "Output Folder",
            "Select destination for processed files",
            self.output_var,
            self.browse_output,
            icon="💾"
        )
        
        # --- SEPARATOR 1 ---
        sep1 = tk.Frame(dashboard_card, bg=ModernColors.BORDER, width=2)
        sep1.grid(row=0, column=1, sticky="ns", padx=10)
        
        # --- SECTION 2: DETECTION CLASS ---
        class_section = tk.Frame(dashboard_card, bg=ModernColors.SURFACE)
        class_section.grid(row=0, column=2, sticky="nsew", padx=20)
        
        tk.Label(
            class_section,
            text="🎯 DETECTION CLASS",
            font=("Segoe UI Bold", 15),
            fg=ModernColors.PRIMARY,
            bg=ModernColors.SURFACE
        ).pack(anchor="w", pady=(0, 10))
        
        tk.Label(
            class_section,
            text="Select detection type:",
            font=("Segoe UI", 12),
            fg=ModernColors.TEXT_MUTED,
            bg=ModernColors.SURFACE
        ).pack(anchor="w", pady=(0, 10))
        
        # Main detection type selection container
        main_type_container = tk.Frame(class_section, bg=ModernColors.SURFACE)
        main_type_container.pack(fill="x", pady=(0, 5))
        
        # Human option (SelectionCard-style radio)
        self.human_card = SelectionCard(
            main_type_container,
            text="Human",
            value="human",
            variable=self.detection_mode,
            icon="👤",
            width=240,
            height=40
        )
        self.human_card.pack(pady=2)
        
        # Animal option (SelectionCard-style radio)
        self.animal_card = SelectionCard(
            main_type_container,
            text="Animal (All)",
            value="animal",
            variable=self.detection_mode,
            icon="🐾",
            width=240,
            height=40
        )
        self.animal_card.pack(pady=2)
        
        # Specific Animals section label
        specific_label = tk.Label(
            class_section,
            text="── OR Select Specific Animals ──",
            font=("Segoe UI", 10),
            fg=ModernColors.TEXT_MUTED,
            bg=ModernColors.SURFACE
        )
        specific_label.pack(anchor="w", pady=(8, 5))
        
        # Specific animals container (checkboxes)
        specific_container = tk.Frame(class_section, bg=ModernColors.SURFACE)
        specific_container.pack(fill="both", expand=True)
        
        class_icons = {"leopard": "🐆", "tiger": "🐅", "hyena": "🦴", "elephant": "🐘"}
        
        # Use CheckboxCard for specific animal multi-selection
        self.class_cards = []
        self.specific_animal_cards = []
        for cls in self.specific_animal_classes:
            card = CheckboxCard(
                specific_container,
                text=cls.capitalize(),
                value=cls,
                selected_set=self.selected_specific_animals,
                icon=class_icons.get(cls, '•'),
                width=240,
                height=38,
                on_change=self._on_specific_animal_change
            )
            card.pack(pady=2)
            self.specific_animal_cards.append(card)
            self.class_cards.append(card)  # Keep reference for locking
        
        # Bind detection mode change
        self.detection_mode.trace_add("write", self._on_detection_mode_change)
        
        # --- SEPARATOR 2 ---
        sep2 = tk.Frame(dashboard_card, bg=ModernColors.BORDER, width=2)
        sep2.grid(row=0, column=3, sticky="ns", padx=10)
        
        # --- SECTION 3: PROGRESS ---
        progress_section = tk.Frame(dashboard_card, bg=ModernColors.SURFACE)
        progress_section.grid(row=0, column=4, sticky="nsew", padx=(20, 0))
        
        tk.Label(
            progress_section,
            text="📈 PROGRESS",
            font=("Segoe UI Bold", 15),
            fg=ModernColors.PRIMARY,
            bg=ModernColors.SURFACE
        ).pack(anchor="w", pady=(0, 15))
        
        # Center progress content vertically
        progress_content = tk.Frame(progress_section, bg=ModernColors.SURFACE)
        progress_content.pack(expand=True, fill="both")
        
        # Circular progress centered
        p_container = tk.Frame(progress_content, bg=ModernColors.SURFACE)
        p_container.pack(pady=10)
        self.circular_progress = CircularProgress(p_container, size=140, thickness=12)
        self.circular_progress.pack()
        
        # Files processed counter
        tk.Label(
            progress_content,
            text="Files Processed",
            font=("Segoe UI", 11),
            fg=ModernColors.TEXT_MUTED,
            bg=ModernColors.SURFACE
        ).pack(pady=(15, 5))
        
        tk.Label(
            progress_content,
            textvariable=self.files_processed_var,
            font=("Segoe UI Bold", 22),
            fg=ModernColors.TEXT_PRIMARY,
            bg=ModernColors.SURFACE
        ).pack()
        
        # Status display
        status_frame = tk.Frame(progress_content, bg=ModernColors.SURFACE)
        status_frame.pack(pady=(15, 10))
        
        tk.Label(
            status_frame,
            textvariable=self.status_var,
            font=("Segoe UI Bold", 13),
            fg=ModernColors.PRIMARY,
            bg=ModernColors.SURFACE
        ).pack()
        
        self.visualizer = Visualizer(progress_content, width=250, height=35, bars=15)
        self.visualizer.pack(fill="x", pady=(10, 0))

        # --- ACTION BUTTON (Centered) ---
        button_container = tk.Frame(self.content_frame, bg=ModernColors.BG_DARK)
        button_container.pack(pady=(0, 15))
        
        self.action_btn = GlassButton(
            button_container,
            "▶  Start Detection",
            self.toggle_detection,
            width=260,
            height=55, # Larger button
            bg_color=ModernColors.SUCCESS,
            hover_color=ModernColors.ACCENT
        )
        self.action_btn.pack()
        
        # ========== BOTTOM SECTION - QUICK ACTIONS ==========
        # Uses Grid for better alignment and prevents "too far right" issue
        self.quick_actions_frame_container = tk.Frame(self.content_frame, bg=ModernColors.SURFACE, padx=30, pady=15)
        self._style_panel(self.quick_actions_frame_container)
        self.quick_actions_frame_container.pack(fill="both", expand=True, pady=(0, 0)) # Minimized padding to fix cut-off
        
        # Quick Actions (Full width now)
        self.quick_actions_frame = tk.Frame(self.quick_actions_frame_container, bg=ModernColors.SURFACE)
        self.quick_actions_frame.pack(fill="both", expand=True)
        
        tk.Label(
            self.quick_actions_frame,
            text="⚡ QUICK ACTIONS",
            font=("Segoe UI Bold", 12),
            fg=ModernColors.PRIMARY,
            bg=ModernColors.SURFACE
        ).pack(anchor="w", pady=(0, 15))
        
        actions_container = tk.Frame(self.quick_actions_frame, bg=ModernColors.SURFACE)
        actions_container.pack(fill="x", anchor="n")
        
        self.open_folder_btn = GlassButton(
            actions_container,
            "📂 Open Folder",
            self.open_output_folder,
            width=220,
            height=45,
            bg_color=ModernColors.PRIMARY_DARK,
            hover_color=ModernColors.PRIMARY
        )
        self.open_folder_btn.pack(pady=(0, 12))
        
        self.open_excel_btn = GlassButton(
            actions_container,
            "📊 Open Report",
            self.open_excel_file,
            width=220,
            height=45,
            bg_color=ModernColors.ACCENT,
            hover_color=ModernColors.SUCCESS
        )
        self.open_excel_btn.pack()
        
        # ========== FOOTER ==========
        self.footer_frame = tk.Frame(main_container, bg=ModernColors.BG_DARK)
        self.footer_frame.pack(fill="x", pady=(10, 5), side="bottom")
        
        tk.Label(
            self.footer_frame,
            text="© 2026 IDOCK Technologies Pvt Ltd. All rights reserved.",
            font=("Segoe UI", 9),
            fg=ModernColors.TEXT_MUTED,
            bg=ModernColors.BG_DARK
        ).pack(side="left")
        
        tk.Label(
            self.footer_frame,
            text="v2.0",
            font=("Segoe UI", 9),
            fg=ModernColors.TEXT_MUTED,
            bg=ModernColors.BG_DARK
        ).pack(side="right")
    
    def _style_panel(self, panel):
        """Apply styling to panel (simulated rounded corners)"""
        panel.configure(
            highlightbackground=ModernColors.BORDER,
            highlightthickness=2
        )
    
    def _create_folder_section_large(self, parent, title, subtitle, var, command, icon="📁"):
        """Create a folder input section for better visibility"""
        section = tk.Frame(parent, bg=ModernColors.SURFACE)
        section.pack(fill="x", pady=(0, 12))
        
        tk.Label(
            section,
            text=f"{icon}  {title}",
            font=("Segoe UI Semibold", 14),
            fg=ModernColors.TEXT_PRIMARY,
            bg=ModernColors.SURFACE
        ).pack(anchor="w")
        
        tk.Label(
            section,
            text=subtitle,
            font=("Segoe UI", 11),
            fg=ModernColors.TEXT_MUTED,
            bg=ModernColors.SURFACE
        ).pack(anchor="w", pady=(2, 8))
        
        entry_row = tk.Frame(section, bg=ModernColors.SURFACE)
        entry_row.pack(fill="x")
        
        entry = ModernEntry(entry_row, var, width=420, height=44)
        entry.pack(side="left", padx=(0, 10))
        
        browse_btn = GlassButton(
            entry_row,
            "Browse",
            command,
            width=110,
            height=44,
            bg_color=ModernColors.PRIMARY_DARK
        )
        browse_btn.pack(side="left")
    
    # ========================
    # BROWSE FUNCTIONS
    # ========================
    def browse_input(self):
        path = filedialog.askdirectory()
        if path:
            self.input_var.set(path)
            files = [
                f for f in Path(path).iterdir()
                if f.is_file() and (is_image(f) or is_video(f))
            ]
            self.total_var.set(str(len(files)))
    
    def browse_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_var.set(path)
            # Enable open folder button when output path is set
            self.open_folder_btn.set_enabled(True)
    
    # ========================
    # UI UPDATE CALLBACKS
    # ========================
    def update_progress(self, done, total):
        if self.stop_flag.is_set():
            return False  # Signal to stop
        
        percent = (done / total) * 100
        self.root.after(0, lambda: self._update_ui_progress(done, total, percent))
        return True  # Continue processing
    
    def _update_ui_progress(self, done, total, percent):
        self.progress_var.set(percent)
        self.circular_progress.set_progress(percent)
        self.files_processed_var.set(f"{done} / {total}")
    
    def update_device(self, device_name):
        self.root.after(0, lambda: self.device_var.set(device_name))
    
    def update_status(self, status):
        self.root.after(0, lambda: self.status_var.set(status))
    
    # ========================
    # DETECTION CLASS SELECTION
    # ========================
    def _on_detection_mode_change(self, *args):
        """Called when Human or Animal (All) is selected"""
        mode = self.detection_mode.get()
        if mode in ["human", "animal"]:
            # Clear specific animal selections when human/animal mode is chosen
            self.selected_specific_animals.clear()
            for card in self.specific_animal_cards:
                card.is_selected.set(False)
                card._check_state()
    
    def _on_specific_animal_change(self):
        """Called when a specific animal checkbox is toggled"""
        if self.selected_specific_animals:
            # Clear the human/animal radio selection when specific animals are chosen
            self.detection_mode.set("")
            # Update visual state of radio cards
            self.human_card._check_state()
            self.animal_card._check_state()
    
    # ========================
    # DETECTION CONTROL
    # ========================
    def toggle_detection(self):
        """Toggle between start and stop detection"""
        if self.is_running:
            self.stop_detection()
        else:
            self.start_detection()
    
    def start_detection(self):
        """Start the detection process"""
        if not self.input_var.get() or not self.output_var.get():
            messagebox.showerror("Error", "Please select both input and output folders")
            return
        
        # Check if either detection mode (human/animal) or specific animals are selected
        mode = self.detection_mode.get()
        has_mode_selection = mode in ["human", "animal"]
        has_specific_animals = len(self.selected_specific_animals) > 0
        
        if not has_mode_selection and not has_specific_animals:
            messagebox.showerror("Error", "Please select a detection type (Human/Animal) or specific animals before starting")
            return
        
        # Update selected_classes for backwards compatibility
        self.selected_classes = self.selected_specific_animals.copy()
        
        # Reset state
        self.stop_flag.clear()
        self.is_running = True
        self.progress_var.set(0)
        self.circular_progress.set_progress(0)
        self.device_var.set("Detecting...")
        self.status_var.set("Processing...")
        self.files_processed_var.set("0 / 0")
        
        # Update button to Stop mode
        self.action_btn.set_text("◼  Stop Detection")
        self.action_btn.set_color(ModernColors.ERROR, ModernColors.ERROR)
        
        # Lock detection class selection
        for card in self.class_cards:
            card.set_locked(True)
        # Also lock the human/animal radio cards
        self.human_card.rb.configure(state="disabled")
        self.animal_card.rb.configure(state="disabled")
        
        self.status_indicator.set_status("processing")
        self.visualizer.start()
        
        # Start worker thread
        worker = threading.Thread(target=self._run_worker, daemon=True)
        worker.start()
    
    def stop_detection(self):
        """Stop the detection process"""
        if self.is_running:
            self.stop_flag.set()
            self.status_var.set("Stopping...")
            self.action_btn.set_enabled(False)
            self.status_indicator.set_status("idle")
    
    def _run_worker(self):
        """Background worker for detection"""
        try:
            # Determine detection mode and target classes
            mode = self.detection_mode.get()
            detection_mode = None
            target_classes = None
            
            if mode in ["human", "animal"]:
                # Use weight1.pt model
                detection_mode = mode
            else:
                # Use best.pt model with specific animal classes
                target_classes = list(self.selected_specific_animals)
            
            excel, logs = run_detection(
                self.input_var.get(),
                self.output_var.get(),
                self.update_progress,
                self.update_device,
                self.stop_flag,
                target_classes,
                detection_mode
            )
            
            if self.stop_flag.is_set():
                self.root.after(0, lambda: self._on_stopped())
            elif excel:
                self.root.after(0, lambda: self._on_complete(excel))
            else:
                self.root.after(0, lambda: self._on_no_detections())
        
        except Exception as e:
            err_msg = str(e)
            self.root.after(0, lambda: self._on_error(err_msg))
        
        finally:
            self.is_running = False
            self.root.after(0, self._reset_ui)
    
    def _on_complete(self, excel):
        self.status_indicator.set_status("success")
        self.status_var.set("Completed!")
        
        # Store excel path
        self.last_excel_path = excel
        
        messagebox.showinfo(
            "Detection Complete",
            f"All detections have been saved!\n\nExcel report:\n{excel}"
        )
    
    def _on_no_detections(self):
        self.status_indicator.set_status("idle")
        self.status_var.set("No Detections")
        
        messagebox.showinfo(
            "Complete",
            "Processing complete. No objects were detected in any file."
        )
    
    def _on_stopped(self):
        self.status_indicator.set_status("idle")
        self.status_var.set("Stopped")
        messagebox.showinfo("Stopped", "Detection process was stopped by user.")
    
    def _on_error(self, msg):
        self.status_indicator.set_status("error")
        self.status_var.set("Error")
        messagebox.showerror("Error", msg)
    
    def _reset_ui(self):
        """Reset UI to initial state after detection completes"""
        self.action_btn.set_text("▶  Start Detection")
        self.action_btn.set_color(ModernColors.SUCCESS, ModernColors.ACCENT)
        self.action_btn.set_enabled(True)
        self.visualizer.stop()
        
        # Unlock detection class selection
        for card in self.class_cards:
            card.set_locked(False)
        # Unlock human/animal radio cards
        self.human_card.rb.configure(state="normal")
        self.animal_card.rb.configure(state="normal")
    
    # ========================
    # QUICK ACTION FUNCTIONS
    # ========================
    def open_output_folder(self):
        """Open the output folder in file explorer"""
        output_path = self.output_var.get()
        if output_path and os.path.exists(output_path):
            if sys.platform == 'win32':
                os.startfile(output_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', output_path])
            else:  # Linux
                subprocess.run(['xdg-open', output_path])
        else:
            messagebox.showwarning("Warning", "Output folder not found or not set.")
    
    def open_excel_file(self):
        """Open the generated Excel file"""
        if self.last_excel_path and os.path.exists(self.last_excel_path):
            if sys.platform == 'win32':
                os.startfile(self.last_excel_path)
            elif sys.platform == 'darwin':  # macOS
                subprocess.run(['open', self.last_excel_path])
            else:  # Linux
                subprocess.run(['xdg-open', self.last_excel_path])
        else:
            messagebox.showwarning("Warning", "Excel file not found. Please run detection first.")


def main():
    root = tk.Tk()
    app = YOLOApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
