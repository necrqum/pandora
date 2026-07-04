import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import secrets
import json
import traceback
from pathlib import Path

# Ensure pandora modules can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from pandora.pandora.backend.security import VaultSecurity, WeakPasswordError
from pandora.pandora.backend.database import DatabaseManager, File as DBFile, Category as DBCategory, Tag as DBTag
from pandora.pandora.backend.vault import VaultManager, CHUNK_SIZE
from pandora.pandora.backend.thumbnails import generate_thumbnail_from_file, get_file_creation_date

def get_vault_paths():
    config_path = os.path.expanduser("~/.pandora_config")
    config_dir = os.environ.get("PANDORA_CONFIG_DIR")
    blob_dir = os.environ.get("PANDORA_BLOB_DIR")
    
    if not config_dir and os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
                config_dir = data.get("config_dir")
                blob_dir = data.get("blob_dir")
        except:
            try:
                with open(config_path, "r") as f:
                    config_dir = f.read().strip()
            except:
                pass
                
    if not config_dir:
        config_dir = os.path.expanduser("~/.pandora")
    if not blob_dir:
        blob_dir = os.path.join(config_dir, "data")
        
    return {
        "salt": os.path.join(config_dir, ".vault_salt"),
        "db": os.path.join(config_dir, "pandora.db"),
        "files": os.path.join(blob_dir, "files")
    }

