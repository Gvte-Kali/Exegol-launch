# Exegol-launch

Lanceur graphique Python/Tkinter **exécuté dans Exegol**, accessible avec **`launch`**.
Il ouvre son menu puis rend la main au terminal. Les applications sélectionnées restent
dans le conteneur et utilisent l’environnement graphique du terminal depuis lequel le programme est lancé. Les fenêtres apparaissent sur le
serveur graphique déjà configuré pour le conteneur, sans passer par un bureau VNC
lorsque le partage graphique avec l’hôte est actif.

Recherche, catégories, favoris persistants, découverte des fichiers `.desktop`, commandes
personnalisées et journaux par application. Aucune bibliothèque Python tierce.

## Prérequis

- Un conteneur Exegol avec Python 3.10 ou plus récent et Tkinter.
- Un partage graphique fonctionnel pour afficher les fenêtres sur l’hôte.
- Sous Wayland, un accès XWayland utilisable par Tkinter est généralement nécessaire.
- Pour les installateurs : Bash et curl ; apt est pris en charge pour installer les
  dépendances manquantes dans les images Exegol basées sur Debian.

Le projet n’exige aucun environnement de bureau particulier. La présence de Wayland
seul ne garantit pas que Tkinter puisse ouvrir une fenêtre. L’installation automatique
est prévue pour Exegol ; elle ne configure pas le partage graphique de Docker.

## Installer automatiquement dans les futurs conteneurs

**À exécuter sur la machine hôte, avec le compte utilisateur qui utilise Exegol, sans sudo :**

```bash
curl -fsSL https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/main/setup-exegol.sh | bash
```

Ce one-liner télécharge le projet dans `~/.exegol/my-resources/setup/`, sauvegarde le
`load_user_setup.sh` existant et ajoute un bloc géré **avant son code**, après le shebang.
Les personnalisations et installations déjà présentes sont conservées. Une nouvelle
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

Si `volumes.my_resources_path` dans la configuration Exegol désigne un autre dossier :

```bash
curl -fsSL https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/main/setup-exegol.sh | bash -s -- /chemin/vers/my-resources
```

Le chemin par défaut n’est pas déduit automatiquement du fichier de configuration Exegol.
Ne pas utiliser `sudo` sur l’hôte : il sélectionnerait potentiellement les ressources de root.

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
L’ancienne version initiale du projet n’avait pas de marqueur de gestion : supprimer son
wrapper `launch` après avoir vérifié son origine avant d’utiliser ce nouvel installateur.

### Depuis un clone / sans télécharger les sources

```bash
git clone https://github.com/Gvte-Kali/Exegol-launch.git
cd Exegol-launch
bash install.sh
```

L’installateur détecte les sources locales. Pas de pip, de venv ni de modification du
Python système. Le paquet peut également être installé avec `pip install .` dans un venv.

Pour une version reproductible, remplacer `main` dans l’URL du script par un SHA de commit
et transmettre **le même SHA** avec `EXEGOL_LAUNCH_REF`. Par exemple, sur l’hôte :

```bash
REF='<SHA-du-commit>'; curl -fsSL "https://raw.githubusercontent.com/Gvte-Kali/Exegol-launch/$REF/setup-exegol.sh" | EXEGOL_LAUNCH_REF="$REF" bash
```

Les scripts peuvent également être téléchargés, examinés puis exécutés localement.

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
Les alias et fonctions de shell ne sont pas des exécutables : les déclarer explicitement dans la configuration.

## Applications personnalisées

Créer `~/.config/exegol-launch/apps.json` (ou `$XDG_CONFIG_HOME/exegol-launch/apps.json`) :

```json
[
  {"name": "Burp personnalisé", "argv": ["burpsuite"], "category": "Web"},
  {"name": "Shell de travail", "argv": ["bash"], "terminal": true}
]
```

`argv` est une liste d’arguments sans évaluation implicite par un shell. Utiliser des
chemins absolus : `~` et `$VAR` ne sont pas développés. Autres champs : `description`,
`category` et `cwd`. Exemple complet : [apps.example.json](apps.example.json).
Pour une commande nécessitant réellement un shell, utiliser explicitement
`["bash", "-lc", "commande"]` avec sa configuration appropriée.

Les outils CLI demandent un terminal présent **dans le conteneur**. Au besoin :

```bash
export EXEGOL_LAUNCH_TERMINAL='xterm -e'
```

