from string import ascii_lowercase, ascii_uppercase, digits
from datetime import datetime, timedelta
from hashlib import sha256
from os import environ, mkdir
import os.path
import random

from bcrypt import checkpw
from flask import abort, Flask, request, render_template, session, redirect, flash, send_file
from flask_session import Session
import redis
from redis_om import HashModel, Field, Migrator

app = Flask(__name__, static_url_path="/static", static_folder="../static", template_folder="../templates")
pool = redis.ConnectionPool().from_url(environ['REDIS_OM_URL'])
file_client = redis.Redis(connection_pool=pool)
locker_client = redis.Redis(connection_pool=pool)

SESSION_TYPE = 'redis'
SESSION_REDIS = redis.Redis(connection_pool=pool)
app.config.from_object(__name__)
Session(app)


TEMPORARY_DIRECTORY: str = environ.get("TMP_DIR", "")
if not TEMPORARY_DIRECTORY:
	TEMPORARY_DIRECTORY = "/var/www/Locker/tmp"

with open("/var/www/Locker/.passwd") as f:
	PASSWORD = f.read().strip().encode()

if os.listdir(TEMPORARY_DIRECTORY):
	os.rmdir(TEMPORARY_DIRECTORY)
	os.mkdir(TEMPORARY_DIRECTORY)

class File(HashModel):
	filename: str
	file_hash: str = Field(index=True)
	upload_date: datetime = Field(default_factory=datetime.now)
	file_path: str
	file_size: int
	locker_code: str = Field(index=True)

	class Meta:
		database = file_client


class Locker(HashModel):
	code: str = Field(index=True)
	is_locker: int = Field(default=1, index=True)
	creation_time: datetime
	expire_time: datetime

	class Meta:
		database = locker_client


Migrator().run()

def locker_code() -> str:
	return "".join(random.choice(ascii_lowercase + ascii_uppercase + digits) for _ in range(4))

@app.route("/", methods=["GET"])
def index():
	if not session.get("logged_in", False):
		return render_template("login.html")
	else:
		return render_template("locker-room.html", locker_code=locker_code(), lockers=Locker.find().all())

@app.route("/create-locker", methods=["POST"])
def create_locker():
	if not session.get("logged_in"):
		flash("Not logged in.")
		return redirect("/")

	new_locker = Locker(
		code = request.form['code'],
		creation_time = datetime.now(),
		expire_time = datetime.now() + timedelta(weeks=2)
	)

	mkdir(TEMPORARY_DIRECTORY + "/" + new_locker.code)

	new_locker.save()
	return redirect(f"/l/{new_locker.code}")

@app.route("/login", methods=["POST"])
def check_if_me():
	if passwd := request.form.get('password'):
		if checkpw(passwd.encode(), PASSWORD):
			session["logged_in"] = True
			return redirect("/")

	flash("Bad password. Try again.")
	return redirect("/")


@app.route("/l/<locker_code>", methods=["GET"])
def add_locker(locker_code: str):
	if not session.get("logged_in"):
		flash("Not logged in.")
		return redirect("/")

	try:
		locker = Locker.find(Locker.code == locker_code).first()
	except redis.exceptions.ResponseError:
		return abort(404)

	files = File.find(File.locker_code == locker_code).all()
	return render_template("locker.html", locker=locker, files=files)

@app.route("/l/<locker_code>/<file_name>", methods=["GET", "PUT"])
def upload_file(locker_code: str, file_name: str):

	try:
		locker = Locker.find(Locker.code == locker_code).first()
	except redis.exceptions.ResponseError:
		return abort(404)

	if request.method == "PUT":
		file_hash = sha256(request.data, usedforsecurity=False).hexdigest()
		new_file = File(
			filename = file_name,
			file_hash = file_hash,
			file_path = TEMPORARY_DIRECTORY + f"/{locker_code}/" + file_hash,
			file_size = len(request.data),
			locker_code = locker_code
		)
		new_file.save()
		with open(new_file.file_path, "wb") as f:
			f.write(request.data)
		return "Saved File! (:\n"
	else:
		if not session.get("logged_in"):
			flash("Not logged in.")
			return redirect("/")

		file = File.find(File.file_hash == file_name).first()
		return send_file(file.file_path, as_attachment=True, download_name=file.filename)