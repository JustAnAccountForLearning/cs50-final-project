import os
import sqlite3

from flask import Flask, flash, redirect, render_template, request, session, g
from tempfile import mkdtemp
from werkzeug.exceptions import default_exceptions

from helpers import formatNumber, formatName, customerExists, skierCode, initialIndicator

# Configure application
application = Flask(__name__)
application.secret_key = 'ZEPuPJWX7FogVeJqGoU4LfgDiSxlSkZQ' # Randomly generated key

# Ensure templates are auto-reloaded
application.config["TEMPLATES_AUTO_RELOAD"] = True

# Ensure responses aren't cached
@application.after_request
def after_request(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response

# Configure session to use filesystem (instead of signed cookies)
application.config["SESSION_FILE_DIR"] = mkdtemp()
application.config["SESSION_PERMANENT"] = False
application.config["SESSION_TYPE"] = "filesystem"

# Configure SQLite database
DATABASE = "/home/thomas/Documents/skiform/ski-intake-form/project/information.db"

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db


@application.route("/")
@application.route('/index')
def index():
    """ Start page """

    return render_template("index.html")


@application.route("/contactinfo", methods=["GET", "POST"])
def contactinfo():
    """ Gather the customer contact information """

    if request.method == "GET":
        return render_template("contactinfo.html")

    if request.method == "POST":

        # Gather all the information from the form and add it to a dictionary
        first = formatName(request.form.get("first"))
        last = formatName(request.form.get("last"))
        phoneNumber = request.form.get("phone")
        email = request.form.get("email")
        address1 = formatName(request.form.get("address1"))
        address2 = formatName(request.form.get("address2"))
        city = formatName(request.form.get("city"))
        state = formatName(request.form.get("state"))
        postal = formatName(request.form.get("postal"))

        # Format the phone number to be stored consistently
        phone = formatNumber(phoneNumber)

        info = {
            "first": first,
            "last": last,
            "phone": phone,
            "email": email,
            "address1": address1,
            "address2": address2,
            "city": city,
            "state": state,
            "postal": postal
        }

        # Check for any blank input and send an error if there is.
        for key, value in info.items():
            if value is '':
                # "address2" is optional and can be blank
                if key is not "address2":
                    return render_template("error.html", error="Incomplete input and our checks were bypassed.")

        # See if the customer already exists
        foundcustomer = customerExists(first, last, phone, email)

        if foundcustomer:
            return render_template("foundcustomer.html", yespage="addcustomer", nopage="addcustomer", foundcustomer=foundcustomer, newcustomer=info)
        else:
            return addcustomer(info)


@application.route("/addcustomer", methods=["GET", "POST"])
def addcustomer(info=None):
    """ Correct customer has been found - add customer to database """

    db = get_db().cursor()

    print(info) 
    # If info is not passed into addcustomer() as an argument, then it probably comes from a form
    if info is None:
        info = request.form.to_dict()
        print(info)

    db.execute("INSERT INTO contactinfo (first, last, phone, email, address1, address2, city, state, postal) VALUES (:first, :last, :phone, :email, :address1, :address2, :city, :state, :postal)",
                    info)
    get_db().commit()


    # Find the user in contactinfo.db for the given info
    values = db.execute("SELECT * FROM contactinfo WHERE phone=:phone", {"phone":info.get("phone")}).fetchall()

    user = []
    for i in range(len(values)):
        user.append(dict(zip(["id", "first", "last", "phone", "email", "address1", "address2", "city", "state", "postal"], values[i])))

    print(user)
    # Remember which user is working
    try:
        session.clear()
        session["user_id"] = user[0]["id"]
    except:
        return render_template("error.html", error="User not added or found")

    return redirect("/skierinfo")


@application.route("/findcustomer", methods=["GET", "POST"])
def findcustomer():
    """ Search database to locate customer info """
    if request.method == "GET":
        return render_template("findcustomer.html")

    if request.method == "POST":

        # Retrieve and format phone number if it exists
        if request.form.get("phone") is not None:
            phone = formatNumber(request.form.get("phone"))
        else:
            phone = ''

        # See if the customer already exists
        foundcustomer = customerExists(formatName(request.form.get("first")), formatName(request.form.get("last")), phone, request.form.get("email"))

        if foundcustomer:
            return render_template("foundcustomer.html", yespage="addcustomer", nopage="", foundcustomer=foundcustomer, newcustomer=None)
        else:

            # TODO: Let customer know that the customer has NOT been found in database and ask to restart with a new page.

            return redirect("/")


@application.route("/skierinfo", methods=["GET", "POST"])
def skierinfo():
    """ Gather skier information in order to find binding settings """

    if request.method == "GET":
        try:
            if not session["user_id"]:
                return redirect("/")
            else:
                return render_template("skierinfo.html")
        except:
            return render_template("error.html", error="Session has ended. Please start again.")

    if request.method == "POST":

        db = get_db().cursor()

        weight = request.form.get("weight")
        foot = request.form.get("foot")
        inches = request.form.get("inches")
        height = (foot * 12) + inches # Store in inches for ease of use later
        age = request.form.get("age")
        skiertype = request.form.get("type")
        skiercode = skierCode(weight, height, age, skiertype)

        if not skiercode:
            return render_template("error.html", error="There was missing informationt to calculate your skier code.")

        try:
            id = session["user_id"]
        except:
            return render_template("error.html", error="Sorry, there was a disconnect in the system. Please start again.")

        # Add the given information and calculated skiercode to the skierinfo database
        db.execute("INSERT INTO skierinfo (id, weight, foot, inches, age, skiertype, skiercode) VALUES (:id, :weight, :foot, :inches, :age, :skiertype, :skiercode)",
                   dict(id=id, weight=weight, foot=foot, inches=inches, age=age, skiertype=skiertype, skiercode=skiercode))
        get_db().commit()

        # Prep info to pass into verify.html
        if skiertype is "0":
            skiertype = "-1"
        if skiertype is "4":
            skiertype = "3+"

        skierinfo = {
           "weight": weight,
           "foot": foot,
           "inches": inches,
           "age": age,
           "skiertype": skiertype
        }

        values = db.execute("SELECT * FROM contactinfo WHERE id=:id", id=id).fetchall()

        customer = (dict(zip(["id", "first", "last", "phone", "email", "address1", "address2", "city", "state", "postal"], values[0])))

        return render_template("verify.html", customer=customer[0], skierinfo=skierinfo)


@application.route("/verify", methods=["GET", "POST"])
def verify():
    """ Allow the customer to verify the previously provided information """

    if request.method == "GET":
        return redirect("/")

    if request.method == "POST":
        db = get_db().cursor()

        values = db.execute("SELECT * FROM contactinfo WHERE id=:id", {id:session["user_id"]}).fetchall()

        customer = (dict(zip(["id", "first", "last", "phone", "email", "address1", "address2", "city", "state", "postal"], values[0])))

        skierinfo = request.form.to_dict()

        return render_template("verify.html", customer=customer[0], skierinfo=skierinfo)


@application.route("/update", methods=["POST"])
def update():
    """ Just a method to update the SQL databases if changes were made to verify """

    if request.method == "POST":

        db = get_db().cursor()

        try:
            # Gather all the information from the form and add it to a dictionary
            first = formatName(request.form.get("first"))
            last = formatName(request.form.get("last"))
            phoneNumber = request.form.get("phone")
            email = request.form.get("email")
            address1 = formatName(request.form.get("address1"))
            address2 = formatName(request.form.get("address2"))
            city = formatName(request.form.get("city"))
            state = formatName(request.form.get("state"))
            postal = formatName(request.form.get("postal"))

            weight = request.form.get("weight")
            foot = request.form.get("foot")
            inches = request.form.get("inches")
            age = request.form.get("age")
            skiertype = request.form.get("skiertype")

            # Calculae skier code for storage
            height = (foot * 12) + inches
            skiercode = skierCode(weight, height, age, skiertype)

            # Format the phone number to be stored consistently
            phone = formatNumber(phoneNumber)

            customer = {
                "first": first,
                "last": last,
                "phone": phone,
                "email": email,
                "address1": address1,
                "address2": address2,
                "city": city,
                "state": state,
                "postal": postal
            }



        except:
           return render_template("error.html", error="There has been an error processing your information.")

        # Check for any blank input and send an error if there is.
        for key, value in list(customer.items()):
            if value is '':
                # "address2" is optional and can be blank
                if key is not "address2":
                    return render_template("error.html", error="Incomplete input. That shouldn't have happened.")

        try:
            userid = session["user_id"]
            customer['id'] = userid
        except:
            return render_template("error.html", error="Session has ended. Please start again.")

        # Store the updated info into customer info
        db.execute("UPDATE contactinfo SET first=:first, last=:last, phone=:phone, email=:email, address1=:address1, address2=:address2, city=:city, state=:state, postal=:postal WHERE id=:id",
                       customer)

        # Store the updated info into skier info
        db.execute("UPDATE skierinfo SET id=:id, weight=:weight, foot=:foot, inches=:inches, age=:age, skiertype=:skiertype, skiercode=:skiercode",
                   dict(id=userid, weight=weight, foot=foot, inches=inches, age=age, skiertype=skiertype, skiercode=skiercode))

        get_db().commit()

        # Prep info to pass into verify.html
        if skiertype is "0":
            skiertype = "-1"
        if skiertype is "4":
            skiertype = "3+"

        skierinfo = {
           "weight": weight,
           "foot": foot,
           "inches": inches,
           "age": age,
           "skiertype": skiertype
        }

        return render_template("verify.html", customer=customer, skierinfo=skierinfo)


@application.route("/done", methods=["GET","POST"])
def done():
    """ Handover from customer to service writer """

    if request.method == "GET":
        return redirect("/")

    if request.method == "POST":
        return render_template("done.html")


@application.route("/equipment", methods=["GET", "POST"])
def equipment():
    """ Gather information on skis, bindings, and boots """

    if request.method == "GET":
        return redirect("/")

    if request.method == "POST":
        initials = request.form.get("initials")
        return render_template("equipment.html", initials = initials)


@application.route("/printticket", methods=["GET", "POST"])
def printticket():
    """ Prepare to print out the final ticket with all information"""

    if request.method == "GET":
        #TODO: have it redirect to "/"
        return render_template("printticket.html")

    if request.method == "POST":
        # Get the user id
        try:
            userid = session("user_id")
        except:
            return render_template("error.html", error="Sorry, your session has been restarted.")


        # Gather the information from the equipment form.
        try:
            initials = request.form.get("initials").upper() # Capitalize the initials
            skimake = formatName(request.form.get("skimake"))
            skimodel = formatName(request.form.get("skimodel"))
            skilength = request.form.get("skilength")
            bindmake = formatName(request.form.get("bindmake"))
            bindmodel = formatName(request.form.get("bindmodel"))
            bootmake = formatName(request.form.get("bootmake"))
            bootmodel = formatName(request.form.get("bootmodel"))
            bootcolor = formatName(request.form.get("bootcolor"))
            solelength = request.form.get("solelength")
            mountloc = request.form.get("mountloc")
            notes = request.form.get("notes")

            equipmentinfo = {
                "initials": initials,
                "skimake": skimake,
                "skimodel": skimodel,
                "skilength": skilength,
                "bindmake": bindmake,
                "bindmodel": bindmodel,
                "bootmake": bootmake,
                "bootmodel": bootmodel,
                "bootcolor": bootcolor,
                "solelength": solelength,
                "mountloc": mountloc,
                "notes": notes
            }

            # Store equipment information in the database
            db.execute("INSERT INTO equipmentinfo (userid, intials, skimake, skimodel, skilength, bindmake, bindmodel, bootmake, bootmodel, bootcolor, solelength, mountloc, notes) VALUES (:userid, :intials, :skimake, :skimodel, :skilength, :bindmake, :bindmodel, :bootmake, :bootmodel, :bootcolor, :solelength, :mountloc, :notes)",
                       dict(userid=userid, intials=initials, skimake=skimake, skimodel=skimodel, skilength=skilength, bindmake=bindmake, bindmodel=bindmodel, bootmake=bootmake, bootmodel=bootmodel, bootcolor=bootcolor, solelength=solelength, mountloc=mountloc, notes=notes))
            get_db().commit()

        except:
            return render_template("error.html", error="We're sorry. There was an error processing equipment information.")


        # Grab the customer info
        try:
            values = db.execute("SELECT * FROM contactinfo WHERE id=:userid", {userid:userid}).fetchall()

            contactinfo = (dict(zip(["id", "first", "last", "phone", "email", "address1", "address2", "city", "state", "postal"], values[0])))
        except:
            return render_template("error.html", error="We're sorry. There was an error retrieving customer contact info.")


        # Grab the skier info
        try:
            values = db.execute("SELECT * FROM skierinfo WHERE id=:userid", {userid:userid}).fetchall()
            # Select only the most recent iteration by using [-1]
            skierinfo = (dict(zip(["id", "first", "last", "phone", "email", "address1", "address2", "city", "state", "postal"], values[-1])))
            
        except:
            return render_template("error.html", error="We're sorry. There was an error retrieving skier info.")

        # Calculate the skier's intitial indicator setting
        try:
            indicator = initialIndicator(solelength, skierinfo["skiercode"])
        except:
            return render_template("error.html", error="There was an error calculating the skier's initial indicator value.")

        return render_template("printticket.html", contactinfo=contactinfo, skierinfo=skierinfo, equipmentinfo=equipmentinfo, initialindicator = indicator)


@application.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


if __name__ == '__main__':
    application.debug = True
    application.run()