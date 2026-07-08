import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import secrets
import json
import traceback
import hashlib
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

def compute_file_hash(path: str) -> str:
    """Compute SHA-256 of a file in 4MB streaming chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

class PandoraImporter:
    def __init__(self, root):
        self.root = root
        self.root.title("Pandora Mass Importer (Offline)")
        self.root.geometry("800x650")
        
        self.security = None
        self.db = None
        self.vault = None
        self.paths = get_vault_paths()
        self.files_to_import = []
        self.cli_files = sys.argv[1:] if len(sys.argv) > 1 else []
        
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
        self.listbox = tk.Listbox(files_frame, selectmode=tk.EXTENDED, yscrollcommand=list_scroll.set, exportselection=False)
        self.listbox.pack(fill='both', expand=True)
        list_scroll.config(command=self.listbox.yview)
        
        # Shortcuts for file list
        self.listbox.bind("<Control-a>", self.select_all_files)
        self.listbox.bind("<Delete>", self.remove_selected_files)
        self.listbox.bind("<BackSpace>", self.remove_selected_files)
        self.listbox.bind("<<ListboxSelect>>", self.on_listbox_select)
        
        if DND_AVAILABLE:
            self.listbox.drop_target_register(DND_FILES)
            self.listbox.dnd_bind('<<Drop>>', self.on_drop_files)
            
        # Add any files passed from CLI (like Nemo actions)
        if hasattr(self, 'cli_files') and self.cli_files:
            for f in self.cli_files:
                self._add_file_or_folder(f)
            self.cli_files = []
        
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
        self.category_combo.bind("<<ComboboxSelected>>", self.on_category_changed)
        self.category_combo.bind("<KeyRelease>", self.on_category_changed)
        
        # Tags
        tags_frame = ttk.Frame(options_frame)
        tags_frame.pack(fill='both', expand=True, pady=5)
        ttk.Label(tags_frame, text="Select Tags:").pack(side='left', anchor='n', padx=5)
        
        tags_list_frame = ttk.Frame(tags_frame)
        tags_list_frame.pack(side='left', fill='both', expand=True, padx=5)
        
        tag_scroll = ttk.Scrollbar(tags_list_frame)
        tag_scroll.pack(side='right', fill='y')
        self.tags_listbox = tk.Listbox(tags_list_frame, selectmode=tk.MULTIPLE, height=4, yscrollcommand=tag_scroll.set, exportselection=False)
        self.tags_listbox.pack(side='left', fill='both', expand=True)
        tag_scroll.config(command=self.tags_listbox.yview)
        self.tags_listbox.bind("<<ListboxSelect>>", self.on_tags_changed)
        
        new_tag_frame = ttk.Frame(tags_frame)
        new_tag_frame.pack(side='left', anchor='n', padx=5)
        ttk.Label(new_tag_frame, text="Add New Tag:").pack(anchor='w')
        self.new_tag_var = tk.StringVar()
        new_tag_entry = ttk.Entry(new_tag_frame, textvariable=self.new_tag_var)
        new_tag_entry.pack(fill='x')
        new_tag_entry.bind("<Return>", lambda e: self.add_new_tag())
        ttk.Button(new_tag_frame, text="Add", command=self.add_new_tag).pack(fill='x', pady=2)

        # Duplicate Handling
        dup_frame = ttk.Frame(options_frame)
        dup_frame.pack(fill='x', pady=5)
        ttk.Label(dup_frame, text="Duplicate Handling:").pack(side='left', padx=5)
        self.duplicate_mode_var = tk.StringVar(value="skip")
        dup_combo = ttk.Combobox(
            dup_frame,
            textvariable=self.duplicate_mode_var,
            values=["skip", "replace", "allow"],
            state="readonly",
            width=12
        )
        dup_combo.pack(side='left', padx=5)
        ttk.Label(dup_frame, text="(skip = ignore dupe, replace = overwrite old, allow = import anyway)",
                  font=("Helvetica", 8), foreground="gray").pack(side='left', padx=5)
        
        # Start & Progress
        self.start_btn = ttk.Button(self.main_frame, text="START MASS IMPORT", command=self.start_import)
        self.start_btn.pack(pady=10, fill='x')
        
        self.progress_var = tk.DoubleVar()
        self.progress = ttk.Progressbar(self.main_frame, variable=self.progress_var, maximum=100)
        self.progress.pack(fill='x', pady=5)
        
        self.status_var = tk.StringVar(value="Ready")
        self.load_categories()
        self.load_tags()
        self.log("info", "Vault unlocked. Ready to import.")

    def log(self, level: str, msg: str):
        """Log to standard stdout/terminal."""
        import datetime
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        colors = {
            "ok": "\033[92m",      # Green
            "skip": "\033[93m",    # Yellow
            "replace": "\033[95m", # Magenta
            "err": "\033[91m",     # Red
            "info": "\033[94m"     # Blue
        }
        reset = "\033[0m"
        color = colors.get(level, "")
        print(f"{color}[{ts}] [{level.upper()}] {msg}{reset}", flush=True)

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
            self.on_tags_changed()
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
        self.on_listbox_select()
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

    def _create_import_item(self, path):
        # Get UI settings for category/tags as defaults if set
        ui_cat = self.category_var.get().strip()
        if ui_cat:
            cat = ui_cat
        else:
            filename = os.path.basename(path)
            ext = filename.split('.')[-1].lower() if '.' in filename else ''
            if ext in ['mp4', 'mov', 'avi', 'mkv', 'webm', 'flv', 'wmv']:
                cat = "Video"
            elif ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
                cat = "Image"
            elif ext in ['pdf', 'txt', 'doc', 'docx']:
                cat = "Document"
            else:
                cat = "Other"

        selected_tag_indices = self.tags_listbox.curselection()
        ui_tags = [self.tags_listbox.get(i) for i in selected_tag_indices]

        return {
            "path": path,
            "category": cat,
            "tags": list(ui_tags),
            "status": "Checking...",
            "is_duplicate": False
        }

    def _add_file_or_folder(self, path):
        if os.path.isdir(path):
            for root, dirs, files in os.walk(path):
                for file in files:
                    full_path = os.path.join(root, file)
                    if not any(f["path"] == full_path for f in self.files_to_import):
                        item = self._create_import_item(full_path)
                        self.files_to_import.append(item)
                        self._listbox_insert(item)
        else:
            if not any(f["path"] == path for f in self.files_to_import):
                item = self._create_import_item(path)
                self.files_to_import.append(item)
                self._listbox_insert(item)
        self._trigger_duplicate_checks()

    def _listbox_insert(self, item):
        idx = self.listbox.size()
        self.listbox.insert(tk.END, "")
        self._update_listbox_item_text(idx)

    def _update_listbox_item_text(self, index):
        if index >= len(self.files_to_import):
            return
        item = self.files_to_import[index]
        status_str = f"[{item['status']}]" if item['status'] else ""
        cat_str = f" [{item['category']}]" if item['category'] else ""
        tags_str = f" #{' #'.join(item['tags'])}" if item['tags'] else ""
        text = f"{status_str} {item['path']}{cat_str}{tags_str}"
        
        # We need to temporarily disable updates to prevent selection events from firing
        was_selected = index in self.listbox.curselection()
        self._updating_inputs = True
        try:
            self.listbox.delete(index)
            self.listbox.insert(index, text)
            if was_selected:
                self.listbox.selection_set(index)
        finally:
            self._updating_inputs = False
            
        # Re-apply color styling based on status
        if "DUPLICATE" in item['status'] or "SKIPPED" in item['status']:
            self.listbox.itemconfig(index, {'bg': '#3a3000', 'fg': '#f9e2af'})
        elif "OK" in item['status'] or "Complete" in item['status'] or "✓" in item['status']:
            self.listbox.itemconfig(index, {'bg': '#002000', 'fg': '#a6e3a1'})
        elif "FAILED" in item['status'] or "✗" in item['status']:
            self.listbox.itemconfig(index, {'bg': '#200000', 'fg': '#f38ba8'})
        else:
            self.listbox.itemconfig(index, {'bg': '#1a1a1a', 'fg': '#cdd6f4'})

    def _trigger_duplicate_checks(self):
        if not hasattr(self, "_db_check_thread") or not self._db_check_thread.is_alive():
            self._db_check_thread = threading.Thread(target=self._run_duplicate_checks, daemon=True)
            self._db_check_thread.start()

    def _run_duplicate_checks(self):
        while True:
            target_idx = None
            for idx, item in enumerate(self.files_to_import):
                if item["status"] == "Checking...":
                    target_idx = idx
                    break
            
            if target_idx is None:
                break
                
            item = self.files_to_import[target_idx]
            filepath = item["path"]
            try:
                file_hash = compute_file_hash(filepath)
                with self.db.session_scope() as session:
                    existing = session.query(DBFile).filter(DBFile.file_hash == file_hash).first()
                    is_dup = existing is not None
                
                if is_dup:
                    item["status"] = "DUPLICATE"
                    item["is_duplicate"] = True
                else:
                    item["status"] = "Ready"
                    item["is_duplicate"] = False
            except Exception as e:
                item["status"] = "Error"
                print(f"Error checking duplicate for {filepath}: {e}")
                
            self.root.after(0, lambda idx=target_idx: self._update_listbox_item_text(idx))

    def on_listbox_select(self, event=None):
        if getattr(self, "_updating_inputs", False):
            return
            
        selected_indices = self.listbox.curselection()
        if not selected_indices:
            return
            
        self._updating_inputs = True
        try:
            # If single select:
            if len(selected_indices) == 1:
                item = self.files_to_import[selected_indices[0]]
                self.category_var.set(item["category"])
                # Select tags
                self.tags_listbox.selection_clear(0, tk.END)
                all_tags = self.tags_listbox.get(0, tk.END)
                for t in item["tags"]:
                    if t in all_tags:
                        self.tags_listbox.selection_set(all_tags.index(t))
            else:
                # If multi select, find common categories and common tags
                cats = {self.files_to_import[idx]["category"] for idx in selected_indices}
                if len(cats) == 1:
                    self.category_var.set(list(cats)[0])
                else:
                    self.category_var.set("")
                    
                common_tags = None
                for idx in selected_indices:
                    file_tags = set(self.files_to_import[idx]["tags"])
                    if common_tags is None:
                        common_tags = file_tags
                    else:
                        common_tags = common_tags.intersection(file_tags)
                
                self.tags_listbox.selection_clear(0, tk.END)
                if common_tags:
                    all_tags = self.tags_listbox.get(0, tk.END)
                    for t in common_tags:
                        if t in all_tags:
                            self.tags_listbox.selection_set(all_tags.index(t))
        finally:
            self._updating_inputs = False

    def on_category_changed(self, event=None):
        if getattr(self, "_updating_inputs", False):
            return
        selected_indices = self.listbox.curselection()
        if not selected_indices:
            return
        cat = self.category_var.get().strip()
        for idx in selected_indices:
            self.files_to_import[idx]["category"] = cat
            self._update_listbox_item_text(idx)

    def on_tags_changed(self, event=None):
        if getattr(self, "_updating_inputs", False):
            return
        selected_indices = self.listbox.curselection()
        if not selected_indices:
            return
            
        selected_tag_indices = self.tags_listbox.curselection()
        tags = [self.tags_listbox.get(i) for i in selected_tag_indices]
        
        for idx in selected_indices:
            self.files_to_import[idx]["tags"] = list(tags)
            self._update_listbox_item_text(idx)

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
        
        threading.Thread(target=self._import_thread, daemon=True).start()

    def _import_thread(self):
        total = len(self.files_to_import)
        success = 0
        failed = 0
        skipped = 0
        
        for i, item in enumerate(self.files_to_import):
            filepath = item["path"]
            filename = os.path.basename(filepath)
            self.status_var.set(f"[{i+1}/{total}] Processing: {filename}...")
            
            try:
                ext = filename.split('.')[-1] if '.' in filename else 'tmp'
                ext_lower = ext.lower()

                # --- Duplicate detection ---
                file_hash = compute_file_hash(filepath)
                self.root.after(0, lambda msg=f"Hashing: {filename}": self.log("info", msg))
                with self.db.session_scope() as session:
                    existing = session.query(DBFile).filter(DBFile.file_hash == file_hash).first()
                    existing_id = existing.id if existing else None

                if existing_id:
                    mode = self.duplicate_mode_var.get()
                    if mode == "skip":
                        skipped += 1
                        self.root.after(0, lambda idx=i: (
                            self.listbox.delete(idx),
                            self.listbox.insert(idx, f"[SKIPPED – EXISTS] {self.files_to_import[idx]['path']}"),
                            self.listbox.itemconfig(idx, {'bg': '#3a3000', 'fg': '#f9e2af'}),
                            self.log("skip", f"SKIPPED (duplicate): {filename}")
                        ))
                        self.progress_var.set((i + 1) / total * 100)
                        continue
                    elif mode == "replace":
                        self.vault.delete_file(existing_id)
                        with self.db.session_scope() as session:
                            old = session.query(DBFile).filter(DBFile.id == existing_id).first()
                            if old:
                                session.delete(old)
                        self.root.after(0, lambda fn=filename: self.log("replace", f"REPLACING existing: {fn}"))
                    else:
                        self.root.after(0, lambda fn=filename: self.log("info", f"ALLOWING duplicate: {fn}"))
                    # mode == "allow" or "replace": fall through and import

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
                final_cat_name = item["category"]
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
                    for tname in item["tags"]:
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
                        metadata_created_at=creation_date,
                        file_hash=file_hash
                    )
                    
                    if tag_objs:
                        db_file.tags = tag_objs
                    session.add(db_file)
                    # Capture tag names INSIDE the session while objects are still attached
                    tag_names = [t.name for t in tag_objs]
                
                success += 1
                cat_label = f"[{final_cat_name}]" if final_cat_name else ""
                tag_label = f" #{' #'.join(tag_names)}" if tag_names else ""
                self.root.after(0, lambda idx=i, fp=filepath, cl=cat_label, tl=tag_label: (
                    self.listbox.delete(idx),
                    self.listbox.insert(idx, f"✓ {fp}  {cl}{tl}"),
                    self.listbox.itemconfig(idx, {'bg': '#002000', 'fg': '#a6e3a1'})
                ))
                self.root.after(0, lambda fn=filename, cl=cat_label, tl=tag_label: self.log("ok", f"OK: {fn}  {cl}{tl}"))
                
            except Exception as e:
                failed += 1
                traceback.print_exc()
                err_msg = str(e)
                self.root.after(0, lambda idx=i, fp=filepath: (
                    self.listbox.delete(idx),
                    self.listbox.insert(idx, f"✗ {fp}"),
                    self.listbox.itemconfig(idx, {'bg': '#200000', 'fg': '#f38ba8'})
                ))
                self.root.after(0, lambda fn=filename, em=err_msg: self.log("err", f"FAILED: {fn} — {em}"))
                
            self.progress_var.set((i+1) / total * 100)
            
        self.status_var.set(f"Completed! {success} added, {skipped} skipped (duplicate), {failed} failed.")
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
