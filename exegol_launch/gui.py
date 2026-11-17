"""Tkinter interface; delegate discovery and process launching to the engine."""

import json
import tkinter as tk
from tkinter import ttk, messagebox
from .core import discover, launch_app, state_dir, config_file


def run():
    """Build the window, connect actions and start the Tkinter event loop."""
    root = tk.Tk()
    root.title("Exegol-launch")
    root.geometry("900x600")
    root.minsize(650, 420)
    root.configure(bg="#111827")
    # The built-in ttk theme avoids an additional GUI dependency.
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background="#111827", foreground="#e5e7eb", font=("Sans", 11))
    style.configure("TButton", padding=(12, 8), background="#263449")
    style.map("TButton", background=[("active", "#334155")])
    style.configure("TEntry", fieldbackground="#1e293b", foreground="#f8fafc", padding=8)
    style.configure("Treeview", background="#182235", fieldbackground="#182235", foreground="#e5e7eb", rowheight=36, borderwidth=0)
    style.configure("Treeview.Heading", background="#263449", padding=8)
    style.map("Treeview", background=[("selected", "#155e75")])
    frame = ttk.Frame(root, padding=24)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="Exegol-launch", font=("Sans", 23, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Your Exegol tools, on your Linux desktop.").pack(anchor="w", pady=(4, 18))
    # Tk variables update results as text is entered, without a search button.
    search = tk.StringVar()
    entry = ttk.Entry(frame, textvariable=search)
    entry.pack(fill="x")
    toolbar = ttk.Frame(frame)
    toolbar.pack(fill="x", pady=12)
    only_favorites = tk.BooleanVar()
    # A missing or invalid favorites file must not prevent the menu from opening.
    favorite_path = state_dir() / "favorites.json"
    try:
        saved = json.loads(favorite_path.read_text())
        favorites = set(saved) if isinstance(saved, list) and all(isinstance(x, str) for x in saved) else set()
    except (OSError, ValueError, TypeError):
        favorites = set()
    ttk.Checkbutton(toolbar, text="Favorites only", variable=only_favorites, command=lambda: refresh()).pack(side="left")
    ttk.Button(toolbar, text="Refresh", command=lambda: reload()).pack(side="right")
    tree_frame = ttk.Frame(frame)
    tree_frame.pack(fill="both", expand=True)
    # Map each row to an Application object through the visible dictionary.
    tree = ttk.Treeview(tree_frame, columns=("favorite", "name", "category", "type"), show="headings", selectmode="browse")
    for col, title, width in [("favorite", "★", 45), ("name", "Application", 300), ("category", "Category", 170), ("type", "Mode", 90)]:
        tree.heading(col, text=title)
        tree.column(col, width=width, stretch=col != "favorite")
    scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scrollbar.set)
    scrollbar.pack(side="right", fill="y")
    tree.pack(fill="both", expand=True)
    status = tk.StringVar(value="")
    ttk.Label(frame, textvariable=status, wraplength=800).pack(anchor="w", pady=10)
    actions = ttk.Frame(frame)
    actions.pack(fill="x")
    ttk.Button(actions, text="★ Favorite", command=lambda: toggle_favorite()).pack(side="left")
    ttk.Button(actions, text="Configuration", command=lambda: messagebox.showinfo("Custom applications", f"Add custom commands in:\n{config_file()}\n\nFormat: JSON list with name and argv fields.\nSee apps.example.json in the project.")).pack(side="left", padx=8)
    ttk.Button(actions, text="Launch ↵", command=lambda: start()).pack(side="right")
    apps, warnings = [], []
    # Row IDs are temporary; favorites use stable application IDs.
    visible = {}

    def refresh(*_):
        """Rebuild visible rows using the search query and favorites filter."""
        tree.delete(*tree.get_children())
        visible.clear()
        query = search.get().casefold().strip()
        for app in apps:
            if only_favorites.get() and app.id not in favorites:
                continue
            if query and query not in f"{app.name} {app.category} {app.description}".casefold():
                continue
            key = str(len(visible))
            visible[key] = app
            tree.insert("", "end", iid=key, values=("★" if app.id in favorites else "", app.name, app.category, "Terminal" if app.terminal else "GUI"))
        if visible:
            tree.selection_set("0")
        status.set(f"{len(visible)} application(s) · {len(warnings)} warning(s)" if apps else "No applications detected. Add custom commands in apps.json.")

    def reload():
        """Reload application sources and display any configuration warnings."""
        nonlocal apps, warnings
        apps, warnings = discover()
        refresh()
        if warnings:
            messagebox.showwarning("Application discovery", "\n".join(warnings))

    def selected():
        """Return the application for the selected row, or None if nothing is selected."""
        selection = tree.selection()
        return visible.get(selection[0]) if selection else None

    def toggle_favorite():
        """Toggle the selected favorite and save the list by replacing the file."""
        app = selected()
        if app:
            if app.id in favorites:
                favorites.remove(app.id)
            else:
                favorites.add(app.id)
            try:
                # Replacing the whole file reduces the risk of partially written JSON.
                temp = favorite_path.with_suffix(".tmp")
                temp.write_text(json.dumps(sorted(favorites)))
                temp.replace(favorite_path)
            except OSError as exc:
                messagebox.showerror("Unable to save", str(exc))
            refresh()

    def start():
        """Launch the selection and report immediate errors without closing the menu."""
        app = selected()
        if app:
            try:
                logfile = launch_app(app)
                status.set(f"Command started: {app.name} · log: {logfile}")
            except (OSError, ValueError, RuntimeError) as exc:
                messagebox.showerror("Unable to launch", str(exc))

    # Callbacks run only after all actions have been defined.
    search.trace_add("write", refresh)
    tree.bind("<Double-1>", lambda _: start())
    root.bind("<Return>", lambda _: start())
    root.bind("<Control-f>", lambda _: entry.focus_set())
    root.bind("<Escape>", lambda _: root.destroy())
    reload()
    entry.focus_set()
    root.mainloop()
