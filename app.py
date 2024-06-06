import sqlite3
import bcrypt
from flask import Flask, redirect, render_template, request, session, url_for
import os
import math

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
        mot_de_passe TEXT,
        video_url TEXT
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
    CREATE TABLE IF NOT EXISTS ReussiteNiveau (
        joueur_id INTEGER,
        niveau_id INTEGER,
        video_url TEXT,
        createurs TEXT,
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

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS SubmitRecord (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        joueur_nom TEXT NOT NULL,
        niveau_nom TEXT NOT NULL,
        createur TEXT NOT NULL,
        video_url TEXT NOT NULL,
        status TEXT DEFAULT 'pending'
    )
    ''')
    connection.commit()
    connection.close()

init_db()



#pages
@app.route('/liste')
def liste():
    active_page = 'home'
    connection = sqlite3.connect('DataBase.db')
    cursor = connection.cursor()
    cursor.execute('SELECT id, nom, createurs, classement, video_url FROM Niveau ORDER BY classement')
    niveaux = cursor.fetchall()
    connection.close()
    return render_template('home.html', active_page=active_page, niveaux=niveaux)

@app.route('/liste/<int:classement>')
def niveau(classement):
    active_page = 'home'
    connection = sqlite3.connect('DataBase.db')
    cursor = connection.cursor()
    
    cursor.execute('SELECT nom, createurs, classement, video_url FROM Niveau WHERE classement = ?', (classement,))
    niveau = cursor.fetchone()

    cursor.execute('SELECT id, nom, createurs, classement, video_url FROM Niveau ORDER BY classement')
    classementniveaux = cursor.fetchall()

    cursor.execute('''
        SELECT Joueur.nom, ReussiteNiveau.video_url 
        FROM ReussiteNiveau
        JOIN Joueur ON ReussiteNiveau.joueur_id = Joueur.id
        WHERE ReussiteNiveau.niveau_id = (SELECT id FROM Niveau WHERE classement = ?)
        ORDER BY ReussiteNiveau.rowid
    ''', (classement,))
    victoires = cursor.fetchall()

    connection.close()

    return render_template('level.html', niveau=niveau, victoires=victoires, classementniveaux=classementniveaux, active_page=active_page)

@app.route('/classement')
def classement():
    active_page = 'classement'
    return render_template('classement.html', active_page=active_page)

@app.route('/information')
def information():
    active_page = 'information'
    return render_template('information.html', active_page=active_page)

@app.errorhandler(404)
def not_found_error(error):
    return redirect('/error404')

@app.route('/error404')
def error404():
    return render_template('404.html')

@app.route('/')
def noroute():
    return redirect('/liste')

@app.route('/home')
def home():
    return redirect('/liste')

#SubmitRecord
@app.route('/submit_record', methods=['GET', 'POST'])
def submit_record():
    active_page = 'envoyerunevideo'
    if request.method == 'POST':
        joueur_nom = request.form['joueur_nom']
        niveau_nom = request.form['niveau_nom']
        createur = request.form['createur']
        video_url = request.form['video_url']

        connection = sqlite3.connect('DataBase.db')
        cursor = connection.cursor()
        cursor.execute('''
        INSERT INTO SubmitRecord (joueur_nom, niveau_nom, createur, video_url) 
        VALUES (?, ?, ?, ?)
        ''', (joueur_nom, niveau_nom, createur, video_url))
        connection.commit()
        connection.close()
        
        return render_template('submit_record_correctement_envoyer.html')

    return render_template('submit_record.html', active_page=active_page)



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
        
        cursor.execute('SELECT * FROM SubmitRecord WHERE status = "pending"')
        submissions = cursor.fetchall()
        
        connection.close()
        return render_template('admin.html', niveaux=niveaux, submissions=submissions)
    else:
        return redirect(url_for('connexion'))

@app.route('/ajouter_niveau', methods=['POST'])
def ajouter_niveau():
    id_niveau = int(request.form['id_niveau'])
    nom_niveau = request.form['nom_niveau']
    createurs = request.form['createurs']
    classement = int(request.form['classement'])
    mot_de_passe = request.form['mot_de_passe']
    video_url = request.form['video_url']

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
        INSERT INTO Niveau (id_niveau, nom, createurs, points, classement, mot_de_passe, video_url) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (id_niveau, nom_niveau, createurs, points, classement, mot_de_passe, video_url))

        connection.commit()
        connection.close()
        mettre_a_jour_points()
        mettre_a_jour_points_utilisateurs()

        return f'Niveau {nom_niveau} ajouté avec succès !'
    
    except sqlite3.IntegrityError:
        return f'Erreur : Le niveau {nom_niveau} ou l\'ID {id_niveau} existe déjà.'

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

    cursor.execute('DELETE FROM ReussiteNiveau WHERE niveau_id = ?', (niveau_id,))
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

    cursor.execute('DELETE FROM ReussiteNiveau WHERE joueur_id = ? AND niveau_id = ?', (joueur_id, niveau_id))
    connection.commit()
    connection.close()
    mettre_a_jour_points_utilisateurs()
    mettre_a_jour_points()

    return f'Réussite du joueur {nom_joueur} pour le niveau {nom_niveau} supprimée avec succès !'


def calculer_points(classement, base=2):
    return max(1, int(5000 / math.log(classement + base, base)))

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
        INNER JOIN ReussiteNiveau ON Niveau.id = ReussiteNiveau.niveau_id 
        WHERE ReussiteNiveau.joueur_id = ?
        ''', (joueur_id,))
        total_points = cursor.fetchone()[0] or 0

        cursor.execute('UPDATE Joueur SET points = ? WHERE id = ?', (total_points, joueur_id))

    connection.commit()
    connection.close()


    
