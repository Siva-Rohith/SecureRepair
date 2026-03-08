import os
import re
from flask import Flask, render_template, request, redirect, session
from datetime import datetime
import sqlite3
from flask import jsonify
import secrets
import csv
from flask import Response
from werkzeug.security import check_password_hash
app = Flask(__name__)
from datetime import timedelta



app.config['SECRET_KEY'] = secrets.token_hex(16)
app.permanent_session_lifetime = timedelta(minutes=10)


ALLOWED_EXTENSIONS = {'png','jpg','jpeg'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.',1)[1].lower() in ALLOWED_EXTENSIONS


# Create database table
from werkzeug.security import generate_password_hash
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)


def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            mobile TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            profile_image TEXT DEFAULT 'default.png',
            created_at TEXT
        )
        """)
    
    # Create bookings table
    cursor.execute("""
     CREATE TABLE IF NOT EXISTS bookings (
        id TEXT PRIMARY KEY,
        user_id INTEGER,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        mobile TEXT,
        address TEXT,
        device TEXT NOT NULL,
        issue TEXT NOT NULL,
        preferred_date TEXT,
        time_slot TEXT,
        status TEXT DEFAULT 'Pending',
        created_at TEXT,
        completed_at TEXT,
        cancel_reason TEXT,
        cancelled_at TEXT
    )
    """)


    # Chat messages table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        booking_id TEXT,
        sender TEXT,
        message TEXT,
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

init_db()







@app.route('/')
def home():
    return render_template('index.html')



#BOOKING ROUTE
@app.route('/book', methods=['POST'])
def book():

    name = request.form['name'].strip()
    email = request.form['email'].strip().lower()
    mobile = request.form['mobile'].strip()
    address = request.form['address']
    device = request.form['device']
    issue = request.form['issue']
    date = request.form['date']
    time_slot = request.form['time_slot']

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("SELECT id FROM bookings ORDER BY created_at DESC LIMIT 1")
    last = cursor.fetchone()

    if last:
        last_number = int(last[0].split("-")[1])
        new_id = f"SR-{last_number + 1}"
    else:
        new_id = "SR-1000"

    user_id = session.get("user_id")

    # If not logged in, try linking by email
    if not user_id:
        cursor.execute("SELECT id FROM users WHERE LOWER(email) = ?", (email,))
        existing_user = cursor.fetchone()
        if existing_user:
            user_id = existing_user[0]

    cursor.execute("""
        INSERT INTO bookings
        (id, user_id, name, email, mobile, address, device, issue, preferred_date, time_slot, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (new_id, user_id, name, email, mobile, address, device, issue, date, time_slot, 'Pending', now))

    conn.commit()
    conn.close()

    return jsonify({"success": True})



@app.route('/cancel-booking/<id>', methods=['POST'])
def cancel_booking(id):

    if not session.get('user_id'):
        return jsonify({"success": False})

    data = request.get_json()
    reason = data.get("reason")

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT user_id, status FROM bookings WHERE id = ?
    """, (id,))
    booking = cursor.fetchone()

    if not booking:
        conn.close()
        return jsonify({"success": False})

    if booking[0] != session['user_id']:
        conn.close()
        return jsonify({"success": False})

    if booking[1] == "Completed":
        conn.close()
        return jsonify({"success": False})

    cancel_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        UPDATE bookings
        SET status = 'Cancelled',
            cancel_reason = ?,
            cancelled_at = ?
        WHERE id = ?
    """, (reason, cancel_time, id))

    conn.commit()
    conn.close()

    return jsonify({"success": True})











