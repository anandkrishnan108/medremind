from flask import Flask, render_template, url_for, redirect, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError
from flask_bcrypt import Bcrypt
import time
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
import schedule
from datetime import datetime
import sqlite3

app = Flask(__name__)        
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SECRET_KEY'] = os.environ['secret_key']


login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(id):
    return UserData.query.get(int(id))

class UserData(db.Model, UserMixin):
    __tablename__ = 'userdata'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=False)
    email = db.Column(db.String(20), nullable=False, unique=True)
    number = db.Column(db.Integer, nullable=False, unique=True)
    pwd = db.Column(db.String(80), nullable=False)
    #logged_in = db.Column(db.String(10), nullable=False)
    medicines = db.relationship('Medications', backref='user')


class Medications(db.Model):
    med_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('userdata.id'))
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    med_name = db.Column(db.String(200), nullable=False)
    days = db.Column(db.String(200), nullable=False)
    times = db.Column(db.String(200), nullable=False)
    taken = db.Column(db.String(10), nullable=False)
    dosage = db.Column(db.String(200)) 

class RegisterForm(FlaskForm):
    name = StringField(validators=[
                           InputRequired(), Length(min=4, max=80)], render_kw={"placeholder": "Name"})
    
    email = StringField(validators=[
                           InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Email"})

    number = StringField(validators=[
                           InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Number"})

    pwd = PasswordField(validators=[
                             InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})

    submit = SubmitField('Register')

    def validate_email(self, email):
        existing_user_email = UserData.query.filter_by(
            email=email.data).first()
        if existing_user_email:
            raise ValidationError(
                'That email already exists within the system. Please choose a different one.')
    def validate_number(self, number):
        existing_user_number = UserData.query.filter_by(
            number=number.data).first()
        if existing_user_number:
            raise ValidationError(
                'That number already exists within the system. Please choose a different one.')            


class LoginForm(FlaskForm):
    email = StringField(validators=[
                           InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Email"})

    pwd = PasswordField(validators=[
                             InputRequired(), Length(min=8, max=20)], render_kw={"placeholder": "Password"})

    submit = SubmitField('Login')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/login', methods=['POST', 'GET'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = UserData.query.filter_by(email=form.email.data).first()
        if user:
            if bcrypt.check_password_hash(user.pwd, form.pwd.data):
                login_user(user)
                print("login successful")
                return redirect(url_for('dashboard'))
    return render_template('login.html', form=form)


@app.route('/logout', methods=['POST', 'GET'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


@ app.route('/register', methods=['POST', 'GET'])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        hashed_password = bcrypt.generate_password_hash(form.pwd.data)
        new_user = UserData(name=form.name.data, email=form.email.data, number=form.number.data, pwd=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('register.html', form=form)  



@app.route('/dashboard', methods=['POST', 'GET'])
@login_required
def dashboard():
    user = current_user.id
    scheduler = BackgroundScheduler()
    scheduler.add_job(func=reminder, trigger="interval", args=str(user), seconds=5)
    #schedule.every(10).seconds.do(reminder, user_id=user)
    atexit.register(lambda: scheduler.shutdown())
    scheduler.start()
    if request.method == 'POST':
        medicine_name = request.form['med_name']
        days_arr = request.form.getlist("days")
        days_str = ' '.join(map(str, days_arr))     
        medicine_times = request.form['times']
        dosage = request.form['dosage']    
        new_medicine = Medications(med_name=medicine_name, days=days_str, times=medicine_times, taken="False", dosage=dosage, user_id=user)        
        try:
            db.session.add(new_medicine)
            db.session.commit()
            return redirect('/dashboard')
        except:
            return 'There was an issue adding your medicine'

    else:
        medicines = Medications.query.filter_by(user_id=user).order_by(Medications.date_created).all()
        return render_template('dashboard.html', medicines=medicines)    
    

@app.route('/delete/<int:id>')
def delete(id):
    medicine_to_delete = Medications.query.get_or_404(id)

    try:
        db.session.delete(medicine_to_delete)
        db.session.commit()
        return redirect('/dashboard')
    except:
        return 'There was a problem deleting that medicine.'

@app.route('/update/<int:id>', methods=['GET', 'POST'])
def update(id):
    medicine = Medications.query.get_or_404(id)

    if request.method == 'POST':
        medicine.med_name = request.form['med_name']
        days_arr = request.form.getlist("days") 
        medicine.days = ' '.join(map(str, days_arr))
        medicine.times = request.form['times']
        medicine.dosage = request.form['dosage']
        try:
            db.session.commit()
            return redirect('/dashboard')
        except:
            return 'There was an issue updating your medicine.'

    else:
        return render_template('update.html', medicine=medicine)


def reminder(user_id):
    dateandtime = time.strftime("%A, %I:%M %p")
    print(dateandtime)
    try:
        sqliteConnection = sqlite3.connect('database.db')
        cursor = sqliteConnection.cursor()
        #print("Connected to SQLite")

        sqlite_select_query = """SELECT * from Medications"""
        cursor.execute(sqlite_select_query)
        records = cursor.fetchall()
        #print("Total rows are:  ", len(records))
        for i in range(0, int(len(records))):
            db_id = records[i][1]
            if int(user_id) == db_id:
                #print("we got the correct user")
                days_arr = records[i][4].split()
                records[i][5].replace(" ", "")
                times_arr = records[i][5].split(',')
                for day in days_arr:
                    #print(day)
                    if day in dateandtime:
                        for a_time in times_arr:
                            #print(a_time)
                            if a_time in dateandtime:
                                print("Time to take your medicine.")
                                return (url_for('notification.html'))

        cursor.close()

    except sqlite3.Error as error:
        print("Failed to read data from sqlite table", error)
    finally:
        if sqliteConnection:
            sqliteConnection.close()
            #print("The SQLite connection is closed")


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
