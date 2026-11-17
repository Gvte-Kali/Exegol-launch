# Validation de la version 0.1.0

- 6 tests unitaires/intégration réussis (découverte XDG, arguments desktop, environnement hérité, survie du processus enfant).
- Installateur système/utilisateur, mises à jour, refus des collisions, hook idempotent et sauvegardes testés dans des dossiers temporaires.
- Installation isolée et commande `launch --version` vérifiées.
- Découverte réelle des applications vérifiée dans l’environnement de développement.
- Interface graphique non validée visuellement : aucun serveur X/DISPLAY disponible ici.
- Exegol et Hyprland ne sont pas présents dans cet environnement.

À vérifier dans ton conteneur :
1. Depuis le terminal où Burp fonctionne, lancer `launch` ; vérifier que le prompt revient.
2. Chercher Burp et le lancer ; vérifier que sa fenêtre apparaît sur Hyprland.
3. Fermer le launcher ; vérifier que Burp reste ouvert.
4. Relancer le launcher ; tester la recherche et la persistance d’un favori.
5. En cas d’échec, lancer `launch --foreground` et lire les journaux.