@app.route('/signup', methods=['GET', 'POST'])
def signup():

    if session.get('user_id'):
        return redirect('/')

    if request.method == 'POST':

        name = request.form['name']
        email = request.form['email']
        mobile = request.form['mobile']
        password = request.form['password']
        

        email = email.strip().lower()
        mobile = mobile.strip()

        # Email validation
        email_pattern = r'^[\w\.-]+@[\w\.-]+\.\w{2,}$'
        if not re.match(email_pattern, email):
            return "Invalid Email Format"

        # Mobile validation (10 digits only)
        if not mobile.isdigit() or len(mobile) != 10:
            return "Mobile must be exactly 10 digits"
        password_hash = generate_password_hash(password)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        # Check if user already exists
        cursor.execute("""
            SELECT id FROM users
            WHERE email = ? OR mobile = ?
        """, (email, mobile))

        existing = cursor.fetchone()

        if existing:
            conn.close()
            return "User already exists with this Email or Mobile"

        # Insert new user
        cursor.execute("""
            INSERT INTO users (name, email, mobile, password_hash, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (name, email, mobile, password_hash, datetime.now()))

        user_id = cursor.lastrowid

        
        cursor.execute("""
            UPDATE bookings
            SET user_id = ?
            WHERE email = ?
            AND user_id IS NULL
        """, (user_id, email))

        conn.commit()
        conn.close()

       
        session['user_id'] = user_id
        session['user_name'] = name
        session['user_email'] = email
        session['user_mobile'] = mobile

        return redirect('/')

    return render_template('signup.html')







@app.route('/user-login', methods=['GET', 'POST'])
def user_login():

    if session.get('user_id'):
        return redirect('/')

    if request.method == 'POST':

        identifier = request.form['identifier'].strip()
        password = request.form['password'].strip()

# If fields are empty
        if not identifier or not password:
            return render_template("user_login.html", error="Invalid username or password")
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute("""
            SELECT id, name, email, mobile, password_hash, profile_image
            FROM users
            WHERE email = ? OR mobile = ?
        """, (identifier, identifier))

        user = cursor.fetchone()
        conn.close()

        if user:
            user_id = user[0]
            user_name = user[1]
            user_email = user[2]
            user_mobile = user[3]
            password_hash = user[4]
            session['profile_image'] = user[5]
            if check_password_hash(password_hash, password):
                session['user_id'] = user_id
                session['user_name'] = user_name
                session['user_email'] = user_email
                session['user_mobile'] = user_mobile
                return redirect('/')

            return render_template("user_login.html", error="Invalid email or password")

    return render_template("user_login.html", error="Invalid email or password")






@app.route('/user-dashboard')
def user_dashboard():
    if not session.get('user_id'):
        return redirect('/user-login')

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM bookings
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (session['user_id'],))

    rows = cursor.fetchall()
    bookings = [dict(row) for row in rows]
    conn.close()
    return render_template('user_dashboard.html', bookings=bookings)




@app.route('/user-chats')
def user_chats():

    if not session.get('user_id'):
        return redirect('/user-login')

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, device, issue, status
        FROM bookings
        WHERE user_id = ?
        ORDER BY created_at DESC
    """, (session['user_id'],))

    rows = cursor.fetchall()
    bookings = [dict(row) for row in rows]

    conn.close()

    return render_template('user_chats.html', bookings=bookings)




@app.route('/chat/<booking_id>')
def chat_page(booking_id):

    if not session.get('user_id'):
        return redirect('/user-login')

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, device, issue
        FROM bookings
        WHERE id = ? AND user_id = ?
    """, (booking_id, session['user_id']))

    booking = cursor.fetchone()

    conn.close()

    return render_template("chat_page.html", booking=dict(booking))




@app.route('/update-profile', methods=['POST'])
def update_profile():

    if not session.get('user_id'):
        return redirect('/user-login')

    name = request.form['name'].strip()
    email = request.form['email'].strip().lower()
    mobile = request.form['mobile'].strip()

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Check duplicate email/mobile
    cursor.execute("""
        SELECT id FROM users
        WHERE (email = ? OR mobile = ?)
        AND id != ?
    """, (email, mobile, session['user_id']))

    if cursor.fetchone():
        conn.close()
        return "Email or Mobile already used"

    # Update basic fields
    cursor.execute("""
        UPDATE users
        SET name = ?, email = ?, mobile = ?
        WHERE id = ?
    """, (name, email, mobile, session['user_id']))

    # Handle image upload
    file = request.files.get('profile_image')
#Checking
    if file and file.filename != "":

        if allowed_file(file.filename):

            filename = f"user_{session['user_id']}_{secure_filename(file.filename)}"

            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            session['profile_image'] = filename

        else:
            session["upload_error"] = "Invalid file type. Please upload PNG, JPG or JPEG."
            return redirect("/user-dashboard")
        cursor.execute("""
            UPDATE users
            SET profile_image = ?
            WHERE id = ?
        """, (filename, session['user_id']))

        session['profile_image'] = filename

    conn.commit()
    conn.close()

    # Update session
    session['user_name'] = name
    session['user_email'] = email
    session['user_mobile'] = mobile

    return redirect('/user-dashboard')








@app.route('/logout-user')
def logout_user():
    session.clear()   
    return redirect('/')





@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect('/loginhead')

    page = request.args.get('page', 1, type=int)
    sort = request.args.get('sort', 'id_desc')
    status_filter = request.args.get('status', 'all')

    per_page = 5
    offset = (page - 1) * per_page

    # Sorting logic
    if sort == "id_asc":
        order_by = "id ASC"

    elif sort == "created_at_desc":
        order_by = "created_at DESC"

    elif sort == "created_at_asc":
        order_by = "created_at ASC"

    elif sort == "preferred_date_desc":
        order_by = "preferred_date DESC"

    elif sort == "preferred_date_asc":
        order_by = "preferred_date ASC"

    elif sort == "time_slot_asc":
        order_by = "time_slot ASC"

    elif sort == "time_slot_desc":
        order_by = "time_slot DESC"

    else:
        order_by = "id DESC"

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Base query
    base_query = "FROM bookings"
    params = []

    if status_filter != 'all':
        base_query += " WHERE status = ?"
        params.append(status_filter)

    # Count total records (after filter)
    cursor.execute(f"SELECT COUNT(*) {base_query}", params)
    total_records = cursor.fetchone()[0]

    # Fetch paginated records
    query = f"SELECT * {base_query} ORDER BY {order_by} LIMIT ? OFFSET ?"
    cursor.execute(query, params + [per_page, offset])
    bookings = cursor.fetchall()

    # Global counts (for dashboard cards)
    cursor.execute("SELECT COUNT(*) FROM bookings WHERE status='Pending'")
    pending = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM bookings WHERE status='Completed'")
    completed = cursor.fetchone()[0]

    conn.close()

    total_pages = (total_records + per_page - 1) // per_page

    return render_template(
        "admin.html",
        bookings=bookings,
        pending=pending,
        completed=completed,
        total=pending + completed,
        page=page,
        total_pages=total_pages,
        sort=sort,  
        current_status=status_filter
    )


@app.route('/admin-chat/<booking_id>')
def admin_chat(booking_id):

    if not session.get('admin'):
        return redirect('/loginhead')

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, device, issue
        FROM bookings
        WHERE id = ?
    """,(booking_id,))

    booking = cursor.fetchone()

    conn.close()

    return render_template("admin_chat.html", booking=dict(booking))




