# Exegol-launch

Lanceur graphique Python/Tkinter **exécuté dans Exegol**, accessible avec **`launch`**.
Il ouvre son menu puis rend la main au terminal. Les applications sélectionnées restent
dans le conteneur et utilisent l’environnement graphique de ton terminal : si `burpsuite`
s’ouvre déjà sur ton bureau Hyprland, le launcher reprend ce même affichage.

Recherche, catégories, favoris persistants, découverte des fichiers `.desktop`, commandes
personnalisées et journaux par application. Aucune bibliothèque Python tierce.

## Installer automatiquement dans les futurs conteneurs

**À exécuter sur ton hôte Omarchy, avec ton utilisateur Exegol, sans sudo :**

```bash
curl -fsSL https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/main/setup-exegol.sh | bash
```

Ce one-liner télécharge le projet dans `~/.exegol/my-resources/setup/`, sauvegarde le
`load_user_setup.sh` existant et ajoute un bloc géré **avant son code**, après le shebang.
Son contenu existant est conservé, y compris les installations Exeflow. Une nouvelle
exécution remplace uniquement le bloc Exegol-launch et prépare un nouveau payload.
Les anciens payloads et sauvegardes sont conservés ; les mises à jour ne sont pas automatiques.

Au **premier démarrage de chaque nouveau conteneur**, le hook officiel Exegol installe
le projet sous `/opt/exegol-launch` et crée `/usr/local/bin/launch`.
Les sources sont déjà dans les ressources partagées : aucun téléchargement GitHub n’est
nécessaire à cette étape. Si Python/Tkinter manque, `apt-get` utilise le réseau pour l’installer.
L’installation du launcher n’exige pas de serveur graphique ; seul son lancement en exige un.
Un échec affiche un avertissement sans interrompre les autres personnalisations du hook.

**Conditions :** `my-resources` doit être activé et monté dans `/opt/my-resources` ;
le hook doit être exécuté par Exegol avec les droits root, sur une image avec Python 3.10+
(ou un dépôt apt proposant cette version). Les conteneurs existants ne sont pas modifiés.
Python 3 et curl sont nécessaires sur l’hôte. Aucun Docker socket n’est utilisé par ce script.

Si `volumes.my_resources_path` dans ta configuration Exegol désigne un autre dossier :

```bash
curl -fsSL https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/main/setup-exegol.sh | bash -s -- /chemin/vers/my-resources
```

Le chemin par défaut n’est pas déduit automatiquement du fichier de configuration Exegol.
N’utilise pas `sudo` sur l’hôte : il sélectionnerait potentiellement les ressources de root.

## Installer dans un conteneur existant

**À exécuter dans le terminal Exegol**, en root :

```bash
curl -fsSL https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/main/install.sh | bash
```

Puis :

```bash
launch
```

L’installateur choisit un Python avec Tkinter, préfère celui du système et installe les
composants manquants via apt sur Exegol. Il refuse d’écraser une commande `launch` non gérée.
Une réexécution met à jour une installation gérée. Les fichiers sont préparés dans une
nouvelle release avant activation ; un téléchargement échoué conserve la version active.
Les favoris et commandes personnalisées restent dans les dossiers XDG de chaque utilisateur.

Sans root, Python/Tkinter doivent déjà être installés ; le projet va dans
`~/.local/share/exegol-launch` et la commande dans `~/.local/bin` (à ajouter au `PATH`).
L’ancienne version initiale du projet n’avait pas de marqueur de gestion : retire son
wrapper `launch` après avoir vérifié son origine avant d’utiliser ce nouvel installateur.

### Depuis un clone / sans télécharger les sources

```bash
git clone https://github.com/Gvte-Kali/Exegol-launch.git
cd Exegol-launch
bash install.sh
```

L’installateur détecte les sources locales. Pas de pip, de venv ni de modification du
Python système. Le paquet peut également être installé avec `pip install .` dans un venv.

Pour une version reproductible, remplace `main` dans l’URL du script par un SHA de commit
et passe **le même SHA** avec `EXEGOL_LAUNCH_REF`. Par exemple, sur l’hôte :

```bash
REF='<SHA-du-commit>'; curl -fsSL "https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/$REF/setup-exegol.sh" | EXEGOL_LAUNCH_REF="$REF" bash
```

Tu peux aussi télécharger les scripts, les lire, puis les exécuter localement.

## Utilisation