class PandoraImporter:
    def __init__(self, root):
        self.root = root
        self.root.title("Pandora Mass Importer (Offline)")
        self.root.geometry("600x500")
        
        self.security = None
        self.db = None
        self.vault = None
        self.paths = get_vault_paths()
        self.files_to_import = []
        
        self.build_login_ui()

    def build_login_ui(self):
        for widget in self.root.winfo_children():
            widget.destroy()
            
        frame = ttk.Frame(self.root, padding="20")
        frame.pack(expand=True, fill='both')
        
        ttk.Label(frame, text="Pandora Mass Importer", font=("Helvetica", 16, "bold")).pack(pady=20)
        
        ttk.Label(frame, text=f"Config DB: {self.paths['db']}").pack(pady=5)
        ttk.Label(frame, text=f"Mass Storage: {self.paths['files']}").pack(pady=5)
        
        if not os.path.exists(self.paths['salt']):
            ttk.Label(frame, text="Vault not initialized! Please run Pandora web app first.", foreground="red").pack(pady=10)
            return

        ttk.Label(frame, text="Enter Master Password:").pack(pady=10)
        self.pw_entry = ttk.Entry(frame, show="*")
        self.pw_entry.pack(pady=5, ipadx=50)
        self.pw_entry.bind('<Return>', lambda e: self.login())
        
        ttk.Button(frame, text="Unlock Vault", command=self.login).pack(pady=20)
        
    def login(self):
        password = self.pw_entry.get()
        if not password:
            return
            
        try:
            with open(self.paths["salt"], 'rb') as f:
                salt = f.read()
                
            security = VaultSecurity(password, salt)
            db = DatabaseManager(self.paths["db"], password)
            db.verify_password()
            
            self.security = security
            self.db = db
            self.vault = VaultManager(self.paths["files"], security)
            
            self.build_main_ui()
        except Exception as e:
            messagebox.showerror("Login Failed", f"Invalid password or corrupt database.\n{e}")

    def build_main_ui(self):
        for widget in self.root.winfo_children():
            widget.destroy()
            
        self.main_frame = ttk.Frame(self.root, padding="10")
        self.main_frame.pack(expand=True, fill='both')
        
        top_frame = ttk.Frame(self.main_frame)
        top_frame.pack(fill='x', pady=5)
        
        ttk.Button(top_frame, text="Add Files", command=self.select_files).pack(side='left', padx=5)
        ttk.Button(top_frame, text="Add Folder (recursive)", command=self.select_folder).pack(side='left', padx=5)
        ttk.Button(top_frame, text="Clear List", command=self.clear_list).pack(side='left', padx=5)
        
        self.listbox = tk.Listbox(self.main_frame)
        self.listbox.pack(fill='both', expand=True, pady=10)
        
        options_frame = ttk.LabelFrame(self.main_frame, text="Default Import Settings", padding="10")
        options_frame.pack(fill='x', pady=10)
        
        ttk.Label(options_frame, text="Category (leave empty for auto):").grid(row=0, column=0, padx=5, pady=5, sticky='w')
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(options_frame, textvariable=self.category_var)
        self.category_combo.grid(row=0, column=1, padx=5, pady=5, sticky='ew')
        
        ttk.Label(options_frame, text="Tags (comma separated):").grid(row=1, column=0, padx=5, pady=5, sticky='w')
        self.tags_entry = ttk.Entry(options_frame)
        self.tags_entry.grid(row=1, column=1, padx=5, pady=5, sticky='ew')
        
        options_frame.columnconfigure(1, weight=1)
        
        self.start_btn = ttk.Button(self.main_frame, text="START MASS IMPORT", command=self.start_import)
        self.start_btn.pack(pady=10, fill='x')
        
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self.main_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill='x', pady=5)
        
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.main_frame, textvariable=self.status_var).pack()
        
        self.load_categories()

    def load_categories(self):
        try:
            with self.db.session_scope() as session:
                cats = session.query(DBCategory).all()
                self.category_combo['values'] = [c.name for c in cats]
        except Exception as e:
            print("Failed to load categories:", e)

    def select_files(self):
        files = filedialog.askopenfilenames()
        for f in files:
            if f not in self.files_to_import:
                self.files_to_import.append(f)
                self.listbox.insert(tk.END, f)
                
    def select_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            for root, _, files in os.walk(folder):
                for file in files:
                    full_path = os.path.join(root, file)
                    if full_path not in self.files_to_import:
                        self.files_to_import.append(full_path)
                        self.listbox.insert(tk.END, full_path)
                        
    def clear_list(self):
        self.files_to_import.clear()
        self.listbox.delete(0, tk.END)

    def start_import(self):
        if not self.files_to_import:
            return
            
        self.start_btn.config(state='disabled')
        self.category_combo.config(state='disabled')
        self.tags_entry.config(state='disabled')
        
        cat_name = self.category_var.get().strip()
        tags_raw = self.tags_entry.get().strip()
        tags = [t.strip() for t in tags_raw.split(',')] if tags_raw else []
        
        threading.Thread(target=self._import_thread, args=(cat_name, tags), daemon=True).start()

    def _import_thread(self, custom_cat_name, tags):
        total = len(self.files_to_import)
        success = 0
        failed = 0
        
        for i, filepath in enumerate(self.files_to_import):
            filename = os.path.basename(filepath)
            self.status_var.set(f"[{i+1}/{total}] Processing: {filename}...")
            
            try:
                ext = filename.split('.')[-1] if '.' in filename else 'tmp'
                ext_lower = ext.lower()
                
                # Thumbnail extraction
                thumbnail, duration = generate_thumbnail_from_file(filepath, filename)
                creation_date = get_file_creation_date(filepath)
                
                # Encryption stream
                def file_iterator():
                    with open(filepath, "rb") as f:
                        while True:
                            chunk = f.read(CHUNK_SIZE)
                            if not chunk: break
                            yield chunk
                            
                file_id, total_size = self.vault.store_file(file_iterator())
                
                # Database Insert
                final_cat_name = custom_cat_name
                if not final_cat_name:
                    if ext_lower in ['mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv']:
                        final_cat_name = "Video"
                    elif ext_lower in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                        final_cat_name = "Image"
                    elif ext_lower in ['pdf', 'txt', 'doc', 'docx']:
                        final_cat_name = "Document"
                    else:
                        final_cat_name = "Other"
                        
                with self.db.session_scope() as session:
                    category = session.query(DBCategory).filter(DBCategory.name == final_cat_name).first()
                    if not category:
                        category = DBCategory(name=final_cat_name)
                        session.add(category)
                        session.flush()
                    final_category_id = category.id
                    
                    tag_objs = []
                    for tname in tags:
                        if not tname: continue
                        tag = session.query(DBTag).filter(DBTag.name == tname).first()
                        if not tag:
                            tag = DBTag(name=tname)
                            session.add(tag)
                            session.flush()
                        tag_objs.append(tag)
                        
                    db_file = DBFile(
                        id=file_id, 
                        filename=filename, 
                        size=total_size, 
                        duration=duration,
                        thumbnail_data=thumbnail,
                        category_id=final_category_id,
                        metadata_created_at=creation_date
                    )
                    
                    if tag_objs:
                        db_file.tags = tag_objs
                    session.add(db_file)
                
                success += 1
                
                # Optional: update UI listbox to show completion
                self.root.after(0, lambda idx=i: self.listbox.itemconfig(idx, {'bg': '#d4edda'}))
                
            except Exception as e:
                failed += 1
                traceback.print_exc()
                self.root.after(0, lambda idx=i: self.listbox.itemconfig(idx, {'bg': '#f8d7da'}))
                
            self.progress_var.set((i+1) / total * 100)
            
        self.status_var.set(f"Completed! {success} added, {failed} failed.")
        
        self.root.after(0, lambda: self.start_btn.config(state='normal'))
        self.root.after(0, lambda: self.category_combo.config(state='normal'))
        self.root.after(0, lambda: self.tags_entry.config(state='normal'))

if __name__ == "__main__":
    root = tk.Tk()
    
    # Simple styling
    style = ttk.Style(root)
    style.theme_use('clam')
    
    app = PandoraImporter(root)
    root.mainloop()
