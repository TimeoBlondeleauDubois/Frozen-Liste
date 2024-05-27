import sqlite3

connection = sqlite3.connect('DataBase.db')
cursor = connection.cursor()
connection.commit()