@app.route('/export')
def export_csv():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bookings")
    data = cursor.fetchall()
    conn.close()
    
    def generate():
        yield 'SR-ID,Name,Email,Mobile,Address,Device,Issue,Preferred Date,Time Slot,Status,Created At\n'

        for row in data:
           yield f"{row[0]},{row[2]},{row[3]},{row[4]},{row[5]},{row[6]},{row[7]},{row[8]},{row[9]},{row[10]},{row[11]}\n"

    return Response(generate(),
                    mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=bookings.csv"})







@app.route('/delete/<id>')
def delete(id):
    if not session.get('admin'):
        return redirect('/loginhead')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bookings WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    return redirect('/admin')



@app.route('/toggle/<id>', methods=['POST'])
def toggle_status(id):

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM bookings WHERE id = ?", (id,))
    result = cursor.fetchone()

    if not result:
        conn.close()
        return jsonify({"success": False})

    current_status = result[0]

    # Do not allow toggle for cancelled bookings
    if current_status == "Cancelled":
        conn.close()
        return jsonify({"success": False})

    # Normal toggle
    new_status = "Completed" if current_status == "Pending" else "Pending"

    cursor.execute(
        "UPDATE bookings SET status = ? WHERE id = ?",
        (new_status, id)
    )

    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "new_status": new_status
    })



# For Login


@app.route('/loginhead', methods=['GET', 'POST'])
def login():

    stored_password = "scrypt:32768:8:1$I5W3l0w0R8bCEaMR$622d98f696f09e62aae8be623f0fa1f8cf43d3e5448ae890e6df9a632ac0c719840cbe7d1c35b7a561fa1486f3ed5f7fca1b3d34089e42d2462a2a891b5b8345"


    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == "admin" and check_password_hash(stored_password, password):
            session.permanent = True
            session['admin'] = True
            return redirect('/admin')
        else:
            return render_template("loginhead.html", error="Invalid username or password")
    return render_template('loginhead.html')





#For Logout

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/loginhead')


@app.route('/send-message', methods=['POST'])
def send_message():

    booking_id = request.form['booking_id']
    message = request.form['message']

    # Detect sender correctly
    if session.get('admin'):
        sender = "admin"
    elif session.get('user_id'):
        sender = "user"
    else:
        return jsonify({"success": False})

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO messages (booking_id, sender, message, created_at)
        VALUES (?, ?, ?, ?)
    """, (booking_id, sender, message, now))

    conn.commit()
    conn.close()

    return jsonify({"success": True})


@app.route('/get-messages/<booking_id>')
def get_messages(booking_id):

    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        SELECT * FROM messages
        WHERE booking_id = ?
        ORDER BY created_at ASC
    """, (booking_id,))

    rows = cursor.fetchall()
    messages = [dict(row) for row in rows]

    conn.close()

    return jsonify(messages)


typing_status = {}

@app.route('/typing', methods=['POST'])
def typing():
    booking_id = request.form['booking_id']
    typing_status[booking_id] = True
    return jsonify({"success": True})


@app.route('/check-typing/<booking_id>')
def check_typing(booking_id):

    status = typing_status.get(booking_id, False)

    typing_status[booking_id] = False

    return jsonify({"typing": status})

if __name__ == '__main__':
    app.run(debug=True)

