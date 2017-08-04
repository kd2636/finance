from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session, url_for
from flask_session import Session
from passlib.apps import custom_app_context as pwd_context
from tempfile import gettempdir

from helpers import *

# configure application
app = Flask(__name__)

# ensure responses aren't cached
if app.config["DEBUG"]:
    @app.after_request
    def after_request(response):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Expires"] = 0
        response.headers["Pragma"] = "no-cache"
        return response

# custom filter
app.jinja_env.filters["usd"] = usd

# configure session to use filesystem (instead of signed cookies)
app.config["SESSION_FILE_DIR"] = gettempdir()
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

@app.route("/")
@login_required
def index():
    sharePrice = []
    shareTotal = []
    total = 0
    shares = db.execute("SELECT * FROM shares WHERE userid = :userid ORDER BY name", userid = session.get("user_id"))
    n=len(shares)
    for share in shares:
        shareDetail = lookup(share["symbol"])
        sharePrice.append(usd(shareDetail["price"]))
        shareTotal.append(usd(shareDetail["price"]*share["qty"]))
        total = total + (shareDetail["price"]*share["qty"])
    
        
        
    user = db.execute("Select * FROM users WHERE id = :userid", userid = session.get("user_id"))
    cash = user[0]["cash"]
    total = total + cash
    cash = usd(cash)
    total = usd(total)
    return render_template("index.html", shares = shares, sharePrice = sharePrice, n = n, shareTotal = shareTotal, total = total, cash = cash)

@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock."""
    if request.method == "POST":
        if not request.form.get("symbol") or not request.form.get("qty"):
            return apology("fill details")
        
        qty = int(request.form.get("qty"))
        
        if qty < 1:
            return apology("Invalid Shares")
        
        share = lookup(request.form.get("symbol"))
        if share == None:
            return apology("Invalid Shares")
            
        row = db.execute("SELECT * FROM users WHERE id = :id", id=session.get("user_id"))
        if len(row) != 1:
            return apology("database error")
            
        cash = row[0]["cash"]
        
        if share["price"]*qty <= cash:
            newCash = cash - (share["price"]*qty)
            try:
                db.execute("INSERT INTO transactions (userid, symbol, price, qty) VALUES(:userid, :symbol, :price, :qty)",
                userid=session.get("user_id"), symbol = share["symbol"], price=usd(share["price"]), qty = qty)
                
                db.execute("UPDATE users SET cash = :cash WHERE id = :userid",
                cash = newCash, userid=session.get("user_id"))
                
                updater = db.execute("SELECT * FROM shares WHERE userid = :userid AND symbol = :symbol",userid = session.get("user_id"), symbol = share["symbol"])
                if len(updater) == 0:
                    db.execute("INSERT INTO shares (userid, symbol, name, qty) VALUES(:userid, :symbol, :name, :qty)",
                    userid = session.get("user_id"), symbol=share["symbol"], name=share["name"], qty=qty)
                
                elif len(updater) == 1:
                    db.execute("UPDATE shares SET qty = :q WHERE userid = :userid AND symbol = :symbol",
                    q=updater[0]["qty"]+qty, userid = session.get("user_id"), symbol = share["symbol"])
                    
                else:
                    return apology("len of updater is 2 or more")
                

            except:
                return apology("database error 2")
        else:
            return apology("can't afford")
        flash("Bought")    
        return redirect(url_for("index"))
    
    else:
        return render_template("buy.html")

@app.route("/history")
@login_required
def history():
    """Show history of transactions."""
    rows = db.execute("SELECT * FROM transactions WHERE userid = :userid ORDER BY transacted",
    userid = session.get("user_id"))
    return render_template("history.html", rows = rows)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in."""

    # forget any user_id
    session.clear()

    # if user reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username")

        # ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password")

        # query database for username
        rows = db.execute("SELECT * FROM users WHERE username = :username", username=request.form.get("username"))

        # ensure username exists and password is correct
        if len(rows) != 1 or not pwd_context.verify(request.form.get("password"), rows[0]["hash"]):
            return apology("invalid username and/or password")

        # remember which user has logged in
        session["user_id"] = rows[0]["id"]
        session["user_name"] = rows[0]["username"]

        # redirect user to home page
        return redirect(url_for("index"))

    # else if user reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")

