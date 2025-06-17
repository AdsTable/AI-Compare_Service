# gui.py
import tkinter as tk
from tkinter import ttk
import asyncio
from main import crawl_data
from config import DATA_MODEL

class CrawlerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("AI Web Scraper")
        
        # Configuration frame
        config_frame = ttk.LabelFrame(root, text="Configuration")
        config_frame.pack(padx=10, pady=10, fill="x")
        
        ttk.Label(config_frame, text="Data Model:").grid(row=0, column=0)
        self.model_var = tk.StringVar(value=DATA_MODEL)
        model_combo = ttk.Combobox(config_frame, textvariable=self.model_var, 
                                  values=["mobile_service_provider", "business"])
        model_combo.grid(row=0, column=1)
        
        # Control buttons
        btn_frame = ttk.Frame(root)
        btn_frame.pack(pady=10)
        
        ttk.Button(btn_frame, text="Start Crawling", command=self.start_crawl).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Download Data", command=self.download).pack(side=tk.LEFT, padx=5)
    
    def start_crawl(self):
        # Update configuration
        DATA_MODEL = self.model_var.get()
        
        # Run crawling in background
        asyncio.create_task(crawl_data())
    
    def download(self):
        # Implement download functionality
        pass

if __name__ == "__main__":
    root = tk.Tk()
    app = CrawlerApp(root)
    root.mainloop()