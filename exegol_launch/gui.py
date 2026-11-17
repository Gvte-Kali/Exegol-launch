"""Interface Tkinter ; les opérations de découverte et de lancement sont déléguées au moteur."""

import json
import tkinter as tk
from tkinter import ttk, messagebox
from .core import discover, launch_app, state_dir, config_file


def run():
    """Construire la fenêtre, connecter les actions puis démarrer la boucle événementielle Tkinter."""
    root = tk.Tk()
    root.title("Exegol-launch")
    root.geometry("900x600")
    root.minsize(650, 420)
    root.configure(bg="#111827")
    # Le thème ttk intégré évite une bibliothèque graphique supplémentaire.
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
    ttk.Label(frame, text="Tes outils Exegol, dans ton bureau Linux.").pack(anchor="w", pady=(4, 18))
    # Les variables Tk permettent de réagir à la saisie sans bouton de recherche.
    search = tk.StringVar()
    entry = ttk.Entry(frame, textvariable=search)
    entry.pack(fill="x")
    toolbar = ttk.Frame(frame)
    toolbar.pack(fill="x", pady=12)
    only_favorites = tk.BooleanVar()
    # Un fichier manquant ou invalide ne doit pas empêcher le menu de s’ouvrir.
    favorite_path = state_dir() / "favorites.json"
    try:
        saved = json.loads(favorite_path.read_text())
        favorites = set(saved) if isinstance(saved, list) and all(isinstance(x, str) for x in saved) else set()
    except (OSError, ValueError, TypeError):
        favorites = set()
    ttk.Checkbutton(toolbar, text="Favoris uniquement", variable=only_favorites, command=lambda: refresh()).pack(side="left")
    ttk.Button(toolbar, text="Actualiser", command=lambda: reload()).pack(side="right")
    tree_frame = ttk.Frame(frame)
    tree_frame.pack(fill="both", expand=True)
    # Chaque ligne est liée à un objet Application via le dictionnaire visible.
    tree = ttk.Treeview(tree_frame, columns=("favorite", "name", "category", "type"), show="headings", selectmode="browse")
    for col, title, width in [("favorite", "★", 45), ("name", "Application", 300), ("category", "Catégorie", 170), ("type", "Mode", 90)]:
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
    ttk.Button(actions, text="★ Favori", command=lambda: toggle_favorite()).pack(side="left")
    ttk.Button(actions, text="Configuration", command=lambda: messagebox.showinfo("Applications personnalisées", f"Ajoute tes commandes dans :\n{config_file()}\n\nFormat : liste JSON avec name et argv.\nVoir apps.example.json dans le projet.")).pack(side="left", padx=8)
    ttk.Button(actions, text="Lancer ↵", command=lambda: start()).pack(side="right")
    apps, warnings = [], []
    # Les identifiants de lignes sont temporaires ; les favoris utilisent les IDs stables des apps.
    visible = {}

    def refresh(*_):
        """Reconstruire les lignes visibles à partir de la recherche et du filtre de favoris."""
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
        status.set(f"{len(visible)} application(s) · {len(warnings)} avertissement(s)" if apps else "Aucune application détectée. Ajoute tes commandes via apps.json.")

    def reload():
        """Relire les sources d’applications et afficher les éventuelles erreurs de configuration."""
        nonlocal apps, warnings
        apps, warnings = discover()
        refresh()
        if warnings:
            messagebox.showwarning("Découverte des applications", "\n".join(warnings))

    def selected():
        """Retrouver l’application associée à la ligne sélectionnée, ou None sans sélection."""
        selection = tree.selection()
        return visible.get(selection[0]) if selection else None

    def toggle_favorite():
        """Inverser le favori sélectionné et enregistrer la liste par remplacement du fichier."""
        app = selected()
        if app:
            if app.id in favorites:
                favorites.remove(app.id)
            else:
                favorites.add(app.id)
            try:
                # Remplacer le fichier complet limite le risque de JSON partiellement écrit.
                temp = favorite_path.with_suffix(".tmp")
                temp.write_text(json.dumps(sorted(favorites)))
                temp.replace(favorite_path)
            except OSError as exc:
                messagebox.showerror("Enregistrement impossible", str(exc))
            refresh()

    def start():
        """Lancer la sélection et signaler les erreurs immédiates sans fermer le menu."""
        app = selected()
        if app:
            try:
                logfile = launch_app(app)
                status.set(f"Commande démarrée : {app.name} · journal : {logfile}")
            except (OSError, ValueError, RuntimeError) as exc:
                messagebox.showerror("Lancement impossible", str(exc))

    # Les callbacks ne sont exécutés qu’après la définition de toutes les actions.
    search.trace_add("write", refresh)
    tree.bind("<Double-1>", lambda _: start())
    root.bind("<Return>", lambda _: start())
    root.bind("<Control-f>", lambda _: entry.focus_set())
    root.bind("<Escape>", lambda _: root.destroy())
    reload()
    entry.focus_set()
    root.mainloop()
