import os
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)
from werkzeug.security import generate_password_hash, check_password_hash

from models import db, User, Book, Borrowing

load_dotenv()

application = Flask(__name__)

# ── Configuration ──────────────────────────────────────────────────────────────
application.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
application.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///library.db"
)
application.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
application.config["WTF_CSRF_ENABLED"] = False  # CSRF handled via secret key; disable for simplicity

# ── Extensions ─────────────────────────────────────────────────────────────────
db.init_app(application)

login_manager = LoginManager(application)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ── Database initialisation ────────────────────────────────────────────────────
def seed_sample_books():
    """Insert a handful of sample books if the table is empty."""
    if Book.query.count() > 0:
        return
    samples = [
        Book(
            title="The Great Gatsby",
            author="F. Scott Fitzgerald",
            isbn="9780743273565",
            year=1925,
            description="A story of the fabulously wealthy Jay Gatsby and his love for Daisy Buchanan.",
            quantity=3,
            available=3,
        ),
        Book(
            title="To Kill a Mockingbird",
            author="Harper Lee",
            isbn="9780061935466",
            year=1960,
            description="The unforgettable novel of a childhood in a sleepy Southern town and the crisis of conscience that rocked it.",
            quantity=2,
            available=2,
        ),
        Book(
            title="1984",
            author="George Orwell",
            isbn="9780451524935",
            year=1949,
            description="A dystopian social science fiction novel and cautionary tale.",
            quantity=4,
            available=4,
        ),
        Book(
            title="Pride and Prejudice",
            author="Jane Austen",
            isbn="9780141439518",
            year=1813,
            description="A romantic novel of manners set in rural England.",
            quantity=2,
            available=2,
        ),
        Book(
            title="The Hobbit",
            author="J.R.R. Tolkien",
            isbn="9780547928227",
            year=1937,
            description="A fantasy novel about the adventures of hobbit Bilbo Baggins.",
            quantity=3,
            available=3,
        ),
        Book(
            title="Harry Potter and the Philosopher's Stone",
            author="J.K. Rowling",
            isbn="9780439708180",
            year=1997,
            description="The first novel in the Harry Potter series.",
            quantity=5,
            available=5,
        ),
    ]
    db.session.add_all(samples)
    db.session.commit()


with application.app_context():
    db.create_all()
    seed_sample_books()


# ── Helpers ────────────────────────────────────────────────────────────────────
def admin_required(f):
    """Decorator that restricts a view to admin users."""
    from functools import wraps

    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)

    return decorated


# ── Public routes ──────────────────────────────────────────────────────────────
@application.route("/")
def index():
    query = request.args.get("q", "").strip()
    if query:
        books = Book.query.filter(
            db.or_(
                Book.title.ilike(f"%{query}%"),
                Book.author.ilike(f"%{query}%"),
                Book.isbn.ilike(f"%{query}%"),
            )
        ).order_by(Book.title).all()
    else:
        books = Book.query.order_by(Book.title).all()
    return render_template("index.html", books=books, query=query)


@application.route("/book/<int:book_id>")
def book_detail(book_id):
    book = db.get_or_404(Book, book_id)
    active_borrowing = None
    if current_user.is_authenticated:
        active_borrowing = Borrowing.query.filter_by(
            user_id=current_user.id, book_id=book_id, status="borrowed"
        ).first()
    return render_template("book_detail.html", book=book, active_borrowing=active_borrowing)


# ── Authentication routes ──────────────────────────────────────────────────────
@application.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")

        error = None
        if not username or not email or not password:
            error = "All fields are required."
        elif len(username) < 3:
            error = "Username must be at least 3 characters."
        elif len(password) < 6:
            error = "Password must be at least 6 characters."
        elif password != confirm:
            error = "Passwords do not match."
        elif User.query.filter_by(username=username).first():
            error = "Username already taken."
        elif User.query.filter_by(email=email).first():
            error = "Email already registered."

        if error:
            flash(error, "danger")
            return render_template("register.html")

        user = User(
            username=username,
            email=email,
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.commit()
        flash("Account created! You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@application.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = User.query.filter(
            db.or_(User.username == identifier, User.email == identifier.lower())
        ).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=remember)
            next_page = request.args.get("next")
            flash(f"Welcome back, {user.username}!", "success")
            return redirect(next_page or url_for("index"))

        flash("Invalid username/email or password.", "danger")

    return render_template("login.html")


@application.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("index"))


