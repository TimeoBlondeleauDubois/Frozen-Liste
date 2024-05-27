from flask import Flask, render_template
import os

app = Flask(__name__)
app.secret_key = os.urandom(8192)

@app.route('/')
def index():
    return render_template('home.html')

if __name__ == '__main__':
    app.run(debug=True)
