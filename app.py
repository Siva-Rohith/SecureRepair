import os
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





# Create database table
from werkzeug.security import generate_password_hash

def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    # Create bookings table
    cursor.execute("""
    
    CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        mobile TEXT,
        address TEXT,
        device TEXT NOT NULL,
        issue TEXT NOT NULL,
        preferred_date TEXT,
        time_slot TEXT,
        status TEXT DEFAULT 'Pending',
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

    name = request.form['name']
    mobile = request.form['mobile']
    address = request.form['address']
    device = request.form['device']
    issue = request.form['issue']
    date = request.form['date']
    time_slot = request.form['time_slot']

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO bookings
        (name, mobile, address, device, issue, preferred_date, time_slot, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, mobile, address, device, issue, date, time_slot, 'Pending', now))

    conn.commit()
    conn.close()

    return jsonify({"success": True})








@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect('/login')

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






@app.route('/export')
def export_csv():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM bookings")
    data = cursor.fetchall()
    conn.close()
    
    def generate():
        yield 'ID,Name,Device,Issue,Preferred Date,Time Slot,Status,Created At\n'

        for row in data:
            yield f"{row[0]},{row[1]},{row[2]},{row[3]},{row[4]},{row[5]},{row[6]},{row[7]}\n"

    return Response(generate(),
                    mimetype='text/csv',
                    headers={"Content-Disposition": "attachment;filename=bookings.csv"})







@app.route('/delete/<int:id>')
def delete(id):
    if not session.get('admin'):
        return redirect('/login')

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM bookings WHERE id = ?", (id,))
    conn.commit()
    conn.close()

    return redirect('/admin')




@app.route('/toggle/<int:id>', methods=['POST'])
def toggle_status(id):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT status FROM bookings WHERE id = ?", (id,))
    result = cursor.fetchone()

    if not result:
        conn.close()
        return jsonify({"success": False})

    current_status = result[0]
    new_status = 'Completed' if current_status == 'Pending' else 'Pending'

    cursor.execute("UPDATE bookings SET status = ? WHERE id = ?", (new_status, id))
    conn.commit()
    conn.close()

    return jsonify({
        "success": True,
        "new_status": new_status
    })




# For Login


@app.route('/login', methods=['GET', 'POST'])
def login():

    stored_password = "scrypt:32768:8:1$I5W3l0w0R8bCEaMR$622d98f696f09e62aae8be623f0fa1f8cf43d3e5448ae890e6df9a632ac0c719840cbe7d1c35b7a561fa1486f3ed5f7fca1b3d34089e42d2462a2a891b5b8345"


    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if username == "admin" and check_password_hash(stored_password, password):
            session.permanent = True
            session['admin'] = True
            return redirect('/admin')
        else:
            return "Invalid Credentials"

    return render_template('login.html')



#For Logout

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect('/login')



if __name__ == '__main__':
    app.run(debug=True)

