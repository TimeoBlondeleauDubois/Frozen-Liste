import sqlite3
import bcrypt
from flask import Flask, redirect, render_template, request, session, url_for
import os

app = Flask(__name__)
app.secret_key = os.urandom(8192)



# Création de la base de données
def init_db():
    connection = sqlite3.connect('DataBase.db')
    cursor = connection.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Niveau (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        createurs TEXT NOT NULL,
        id_niveau INTEGER UNIQUE,
        points INTEGER NOT NULL,
        classement INTEGER,
        victoires INTEGER DEFAULT 0,
        mot_de_passe TEXT
    )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_niveau_nom ON Niveau(nom)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_niveau_classement ON Niveau(classement)')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Joueur (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT NOT NULL UNIQUE,
        points INTEGER DEFAULT 0
    )
    ''')

    cursor.execute('CREATE INDEX IF NOT EXISTS idx_joueur_nom ON Joueur(nom)')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS JoueurNiveau (
        joueur_id INTEGER,
        niveau_id INTEGER,
        video_url TEXT,
        FOREIGN KEY (joueur_id) REFERENCES Joueur(id),
        FOREIGN KEY (niveau_id) REFERENCES Niveau(id),
        PRIMARY KEY (joueur_id, niveau_id)
    )
    ''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS Utilisateur (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        password BLOB NOT NULL
    )
    ''')
    connection.commit()
    connection.close()

init_db()



#Home page
@app.route('/')
def index():
    return render_template('home.html')



#Accéder à la page Admin
@app.route('/creer_compte', methods=['GET', 'POST'])
def creer_compte():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        try:
            connection = sqlite3.connect('DataBase.db')
            cursor = connection.cursor()
            cursor.execute('INSERT INTO Utilisateur (username, password) VALUES (?, ?)', (username, hashed_password))
            connection.commit()
            connection.close()
            return 'Compte créé avec succès !'
        except sqlite3.IntegrityError:
            return 'Erreur : Nom d\'utilisateur déjà utilisé.'
    else:
        return render_template('creer_compte.html')

@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if not validate_user_input(username, password):
            return 'Nom d\'utilisateur et mot de passe requis', 400

        connection = sqlite3.connect('DataBase.db')
        cursor = connection.cursor()
        cursor.execute('SELECT password FROM Utilisateur WHERE username = ?', (username,))
        result = cursor.fetchone()
        connection.close()

        if result:
            hashed_password = result[0]
            if bcrypt.checkpw(password.encode('utf-8'), hashed_password):
                session['username'] = username
                return redirect(url_for('admin'))

        return 'Nom d\'utilisateur ou mot de passe incorrect.'
    else:
        return render_template('connexion.html')

def validate_user_input(username, password):
    return bool(username and password)



# Page d'administration : Ajouter un joueur, ajouter un niveau, modifier l'ordre des niveaux, ajouter une victoire à un joueur

@app.route('/admin')
def admin():
    if 'username' in session:
        connection = sqlite3.connect('DataBase.db')
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM Niveau ORDER BY classement')
        niveaux = cursor.fetchall()
        connection.close()
        return render_template('admin.html', niveaux=niveaux)
    else:
        return redirect(url_for('connexion'))

@app.route('/ajouter_joueur', methods=['POST'])
def ajouter_joueur():
    nom_joueur = request.form['nom_joueur']
    try:
        connection = sqlite3.connect('DataBase.db')
        cursor = connection.cursor()
        cursor.execute('INSERT INTO Joueur (nom) VALUES (?)', (nom_joueur,))
        connection.commit()
        connection.close()
        return f'Joueur {nom_joueur} ajouté avec succès !'
    except sqlite3.IntegrityError:
        return f'Erreur : Le joueur {nom_joueur} existe déjà.'