- `launch` : ouvre la GUI et libère le terminal.
- `launch --foreground` : conserve les erreurs du launcher dans le terminal.
- `launch --list` : liste les applications sans ouvrir de fenêtre.
- `launch --version` : affiche la version.
- Entrée ou double clic : lance la sélection ; `Ctrl+F` : recherche ; Échap : ferme le menu.
- Favoris et bouton Actualiser après ajout d’un outil.

Les entrées XDG `.desktop` sont découvertes dans le conteneur, avec priorité aux entrées
utilisateur. Hidden/NoDisplay et les exécutables absents sont ignorés. Burp Suite,
Firefox, Wireshark, ZAP, BloodHound et Ghidra ont une détection complémentaire si leur
commande est dans le PATH. Les restrictions OnlyShowIn/NotShowIn ne filtrent pas ce menu.
Les alias et fonctions de shell ne sont pas des exécutables : ajoute-les explicitement.

## Applications personnalisées

Crée `~/.config/exegol-launch/apps.json` (ou `$XDG_CONFIG_HOME/exegol-launch/apps.json`) :

```json
[
  {"name": "Burp personnalisé", "argv": ["burpsuite"], "category": "Web"},
  {"name": "Shell de travail", "argv": ["bash"], "terminal": true}
]
```

`argv` est une liste d’arguments sans évaluation implicite par un shell. Utilise des
chemins absolus : `~` et `$VAR` ne sont pas développés. Autres champs : `description`,
`category` et `cwd`. Exemple complet : [apps.example.json](apps.example.json).
Pour une commande nécessitant réellement un shell, utilise explicitement
`["bash", "-lc", "ta commande"]` avec sa configuration appropriée.

Les outils CLI demandent un terminal présent **dans le conteneur**. Au besoin :

```bash
export EXEGOL_LAUNCH_TERMINAL='xterm -e'
```

Cette variable fournit le terminal et les options avant les arguments de l’outil.
Sans réglage : x-terminal-emulator, xterm, kitty puis alacritty sont recherchés.

## Hyprland et diagnostic

Aucun DISPLAY n’est inventé et aucune permission graphique n’est modifiée :
DISPLAY, XAUTHORITY, WAYLAND_DISPLAY et les autres variables sont hérités du terminal.
Tkinter sous Linux nécessite généralement X11/XWayland et un DISPLAY accessible.
Si la fenêtre part dans le VNC, vérifie l’environnement du terminal utilisé ; le projet
ne remplace pas le partage graphique Exegol.

Les outils sont détachés du launcher : fermer le menu ne les ferme pas. Arrêter le
conteneur ou son serveur graphique peut en revanche les arrêter.

Journaux : `~/.local/state/exegol-launch/` ou `$XDG_STATE_HOME/exegol-launch/`.
`launcher.log` concerne le menu ; les autres fichiers correspondent aux applications.
« Commande démarrée » confirme la création du processus, pas l’ouverture effective
d’une fenêtre. Consulte le journal si un outil se ferme immédiatement. Les logs sont
cumulés ; tu peux les supprimer quand les outils concernés sont arrêtés.

## Tests

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh setup-exegol.sh
```

Tests de découverte XDG, arguments, lancement indépendant et installation/registration
isolées. La validation visuelle et l’intégration réelle Exegol/Hyprland restent à faire
sur ta machine ; aucun conteneur Exegol n’est disponible dans l’environnement de développement.
Le mécanisme du hook est documenté dans le [modèle officiel Exegol](https://github.com/ThePorgs/Exegol-images/blob/main/sources/assets/exegol/skel/load_user_setup.sh).

## Désinstallation

Dans le conteneur, retire uniquement le wrapper géré `/usr/local/bin/launch` et
`/opt/exegol-launch` (ou les chemins utilisateur si installé sans root).
Sur l’hôte, retire le bloc `# BEGIN Exegol-launch` à `# END Exegol-launch` dans
`my-resources/setup/load_user_setup.sh` pour désactiver l’installation future.
Les payloads `.exegol-launch.*` de ce dossier peuvent ensuite être supprimés si aucun
hook ne les référence. Garde les sauvegardes nécessaires. Les préférences utilisateur
et dépendances Python/Tkinter ne sont pas supprimées automatiquement.

## Améliorations possibles

- Icônes des applications et sélection par catégorie.
- Éditeur de commandes intégré à la GUI.
- Détection des fermetures immédiates avec accès direct au journal.
- Mode instance unique et commande de diagnostic de l’affichage.
