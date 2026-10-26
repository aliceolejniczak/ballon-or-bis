# 🏆 Ballon d’Or Battle

Une application web pour organiser des pronostics du Ballon d’Or entre amis. Chaque participant prédit le Top 10, les pronostics sont verrouillés avant la révélation du classement officiel, puis les scores sont calculés.

## Comment jouer

### 1. Créer son profil
- Ouvrir l’application.
- Cliquer sur **Créer mon profil**.
- Choisir un pseudo unique et un code personnel d’au moins 6 caractères.
- Aucun e-mail n’est demandé.
- Conserver son pseudo et son code pour se reconnecter plus tard.

### 2. Créer ou rejoindre une partie
- **Organisateur :** créer une partie depuis l’onglet correspondant. L’organisateur devient l’administrateur.
- Partager le lien d’invitation ou le code de la partie.
- **Participants :** ouvrir le lien, créer un profil ou se connecter, puis cliquer sur **Rejoindre cette partie**.
- Il est nécessaire de rejoindre la partie avant le verrouillage des pronostics.

### 3. Enregistrer son Top 10
- Ouvrir la partie et aller dans **Mes pronostics**.
- Choisir 10 joueurs distincts, classés de la 1re à la 10e place.
- Cliquer sur **Enregistrer mon Top 10**.
- Les choix peuvent être modifiés tant que l’administrateur n’a pas verrouillé les pronostics.

### 4. Verrouillage et résultats
Le déroulement se fait dans cet ordre :

1. **Verrouillage :** l’administrateur verrouille les pronostics de tous les joueurs. Ils ne peuvent alors plus être modifiés.
2. **Classement officiel :** après le verrouillage, l’administrateur saisit le classement officiel et le révèle à tous les participants.
3. **Clôture :** l’administrateur clôture la partie pour afficher les scores finaux et le classement des participants.

Les scores restent masqués jusqu’à la clôture.

## Barème des points

| Place officielle | Points de base |
|---:|---:|
| 1re | 20 |
| 2e | 15 |
| 3e | 12 |
| 4e | 10 |
| 5e | 8 |
| 6e | 6 |
| 7e | 5 |
| 8e | 4 |
| 9e | 3 |
| 10e | 2 |

Pour un joueur présent dans le Top 10 officiel, on retire **3 points par place d’écart** entre la prédiction et le classement réel, avec un minimum de 0 point pour ce choix.

Un joueur pronostiqué qui ne figure pas dans le Top 10 officiel vaut **−2 points**.

Le score final correspond à la somme des points obtenus pour les dix pronostics.

## Retrouver une partie
Ouvrir l’application, se connecter avec le même pseudo et le même code personnel, puis retrouver la partie dans **Mes parties**.

## Technologies
- Python
- Streamlit
- Supabase

Les identifiants de connexion à Supabase doivent rester dans les secrets de Streamlit et ne jamais être publiés sur GitHub.