Cette variable fournit le terminal et les options avant les arguments de l’outil.
Sans réglage : x-terminal-emulator, xterm, kitty puis alacritty sont recherchés.

## Affichage graphique et diagnostic

Aucun DISPLAY n’est inventé et aucune permission graphique n’est modifiée :
DISPLAY, XAUTHORITY, WAYLAND_DISPLAY et les autres variables sont hérités du terminal.
Tkinter sous Linux nécessite généralement X11/XWayland et un DISPLAY accessible.
Si la fenêtre part dans le VNC, vérifier l’environnement du terminal utilisé ; le projet
ne remplace pas le partage graphique Exegol.

Les outils sont détachés du launcher : fermer le menu ne les ferme pas. Arrêter le
conteneur ou son serveur graphique peut en revanche les arrêter.

Journaux : `~/.local/state/exegol-launch/` ou `$XDG_STATE_HOME/exegol-launch/`.
`launcher.log` concerne le menu ; les autres fichiers correspondent aux applications.
« Commande démarrée » confirme la création du processus, pas l’ouverture effective
d’une fenêtre. Consulter le journal si un outil se ferme immédiatement. Les logs sont
cumulés ; ils peuvent être supprimés quand les outils concernés sont arrêtés.

## Tests

```bash
python3 -m unittest discover -s tests -v
bash -n install.sh setup-exegol.sh
```

Les tests couvrent la découverte XDG, les arguments des commandes, le lancement
indépendant et les installateurs dans des dossiers temporaires. Ils ne nécessitent
pas de serveur graphique et ne sont pas installés dans les conteneurs.
La compatibilité graphique dépend de l’image Exegol et du partage d’affichage de l’hôte ;
ces tests ne remplacent pas une validation dans un conteneur avec un affichage réel.
Le mécanisme du hook est documenté dans le [modèle officiel Exegol](https://github.com/ThePorgs/Exegol-images/blob/main/sources/assets/exegol/skel/load_user_setup.sh).

## Désinstallation

Dans le conteneur, supprimer uniquement le wrapper géré `/usr/local/bin/launch` et
`/opt/exegol-launch` (ou les chemins utilisateur si installé sans root).
Sur l’hôte, supprimer le bloc `# BEGIN Exegol-launch` à `# END Exegol-launch` dans
`my-resources/setup/load_user_setup.sh` pour désactiver l’installation future.
Les payloads `.exegol-launch.*` de ce dossier peuvent ensuite être supprimés si aucun
hook ne les référence. Conserver les sauvegardes nécessaires. Les préférences utilisateur
et dépendances Python/Tkinter ne sont pas supprimées automatiquement.

## Contribuer

Les signalements de bugs et propositions d’amélioration sont bienvenus via les
[issues](https://github.com/Gvte-Kali/Exegol-launch/issues) et les pull requests.
Pour un bug, préciser la version du projet, l’image Exegol, la version de Python,
le mode d’affichage (X11, XWayland ou VNC) et les messages d’erreur utiles.
Supprimer les données sensibles des journaux avant de les partager.

Le dossier `tests/` fait partie des sources de développement : il vérifie les
comportements importants avant publication et alimente GitHub Actions. Son contenu
n’est nécessaire ni à l’installation ni à l’utilisation du launcher.

### Organisation du projet

| Fichier ou dossier | Rôle |
|---|---|
| `exegol_launch/cli.py` | Arguments CLI, vérification de l’affichage et démarrage détaché |
| `exegol_launch/core.py` | Découverte des applications, configuration et processus |
| `exegol_launch/gui.py` | Interface Tkinter, recherche et favoris |
| `exegol_launch/__main__.py` | Entrée de `python3 -m exegol_launch` |
| `install.sh` | Installation ou mise à jour dans un conteneur |
| `setup-exegol.sh` | Enregistrement sur l’hôte pour les futurs conteneurs |
| `apps.example.json` | Exemple de configuration utilisateur |
| `tests/` | Vérifications automatisées sans interface graphique |
| `.github/workflows/tests.yml` | Exécution des tests sur GitHub Actions |

Exécuter les tests et la vérification de syntaxe ci-dessus avant une pull request.
Les commentaires du code expliquent les choix de gestion des processus, de priorité
XDG et de préservation des installations existantes.

## Améliorations possibles

- Icônes des applications et sélection par catégorie.
- Éditeur de commandes intégré à la GUI.
- Détection des fermetures immédiates avec accès direct au journal.
- Mode instance unique et commande de diagnostic de l’affichage.