@app.route("/logout")
def logout():
    """Log user out."""

    # forget any user_id
    session.clear()

    # redirect user to login form
    return redirect(url_for("login"))

@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        if not request.form.get("symbol"):
            return apology("enter symbol")
        
        share = lookup(request.form.get("symbol"))
        if share == None:
            return apology("Invalid Symbol")
        
        fprice = usd(share["price"])    
        return render_template("quoted.html",share = share,fprice = fprice)
        
    else:
        return render_template("quote.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user."""
    
    if request.method == "POST":
        if not request.form.get("username"):
            return apology("Username cannot be blank")
            
        elif not request.form.get("passo"):
            return apology("Password cannot be blank")
            
        elif request.form.get("passo") != request.form.get("passv"):
            return apology("Password do not match")
            
        else:
            hash = pwd_context.encrypt(request.form.get("passo"))
            try:
                userid = db.execute("INSERT INTO users (username, hash) VALUES(:username, :hash)",
                username=request.form.get("username"), hash=hash)
                if userid == None:
                    return apology("Username taken")
            except:
                return apology("Database insertion error")
            
            session["user_id"]=userid
            session["user_name"]=request.form.get("username")
            return redirect(url_for("index"))
            
    else:
        return render_template("register.html")
        

@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock."""
    
    if request.method == "POST":
        if not request.form.get("symbol") or not request.form.get("qty"):
            return apology("Cannot leave blank")
            
        share = lookup(request.form.get("symbol"))
        if share == None:
            return apology("Invalid Shares")
        
        qty = int(request.form.get("qty"))
        if qty < 1:
            return apology("Invalid Shares")
            
        row = db.execute("SELECT * FROM shares WHERE userid = :userid AND symbol = :symbol",
        userid = session.get("user_id"), symbol=share["symbol"])
        
        if len(row) == 0:
            return apology("Invalid attempt")
            
        if len(row) == 1:
            q2 = row[0]["qty"]
            if qty > q2:
                return apology("Invalid attempt")
            else:
                amt = qty*share["price"]
                
                db.execute("INSERT INTO transactions (userid, symbol, price, qty) VALUES(:userid, :symbol, :price, :qty)",
                userid=session.get("user_id"), symbol = share["symbol"], price=usd(share["price"]), qty = -qty)
                
                db.execute("UPDATE users SET cash = cash + :amt WHERE id = :userid",
                amt = amt, userid = session.get("user_id"))
                
                if qty == q2:
                    db.execute("DELETE FROM shares WHERE userid = :userid AND symbol = :symbol",
                    userid = session.get("user_id"), symbol = share["symbol"])
                    
                else:
                    db.execute("UPDATE shares SET qty = qty - :q WHERE userid = :userid AND symbol = :symbol",
                    q=qty, userid = session.get("user_id"), symbol = share["symbol"])
                
                flash("Sold")    
                return redirect(url_for("index"))
        else:
            return apology("database error sell")
        
    else:
        return render_template("sell.html")
                
    
@app.route("/addcash", methods=["GET", "POST"])
@login_required
def addcash():
    if request.method == "POST":
        
        if not request.form.get("addCash"):
            return apology("Cannot leave blank")
        
        try:    
            addCash = float(request.form.get("addCash"))
        except:
            return apology("Invalid amount")
        
        db.execute("UPDATE users SET cash = cash + :newCash WHERE id = :userid",
        newCash = addCash, userid = session.get("user_id"))
        
        flash("Cash Added")
        return redirect(url_for("index"))
        
    else:
        return render_template("addcash.html")