# ── Borrowing routes ───────────────────────────────────────────────────────────
@application.route("/borrow/<int:book_id>", methods=["POST"])
@login_required
def borrow_book(book_id):
    book = db.get_or_404(Book, book_id)

    already = Borrowing.query.filter_by(
        user_id=current_user.id, book_id=book_id, status="borrowed"
    ).first()
    if already:
        flash("You already have this book borrowed.", "warning")
        return redirect(url_for("book_detail", book_id=book_id))

    if book.available < 1:
        flash("No copies available right now.", "danger")
        return redirect(url_for("book_detail", book_id=book_id))

    due = datetime.now(timezone.utc) + timedelta(days=14)
    borrowing = Borrowing(
        user_id=current_user.id,
        book_id=book_id,
        due_date=due,
        status="borrowed",
    )
    book.available -= 1
    db.session.add(borrowing)
    db.session.commit()
    flash(f'You borrowed "{book.title}". Due back by {due.strftime("%B %d, %Y")}.', "success")
    return redirect(url_for("my_borrowings"))


@application.route("/return/<int:borrowing_id>", methods=["POST"])
@login_required
def return_book(borrowing_id):
    borrowing = db.get_or_404(Borrowing, borrowing_id)

    if borrowing.user_id != current_user.id and not current_user.is_admin:
        abort(403)

    if borrowing.status == "returned":
        flash("This book has already been returned.", "warning")
        return redirect(url_for("my_borrowings"))

    borrowing.status = "returned"
    borrowing.return_date = datetime.now(timezone.utc)
    borrowing.book.available += 1
    db.session.commit()
    flash(f'"{borrowing.book.title}" returned successfully.', "success")
    return redirect(url_for("my_borrowings"))


@application.route("/my-borrowings")
@login_required
def my_borrowings():
    active = (
        Borrowing.query.filter_by(user_id=current_user.id, status="borrowed")
        .order_by(Borrowing.borrow_date.desc())
        .all()
    )
    history = (
        Borrowing.query.filter_by(user_id=current_user.id, status="returned")
        .order_by(Borrowing.return_date.desc())
        .all()
    )
    now = datetime.now(timezone.utc)
    return render_template("my_borrowings.html", active=active, history=history, now=now)


# ── Admin routes ───────────────────────────────────────────────────────────────
@application.route("/admin")
@login_required
@admin_required
def admin_dashboard():
    books = Book.query.order_by(Book.title).all()
    active_borrowings = (
        Borrowing.query.filter_by(status="borrowed")
        .order_by(Borrowing.borrow_date.desc())
        .all()
    )
    users = User.query.order_by(User.username).all()
    return render_template(
        "admin_dashboard.html", books=books, active_borrowings=active_borrowings, users=users
    )


@application.route("/admin/add-book", methods=["GET", "POST"])
@login_required
@admin_required
def admin_add_book():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        author = request.form.get("author", "").strip()
        isbn = request.form.get("isbn", "").strip() or None
        year_raw = request.form.get("year", "").strip()
        description = request.form.get("description", "").strip() or None
        quantity_raw = request.form.get("quantity", "1").strip()

        error = None
        if not title or not author:
            error = "Title and author are required."

        year = None
        if year_raw:
            try:
                year = int(year_raw)
            except ValueError:
                error = "Year must be a number."

        try:
            quantity = max(1, int(quantity_raw))
        except ValueError:
            quantity = 1

        if isbn and Book.query.filter_by(isbn=isbn).first():
            error = "A book with that ISBN already exists."

        if error:
            flash(error, "danger")
            return render_template("admin_add_book.html")

        book = Book(
            title=title,
            author=author,
            isbn=isbn,
            year=year,
            description=description,
            quantity=quantity,
            available=quantity,
        )
        db.session.add(book)
        db.session.commit()
        flash(f'"{book.title}" added to the catalog.', "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("admin_add_book.html")


@application.route("/admin/delete-book/<int:book_id>", methods=["POST"])
@login_required
@admin_required
def admin_delete_book(book_id):
    book = db.get_or_404(Book, book_id)
    if Borrowing.query.filter_by(book_id=book_id, status="borrowed").count() > 0:
        flash("Cannot delete a book that is currently borrowed.", "danger")
        return redirect(url_for("admin_dashboard"))
    db.session.delete(book)
    db.session.commit()
    flash(f'"{book.title}" removed from the catalog.', "success")
    return redirect(url_for("admin_dashboard"))


@application.route("/admin/promote/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def admin_promote_user(user_id):
    user = db.get_or_404(User, user_id)
    user.is_admin = True
    db.session.commit()
    flash(f"{user.username} has been promoted to admin.", "success")
    return redirect(url_for("admin_dashboard"))


# ── Error handlers ─────────────────────────────────────────────────────────────
@application.errorhandler(403)
def forbidden(e):
    return render_template("error.html", code=403, message="Access Forbidden"), 403


@application.errorhandler(404)
def not_found(e):
    return render_template("error.html", code=404, message="Page Not Found"), 404


if __name__ == "__main__":
    application.run(debug=True)