@app.route('/ajouter_niveau', methods=['POST'])
def ajouter_niveau():
    id_niveau = int(request.form['id_niveau'])
    nom_niveau = request.form['nom_niveau']
    createurs = request.form['createurs']
    classement = int(request.form['classement'])
    mot_de_passe = request.form['mot_de_passe']

    if classement <= 0:
        return f'Erreur : Le classement doit être un entier positif'

    try:
        connection = sqlite3.connect('DataBase.db')
        cursor = connection.cursor()

        cursor.execute('SELECT COUNT(*) FROM Niveau')
        total_niveaux = cursor.fetchone()[0]

        if classement > total_niveaux + 1:
            classement = total_niveaux + 1

        cursor.execute('UPDATE Niveau SET classement = classement + 1 WHERE classement >= ?', (classement,))

        points = calculer_points(classement)

        cursor.execute('''
        INSERT INTO Niveau (id_niveau, nom, createurs, points, classement, mot_de_passe) 
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (id_niveau, nom_niveau, createurs, points, classement, mot_de_passe))

        connection.commit()
        connection.close()
        mettre_a_jour_points()
        mettre_a_jour_points_utilisateurs()

        return f'Niveau {nom_niveau} ajouté avec succès !'
    
    except sqlite3.IntegrityError:
        return f'Erreur : Le niveau {nom_niveau} ou l\'ID {id_niveau} existe déjà.'

@app.route('/reussir_niveau', methods=['POST'])
def reussir_niveau():
    nom_joueur = request.form['nom_joueur']
    nom_niveau = request.form['nom_niveau']
    video_url = request.form['video_url']
    connection = sqlite3.connect('DataBase.db')
    cursor = connection.cursor()

    cursor.execute('SELECT id FROM Joueur WHERE nom = ?', (nom_joueur,))
    result = cursor.fetchone()
    if result is None:
        return f'Erreur : Aucun joueur trouvé avec le nom {nom_joueur}'
    
    joueur_id = result[0]

    cursor.execute('SELECT id, points FROM Niveau WHERE nom = ?', (nom_niveau,))
    result = cursor.fetchone()
    if result is None:
        return f'Erreur : Aucun niveau trouvé avec le nom {nom_niveau}'
    
    niveau_id, points = result

    cursor.execute('SELECT * FROM JoueurNiveau WHERE joueur_id = ? AND niveau_id = ?', (joueur_id, niveau_id))
    result = cursor.fetchone()
    if result:
        return f'Erreur : Le joueur {nom_joueur} a déjà réussi le niveau {nom_niveau}'
    
    cursor.execute('''
    INSERT INTO JoueurNiveau (joueur_id, niveau_id, video_url) 
    VALUES (?, ?, ?)
    ''', (joueur_id, niveau_id, video_url))

    cursor.execute('''
    UPDATE Niveau 
    SET victoires = victoires + 1 
    WHERE id = ?
    ''', (niveau_id,))

    cursor.execute('''
    UPDATE Joueur 
    SET points = points + ? 
    WHERE id = ?
    ''', (points, joueur_id))

    connection.commit()
    connection.close()
    mettre_a_jour_points_utilisateurs()

    print(f'Points ajoutés au joueur {nom_joueur}: {points}')

    return f'Joueur {nom_joueur} a réussi le niveau {nom_niveau} et a gagné {points} points avec la vidéo : {video_url}'

@app.route('/modifier_ordre_niveaux', methods=['POST'])
def modifier_ordre_niveaux():
    nom_niveau = request.form['nom_niveau']
    new_classement = int(request.form['new_classement'])

    if new_classement <= 0:
        return "Erreur : Le classement doit être un entier positif."

    try:
        connection = sqlite3.connect('DataBase.db')
        cursor = connection.cursor()

        cursor.execute('SELECT id, classement FROM Niveau WHERE nom = ?', (nom_niveau,))
        result = cursor.fetchone()
        if result is None:
            return f'Erreur : Aucun niveau trouvé avec le nom {nom_niveau}'

        niveau_id, old_classement = result

        cursor.execute('SELECT COUNT(*) FROM Niveau')
        total_niveaux = cursor.fetchone()[0]

        if new_classement > total_niveaux:
            new_classement = total_niveaux

        if new_classement != old_classement:
            if new_classement < old_classement:
                cursor.execute('UPDATE Niveau SET classement = classement + 1 WHERE classement >= ? AND classement < ?', (new_classement, old_classement))
            else:
                cursor.execute('UPDATE Niveau SET classement = classement - 1 WHERE classement <= ? AND classement > ?', (new_classement, old_classement))

            cursor.execute('UPDATE Niveau SET classement = ? WHERE id = ?', (new_classement, niveau_id))

        connection.commit()
        mettre_a_jour_points()
        connection.close()
        mettre_a_jour_points_utilisateurs()

        return redirect(url_for('admin'))
    except sqlite3.Error as e:
        return f"Erreur : {str(e)}"
    
@app.route('/supprimer_niveau', methods=['POST'])
def supprimer_niveau():
    nom_niveau = request.form['nom_niveau']
    connection = sqlite3.connect('DataBase.db')
    cursor = connection.cursor()
    
    cursor.execute('SELECT id, classement FROM Niveau WHERE nom = ?', (nom_niveau,))
    result = cursor.fetchone()
    if result is None:
        return f'Erreur : Aucun niveau trouvé avec le nom {nom_niveau}'
    
    niveau_id, classement_supprime = result

    cursor.execute('DELETE FROM JoueurNiveau WHERE niveau_id = ?', (niveau_id,))
    cursor.execute('DELETE FROM Niveau WHERE id = ?', (niveau_id,))
    
    cursor.execute('UPDATE Niveau SET classement = classement - 1 WHERE classement > ?', (classement_supprime,))
    
    connection.commit()
    connection.close()
    
    mettre_a_jour_points()
    mettre_a_jour_points_utilisateurs()

    return f'Niveau {nom_niveau} supprimé avec succès !'


@app.route('/supprimer_reussite', methods=['POST'])
def supprimer_reussite():
    nom_joueur = request.form['nom_joueur']
    nom_niveau = request.form['nom_niveau']
    connection = sqlite3.connect('DataBase.db')
    cursor = connection.cursor()

    cursor.execute('SELECT id FROM Joueur WHERE nom = ?', (nom_joueur,))
    result = cursor.fetchone()
    if result is None:
        return f'Erreur : Aucun joueur trouvé avec le nom {nom_joueur}'
    
    joueur_id = result[0]

    cursor.execute('SELECT id FROM Niveau WHERE nom = ?', (nom_niveau,))
    result = cursor.fetchone()
    if result is None:
        return f'Erreur : Aucun niveau trouvé avec le nom {nom_niveau}'
    
    niveau_id = result[0]

    cursor.execute('DELETE FROM JoueurNiveau WHERE joueur_id = ? AND niveau_id = ?', (joueur_id, niveau_id))
    connection.commit()
    connection.close()
    mettre_a_jour_points_utilisateurs()
    mettre_a_jour_points()

    return f'Réussite du joueur {nom_joueur} pour le niveau {nom_niveau} supprimée avec succès !'


def calculer_points(classement):
    return int(5000 / classement)

def mettre_a_jour_points():
    connection = sqlite3.connect('DataBase.db')
    cursor = connection.cursor()

    cursor.execute('SELECT id, classement FROM Niveau')
    niveaux = cursor.fetchall()

    for niveau in niveaux:
        niveau_id, classement = niveau
        points = calculer_points(classement)
        cursor.execute('UPDATE Niveau SET points = ? WHERE id = ?', (points, niveau_id))

    connection.commit()
    connection.close()

mettre_a_jour_points()

def mettre_a_jour_points_utilisateurs():
    connection = sqlite3.connect('DataBase.db')
    cursor = connection.cursor()

    cursor.execute('SELECT id FROM Joueur')
    joueurs = cursor.fetchall()

    for joueur_id, in joueurs:
        cursor.execute('''
        SELECT SUM(points) FROM Niveau 
        INNER JOIN JoueurNiveau ON Niveau.id = JoueurNiveau.niveau_id 
        WHERE JoueurNiveau.joueur_id = ?
        ''', (joueur_id,))
        total_points = cursor.fetchone()[0]

        cursor.execute('UPDATE Joueur SET points = ? WHERE id = ?', (total_points, joueur_id))

    connection.commit()
    connection.close()

if __name__ == '__main__':
    app.run(debug=True)
