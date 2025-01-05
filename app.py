import cx_Oracle  
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'secret_key'

def get_db_connection():
    try:
        username = 'bd101'
        password = 'bd101'
        host = 'bd-dc.cs.tuiasi.ro'
        port = '1539'
        service_name = 'orcl'

        connection = cx_Oracle.connect(username, password,'bd-dc.cs.tuiasi.ro:1539/orcl')
        print("Connection successful")
        return connection
    except cx_Oracle.DatabaseError as e:
        print(f"Error while connecting to the database: {e}")
        return None

@app.route('/')
def index():
    #connect to database
    connection = get_db_connection()
    if connection is None:
        return "Failed to connect to the database!", 500
    cursor = connection.cursor()

    cursor.close()
    connection.close()

    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    error_message = None
    if request.method == 'POST':

        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        date_of_birth = request.form.get('date_of_birth')
        bio = request.form.get('bio')

        if not username or not email or not password:
            error_message = "Username, Email, and Password are required."
            return render_template('register.html', error_message=error_message)

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
        """
                INSERT INTO users (username, email, password)
                VALUES (:username, :email, :password)
                """, {
                    'username': username,
                    'email': email,
                    'password': password
                }
        )

            cursor.execute("""
                   SELECT user_id
                   FROM users
                   WHERE username = :username AND email = :email
               """, {'username': username, 'email': email})


            user_id = cursor.fetchone()[0]

            cursor.execute("""
                        INSERT INTO profiles (users_user_id, date_of_birth, bio)
                        VALUES (:user_id, TO_DATE(:date_of_birth, 'YYYY-MM-DD'), :bio)
                        """, {
            'user_id': user_id,
            'date_of_birth': date_of_birth if date_of_birth else None,
            'bio': bio if bio else None
            })

            connection.commit()

        except cx_Oracle.DatabaseError as e:
            connection.rollback()

            error_code = e.args[0].code

            if error_code == 1400:
                error_message = "Please fill in all mandatory fields."
            elif error_code == 1:
                error_message = "Username or Email already exists. Please choose another one."
            else:
                error_message = "An unexpected error occurred while registering your account."

            cursor.close()
            connection.close()

            return render_template('register.html', error_message=error_message)

        cursor.close()
        connection.close()

        return redirect('/register')  # You can customize this as needed


    return render_template('register.html', error_message=error_message)

@app.route('/login', methods=['GET', 'POST'])
def login():
    error_message = None

    if request.method == 'POST':

        username = request.form['username']
        password = request.form['password']

        connection = get_db_connection()
        cursor = connection.cursor()

        cursor.execute("""
            SELECT user_id, username, password
            FROM users
            WHERE username = :username
        """, {'username': username})

        user = cursor.fetchone()  # Fetch user data

        if user and user[2] == password:
            session['user_id'] = user[0]
            print(f"User {user[1]} logged in with user_id: {user[0]}")

            print("Successfully logged in")
            return redirect(url_for('select_genre'))
        else:
            error_message = 'Invalid username or password'
            print('Invalid username or password')

        cursor.close()
        connection.close()

    return render_template('login.html', error_message=error_message)

@app.route('/logout')
def logout():
    # Clear the session
    session.clear()
    return redirect(url_for('index'))

@app.route('/select_genre', methods=['GET', 'POST'])
def select_genre():

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT genre_id, genre_name FROM genres")
    genres = cursor.fetchall()

    if request.method == 'POST':
        genre_id = request.form['genre_id']  # Get the selected genre_id
        cursor.execute("SELECT genre_name FROM genres WHERE genre_id = :genre_id", {'genre_id': genre_id})
        genre_name = cursor.fetchone()[0]

        cursor.execute("""
            SELECT movie_id, title, avg_rating 
            FROM movies 
            WHERE genres_genre_id = :genre_id
        """, {'genre_id': genre_id})


        movies = cursor.fetchall()

        cursor.close()
        connection.close()

        return render_template('movie_list.html', movies=movies)

    cursor.close()
    connection.close()

    return render_template('recommend_by_genre.html', genres=genres)

@app.route('/rate_movie/<int:movie_id>', methods=['GET', 'POST'])
def rate_movie(movie_id):
    user_id = session.get('user_id')

    if not user_id:
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("""
            SELECT movie_id, title 
            FROM movies 
            WHERE movie_id = :movie_id
        """, {'movie_id': movie_id})

    movie = cursor.fetchone()

    print(movie)

    if request.method == 'POST':
        rating = request.form['rating']
        review = request.form['review']

        try:
            cursor.execute("""
                    INSERT INTO ratings (users_user_id, movies_movie_id, review, rating, CREATED_AT)
                    VALUES (:user_id, :movie_id, :review, :rating, SYSDATE)
                """, {'user_id': user_id, 'movie_id': movie_id, 'rating': rating, 'review': review})

            cursor.execute("""
                    UPDATE movies
                    SET avg_rating = (
                        SELECT AVG(rating) 
                        FROM ratings 
                        WHERE movies_movie_id = :movie_id
                    )
                    WHERE movie_id = :movie_id
                """, {'movie_id': movie_id})

            connection.commit()

            return redirect(url_for('select_genre'))

        except Exception as e:

            connection.rollback()
            print(f"Error occurred: {e}")
            return "An error occurred while submitting your rating."

    cursor.close()
    connection.close()

    return render_template('rate_movie.html', movie=movie)


from flask import render_template, session, redirect, url_for


@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    connection = get_db_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT username, email FROM users WHERE user_id = :user_id", {'user_id': session['user_id']})
    user = cursor.fetchone()

    cursor.execute("SELECT bio, date_of_birth FROM profiles WHERE users_user_id = :user_id", {'user_id': session['user_id']})
    profile = cursor.fetchone()

    cursor.close()
    connection.close()

    if not user:
        return redirect(url_for('login'))

    return render_template('profile.html', user=user, profile=profile)



if __name__ == '__main__':
    app.run(debug=True)

