from flask import Flask, render_template, request, redirect
from flask_sqlalchemy import SQLAlchemy
from flask_login import (
    LoginManager, UserMixin,
    login_user, login_required,
    logout_user, current_user
)

app = Flask(__name__)
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = False
app.config["SECRET_KEY"] = "secret123"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///expenses.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ---------- LOGIN ----------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"


# ---------- MODELS ----------
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)


class Expense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(100))
    amount = db.Column(db.Float)

    paid_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    payer = db.relationship("User")

    split_between = db.Column(db.String(200))


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ---------- ROOT ----------
@app.route("/")
def index():
    return redirect("/login")


# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]

        user = User.query.filter_by(username=username).first()

        if not user:
            user = User(username=username)
            db.session.add(user)
            db.session.commit()

        login_user(user)
        return redirect("/dashboard")

    return render_template("login.html")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect("/login")


# ---------- ADD EXPENSE (SMART SPLIT) ----------
@app.route("/add", methods=["POST"])
@login_required
def add_expense():
    desc = request.form["desc"]
    amount = float(request.form["amount"])

    selected_users = request.form.getlist("split_users")

    split_string = ",".join(selected_users)

    expense = Expense(
        description=desc,
        amount=amount,
        paid_by=current_user.id,
        split_between=split_string
    )

    db.session.add(expense)
    db.session.commit()

    return redirect("/dashboard")


# ---------- DELETE ----------
@app.route("/delete/<int:id>")
@login_required
def delete_expense(id):
    exp = Expense.query.get(id)
    if exp:
        db.session.delete(exp)
        db.session.commit()
    return redirect("/dashboard")


# ---------- BALANCE ----------
def calculate_balance():
    balances = {}

    expenses = Expense.query.all()

    for exp in expenses:
        users = exp.split_between.split(",")
        share = exp.amount / len(users)

        for u in users:
            balances[u] = balances.get(u, 0) - share

        payer = str(exp.paid_by)
        balances[payer] = balances.get(payer, 0) + exp.amount

    return balances


def settle(balances):
    creditors, debtors = [], []

    for u, amt in balances.items():
        if amt > 0:
            creditors.append([u, amt])
        elif amt < 0:
            debtors.append([u, -amt])

    result = []
    i = j = 0

    while i < len(debtors) and j < len(creditors):
        pay = min(debtors[i][1], creditors[j][1])

        result.append(
            f"User {debtors[i][0]} pays User {creditors[j][0]} ₹{round(pay,2)}"
        )

        debtors[i][1] -= pay
        creditors[j][1] -= pay

        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1

    return result


# ---------- DASHBOARD ----------
@app.route("/dashboard")
@login_required
def dashboard():
    expenses = Expense.query.all()
    users = User.query.all()

    balances = calculate_balance()
    settlements = settle(balances)

    return render_template(
        "dashboard.html",
        expenses=expenses,
        users=users,
        balances=balances,
        settlements=settlements,
        user=current_user
    )


# ---------- CREATE DB ----------
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    app.run(debug=True)