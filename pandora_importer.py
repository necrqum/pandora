import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import secrets
import json
import traceback
from pathlib import Path

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    DND_AVAILABLE = True
except ImportError:
    DND_AVAILABLE = False

# Ensure pandora modules can be imported
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from pandora.backend.security import VaultSecurity, WeakPasswordError
from pandora.backend.database import DatabaseManager, File as DBFile, Category as DBCategory, Tag as DBTag
from pandora.backend.vault import VaultManager, CHUNK_SIZE
from pandora.backend.thumbnails import generate_thumbnail_from_file, get_file_creation_date

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
        self.root.geometry("800x650")
        
        self.security = None
        self.db = None
        self.vault = None
        self.paths = get_vault_paths()
        self.files_to_import = sys.argv[1:] if len(sys.argv) > 1 else []
        
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
        
        # Files List Section
        files_frame = ttk.LabelFrame(self.main_frame, text="Files to Import (Drag & Drop supported)" if DND_AVAILABLE else "Files to Import", padding="5")
        files_frame.pack(fill='both', expand=True, pady=5)
        
        top_frame = ttk.Frame(files_frame)
        top_frame.pack(fill='x', pady=5)
        
        ttk.Button(top_frame, text="Add Files", command=self.select_files).pack(side='left', padx=5)
        ttk.Button(top_frame, text="Add Folder (recursive)", command=self.select_folder).pack(side='left', padx=5)
        ttk.Button(top_frame, text="Remove Selected (Del)", command=self.remove_selected_files).pack(side='left', padx=5)
        ttk.Button(top_frame, text="Clear All", command=self.clear_list).pack(side='left', padx=5)
        
        list_scroll = ttk.Scrollbar(files_frame)
        list_scroll.pack(side='right', fill='y')
        self.listbox = tk.Listbox(files_frame, selectmode=tk.EXTENDED, yscrollcommand=list_scroll.set)
        self.listbox.pack(fill='both', expand=True)
        list_scroll.config(command=self.listbox.yview)
        
        # Shortcuts for file list
        self.listbox.bind("<Control-a>", self.select_all_files)
        self.listbox.bind("<Delete>", self.remove_selected_files)
        self.listbox.bind("<BackSpace>", self.remove_selected_files)
        
        if DND_AVAILABLE:
            self.listbox.drop_target_register(DND_FILES)
            self.listbox.dnd_bind('<<Drop>>', self.on_drop_files)
            
        # Add any files passed from CLI (like Nemo actions)
        if self.files_to_import:
            for f in self.files_to_import:
                self.listbox.insert(tk.END, f)
        
        # Settings Section
        options_frame = ttk.LabelFrame(self.main_frame, text="Import Settings", padding="10")
        options_frame.pack(fill='x', pady=10)
        
        # Category
        cat_frame = ttk.Frame(options_frame)
        cat_frame.pack(fill='x', pady=5)
        ttk.Label(cat_frame, text="Category (Select or type new):").pack(side='left', padx=5)
        self.category_var = tk.StringVar()
        self.category_combo = ttk.Combobox(cat_frame, textvariable=self.category_var)
        self.category_combo.pack(side='left', fill='x', expand=True, padx=5)
        
        # Tags
        tags_frame = ttk.Frame(options_frame)
        tags_frame.pack(fill='both', expand=True, pady=5)
        ttk.Label(tags_frame, text="Select Tags:").pack(side='left', anchor='n', padx=5)
        
        tags_list_frame = ttk.Frame(tags_frame)
        tags_list_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        tag_scroll = ttk.Scrollbar(tags_list_frame)
        tag_scroll.pack(side='right', fill='y')
        self.tags_listbox = tk.Listbox(tags_list_frame, selectmode=tk.MULTIPLE, height=4, yscrollcommand=tag_scroll.set)
        self.tags_listbox.pack(side='left', fill='both', expand=True)
        tag_scroll.config(command=self.tags_listbox.yview)
        
        new_tag_frame = ttk.Frame(tags_frame)
        new_tag_frame.pack(side='left', anchor='n', padx=5)
        ttk.Label(new_tag_frame, text="Add New Tag:").pack(anchor='w')
        self.new_tag_var = tk.StringVar()
        new_tag_entry = ttk.Entry(new_tag_frame, textvariable=self.new_tag_var)
        new_tag_entry.pack(fill='x')
        new_tag_entry.bind("<Return>", lambda e: self.add_new_tag())
        ttk.Button(new_tag_frame, text="Add", command=self.add_new_tag).pack(fill='x', pady=2)
        
        # Start & Progress
        self.start_btn = ttk.Button(self.main_frame, text="START MASS IMPORT", command=self.start_import)
        self.start_btn.pack(pady=10, fill='x')
        
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self.main_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill='x', pady=5)
        
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(self.main_frame, textvariable=self.status_var).pack()
        
        self.load_categories()
        self.load_tags()

    def load_categories(self):
        try:
            with self.db.session_scope() as session:
                cats = session.query(DBCategory).all()
                self.category_combo['values'] = [c.name for c in cats]
        except Exception as e:
            print("Failed to load categories:", e)
            
    def load_tags(self):
        try:
            with self.db.session_scope() as session:
                tags = session.query(DBTag).all()
                self.tags_listbox.delete(0, tk.END)
                for t in tags:
                    self.tags_listbox.insert(tk.END, t.name)
        except Exception as e:
            print("Failed to load tags:", e)
            
    def add_new_tag(self):
        new_tag = self.new_tag_var.get().strip()
        if new_tag:
            # Check if it already exists in listbox
            existing = self.tags_listbox.get(0, tk.END)
            if new_tag not in existing:
                self.tags_listbox.insert(tk.END, new_tag)
            # Select it
            idx = self.tags_listbox.get(0, tk.END).index(new_tag)
            self.tags_listbox.selection_set(idx)
            self.new_tag_var.set("")

    def select_all_files(self, event=None):
        total = self.listbox.size()
        if total == 0:
            return "break"
            
        selected = self.listbox.curselection()
        if len(selected) == total:
            self.listbox.selection_clear(0, tk.END)
        else:
            self.listbox.selection_set(0, tk.END)
        return "break"
        
    def remove_selected_files(self, event=None):
        selected = list(self.listbox.curselection())
        selected.reverse() # Delete from bottom to top to preserve indices
        for idx in selected:
            self.listbox.delete(idx)
            del self.files_to_import[idx]
            
    def on_drop_files(self, event):
        # TkinterDnD2 returns a string of paths, space separated, wrapped in curly braces if spaces exist
        files = self.root.tk.splitlist(event.data)
        for f in files:
            self._add_file_or_folder(f)

    def _add_file_or_folder(self, path):
        if os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    full_path = os.path.join(root, file)
                    if full_path not in self.files_to_import:
                        self.files_to_import.append(full_path)
                        self.listbox.insert(tk.END, full_path)
        else:
            if path not in self.files_to_import:
                self.files_to_import.append(path)
                self.listbox.insert(tk.END, path)

    def select_files(self):
        try:
            if sys.platform.startswith('linux'):
                import subprocess
                result = subprocess.run(['zenity', '--file-selection', '--multiple', '--separator=|'], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    files = result.stdout.strip().split('|')
                else:
                    return
            else:
                files = filedialog.askopenfilenames()
        except Exception:
            files = filedialog.askopenfilenames()
            
        for f in files:
            self._add_file_or_folder(f)
                
    def select_folder(self):
        try:
            if sys.platform.startswith('linux'):
                import subprocess
                result = subprocess.run(['zenity', '--file-selection', '--directory'], capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    folder = result.stdout.strip()
                else:
                    return
            else:
                folder = filedialog.askdirectory()
        except Exception:
            folder = filedialog.askdirectory()
            
        if folder:
            self._add_file_or_folder(folder)
                        
    def clear_list(self):
        self.files_to_import.clear()
        self.listbox.delete(0, tk.END)

    def start_import(self):
        if not self.files_to_import:
            return
            
        self.start_btn.config(state='disabled')
        self.category_combo.config(state='disabled')
        
        cat_name = self.category_var.get().strip()
        
        # Gather selected tags
        selected_indices = self.tags_listbox.curselection()
        tags = [self.tags_listbox.get(i) for i in selected_indices]
        
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
                self.root.after(0, lambda idx=i: self.listbox.itemconfig(idx, {'bg': '#d4edda'}))
                
            except Exception as e:
                failed += 1
                traceback.print_exc()
                self.root.after(0, lambda idx=i: self.listbox.itemconfig(idx, {'bg': '#f8d7da'}))
                
            self.progress_var.set((i+1) / total * 100)
            
        self.status_var.set(f"Completed! {success} added, {failed} failed.")
        self.root.after(0, lambda: self.start_btn.config(state='normal'))
        self.root.after(0, lambda: self.category_combo.config(state='normal'))
        
        # Reload categories/tags to reflect any new ones that were created during import
        self.root.after(0, self.load_categories)

if __name__ == "__main__":
    if DND_AVAILABLE:
        root = TkinterDnD.Tk()
    else:
        root = tk.Tk()
        
    style = ttk.Style(root)
    style.theme_use('clam')
    
    app = PandoraImporter(root)
    root.mainloop()