# Valider ou refuser un record soumis et pouvoir modifier le nom du joueur et du niveau en cas d'erreur
@app.route('/valider_record', methods=['POST'])
def valider_record():
    submission_id = request.form['submission_id']
    joueur_nom = request.form['joueur_nom']
    niveau_nom = request.form['niveau_nom']
    
    connection = sqlite3.connect('DataBase.db')
    cursor = connection.cursor()

    cursor.execute('SELECT createur, video_url FROM SubmitRecord WHERE id = ?', (submission_id,))
    submission = cursor.fetchone()
    
    if submission:
        createur, video_url = submission
        
        cursor.execute('SELECT id FROM Joueur WHERE nom = ?', (joueur_nom,))
        result = cursor.fetchone()
        if result is None:
            cursor.execute('INSERT INTO Joueur (nom) VALUES (?)', (joueur_nom,))
            connection.commit()
            cursor.execute('SELECT id FROM Joueur WHERE nom = ?', (joueur_nom,))
            result = cursor.fetchone()
        
        joueur_id = result[0]
        
        cursor.execute('SELECT id, points FROM Niveau WHERE nom = ?', (niveau_nom,))
        result = cursor.fetchone()
        if result is None:
            connection.close()
            return f'Erreur : Aucun niveau trouvé avec le nom {niveau_nom}'
        
        niveau_id, points = result
        
        cursor.execute('SELECT * FROM ReussiteNiveau WHERE joueur_id = ? AND niveau_id = ?', (joueur_id, niveau_id))
        result = cursor.fetchone()
        if result:
            connection.close()
            return f'Erreur : Le joueur {joueur_nom} a déjà une réussite sur ce niveau {niveau_nom}'
        
        cursor.execute('''
        INSERT INTO ReussiteNiveau (joueur_id, niveau_id, video_url, createurs) 
        VALUES (?, ?, ?, ?)
        ''', (joueur_id, niveau_id, video_url, createur))
        
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
        
        cursor.execute('UPDATE SubmitRecord SET status = "accepted", joueur_nom = ?, niveau_nom = ? WHERE id = ?', (joueur_nom, niveau_nom, submission_id))
        
        connection.commit()
        connection.close()
        mettre_a_jour_points_utilisateurs()
        mettre_a_jour_points()

    return redirect(url_for('admin'))

@app.route('/refuser_record', methods=['POST'])
def refuser_record():
    submission_id = request.form['submission_id']
    connection = sqlite3.connect('DataBase.db')
    cursor = connection.cursor()
    
    cursor.execute('UPDATE SubmitRecord SET status = "rejected" WHERE id = ?', (submission_id,))
    
    connection.commit()
    connection.close()

    return redirect(url_for('admin'))

if __name__ == '__main__':
    app.run(debug=True)
