#!/usr/bin/env python3
"""
Shakshuka Server Manager GUI
Simple GUI for starting/stopping the Shakshuka server
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import subprocess
import psutil
import webbrowser
import threading
import time
import os
from pathlib import Path

class ShakshukaServerManager:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Shakshuka Server Manager")
        self.root.geometry("500x400")
        self.root.resizable(False, False)
        
        # Try to find Shakshuka.exe
        self.shakshuka_path = self.find_shakshuka_exe()
        
        self.setup_ui()
        self.update_status()
        
    def find_shakshuka_exe(self):
        """Find Shakshuka.exe in common locations"""
        possible_paths = [
            Path.home() / "Desktop" / "Shakshuka.exe",
            Path("C:/Program Files/Shakshuka/Shakshuka.exe"),
            Path("Shakshuka.exe"),
            Path.cwd() / "Shakshuka.exe"
        ]
        
        for path in possible_paths:
            if path.exists():
                return str(path)
        
        return None
    
    def setup_ui(self):
        """Setup the user interface"""
        # Main frame
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Title
        title_label = ttk.Label(main_frame, text="Shakshuka Server Manager", 
                               font=("Arial", 16, "bold"))
        title_label.grid(row=0, column=0, columnspan=2, pady=(0, 20))
        
        # Status frame
        status_frame = ttk.LabelFrame(main_frame, text="Server Status", padding="10")
        status_frame.grid(row=1, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        
        self.status_label = ttk.Label(status_frame, text="Checking...", 
                                    font=("Arial", 12))
        self.status_label.grid(row=0, column=0, sticky=tk.W)
        
        self.pid_label = ttk.Label(status_frame, text="", font=("Arial", 10))
        self.pid_label.grid(row=1, column=0, sticky=tk.W)
        
        # Control buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=2, column=0, columnspan=2, pady=(0, 10))
        
        self.start_button = ttk.Button(button_frame, text="Start Server", 
                                      command=self.start_server, width=15)
        self.start_button.grid(row=0, column=0, padx=(0, 10))
        
        self.stop_button = ttk.Button(button_frame, text="Stop Server", 
                                     command=self.stop_server, width=15)
        self.stop_button.grid(row=0, column=1, padx=(0, 10))
        
        self.restart_button = ttk.Button(button_frame, text="Restart Server", 
                                        command=self.restart_server, width=15)
        self.restart_button.grid(row=0, column=2, padx=(0, 10))
        
        self.open_browser_button = ttk.Button(button_frame, text="Open Browser", 
                                             command=self.open_browser, width=15)
        self.open_browser_button.grid(row=0, column=3)
        
        # Log frame
        log_frame = ttk.LabelFrame(main_frame, text="Server Log", padding="10")
        log_frame.grid(row=3, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, width=60)
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        
        # Configure grid weights
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(3, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        
        # Auto-refresh status every 2 seconds
        self.root.after(2000, self.auto_refresh)
        
    def is_server_running(self):
        """Check if Shakshuka server is running"""
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                if proc.info['name'] == 'Shakshuka.exe':
                    return True, proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return False, None
    
    def update_status(self):
        """Update the status display"""
        is_running, pid = self.is_server_running()
        
        if is_running:
            self.status_label.config(text="🟢 Server is running", foreground="green")
            self.pid_label.config(text=f"Process ID: {pid}")
            self.start_button.config(state="disabled")
            self.stop_button.config(state="normal")
            self.restart_button.config(state="normal")
            self.open_browser_button.config(state="normal")
        else:
            self.status_label.config(text="🔴 Server is stopped", foreground="red")
            self.pid_label.config(text="")
            self.start_button.config(state="normal")
            self.stop_button.config(state="disabled")
            self.restart_button.config(state="disabled")
            self.open_browser_button.config(state="disabled")
    
    def log_message(self, message):
        """Add a message to the log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update()
    
    def start_server(self):
        """Start the Shakshuka server"""
        if not self.shakshuka_path:
            messagebox.showerror("Error", "Could not find Shakshuka.exe!\n\n"
                                "Please ensure Shakshuka is installed.")
            return
        
        self.log_message("Starting Shakshuka server...")
        
        try:
            # Start the server in a new process
            subprocess.Popen([self.shakshuka_path], 
                           creationflags=subprocess.CREATE_NEW_CONSOLE)
            
            # Wait a moment and check if it started
            time.sleep(2)
            self.update_status()
            
            if self.is_server_running()[0]:
                self.log_message("Server started successfully!")
                self.log_message("Opening browser...")
                threading.Timer(1.0, self.open_browser).start()
            else:
                self.log_message("Failed to start server")
                messagebox.showerror("Error", "Failed to start server.\n\n"
                                    "Check the console for error messages.")
                
        except Exception as e:
            self.log_message(f"Error starting server: {e}")
            messagebox.showerror("Error", f"Failed to start server:\n{e}")
    
    def stop_server(self):
        """Stop the Shakshuka server"""
        self.log_message("Stopping Shakshuka server...")
        
        try:
            # Find and kill Shakshuka processes
            killed_count = 0
            for proc in psutil.process_iter(['pid', 'name']):
                try:
                    if proc.info['name'] == 'Shakshuka.exe':
                        proc.kill()
                        killed_count += 1
                        self.log_message(f"Killed process {proc.info['pid']}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            if killed_count > 0:
                self.log_message(f"Stopped {killed_count} server process(es)")
            else:
                self.log_message("No server processes found")
            
            self.update_status()
            
        except Exception as e:
            self.log_message(f"Error stopping server: {e}")
            messagebox.showerror("Error", f"Failed to stop server:\n{e}")
    
    def restart_server(self):
        """Restart the Shakshuka server"""
        self.log_message("Restarting server...")
        self.stop_server()
        time.sleep(1)
        self.start_server()
    
    def open_browser(self):
        """Open the Shakshuka web interface in browser"""
        try:
            webbrowser.open("http://127.0.0.1:8989")
            self.log_message("Opened browser to http://127.0.0.1:8989")
        except Exception as e:
            self.log_message(f"Error opening browser: {e}")
            messagebox.showerror("Error", f"Failed to open browser:\n{e}")
    
    def auto_refresh(self):
        """Auto-refresh status every 2 seconds"""
        self.update_status()
        self.root.after(2000, self.auto_refresh)
    
    def run(self):
        """Start the GUI"""
        self.root.mainloop()

def main():
    try:
        app = ShakshukaServerManager()
        app.run()
    except Exception as e:
        print(f"Error starting server manager: {e}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    main()

