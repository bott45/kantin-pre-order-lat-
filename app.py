
import os
import sqlite3
import hmac
from datetime import datetime
from functools import wraps
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session
)

app = Flask(__name__)

# Pengaturan keamanan
app.secret_key = os.environ.get(
    "SECRET_KEY", "kunci-rahasia-lokal-ganti-nanti"
)

app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = (
    os.environ.get("RENDER") is not None
)

# Akun admin
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "123")

# Lokasi database
DATA_DIR = os.environ.get(
    "DATA_DIR", os.path.dirname(os.path.abspath(__file__))
)
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "kantin.db")

KATEGORI_PEMBELI = [
    "Orang tua/wali siswa",
    "Guru/staf sekolah",
    "Pengunjung"
]


def koneksi():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with koneksi() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            deskripsi TEXT DEFAULT '',
            harga INTEGER NOT NULL CHECK(harga >= 0),
            stok INTEGER NOT NULL DEFAULT 0 CHECK(stok >= 0),
            foto TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS pesanan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kode TEXT NOT NULL UNIQUE,
            nama_pembeli TEXT NOT NULL,
            no_hp TEXT NOT NULL,
            kategori_pembeli TEXT NOT NULL,
            waktu_ambil TEXT NOT NULL,
            catatan TEXT DEFAULT '',
            total INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Menunggu',
            dibuat_pada TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS detail_pesanan (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pesanan_id INTEGER NOT NULL,
            menu_id INTEGER,
            nama_menu TEXT NOT NULL,
            harga INTEGER NOT NULL,
            jumlah INTEGER NOT NULL,
            subtotal INTEGER NOT NULL,
            FOREIGN KEY(pesanan_id)
                REFERENCES pesanan(id) ON DELETE CASCADE
        );
        """)

        jumlah = db.execute(
            "SELECT COUNT(*) FROM menu"
        ).fetchone()[0]

        if jumlah == 0:
            db.executemany(
                """
                INSERT INTO menu
                (nama, deskripsi, harga, stok, foto)
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    ("Cireng", "Cireng renyah dengan pilihan saus.", 5000, 30, ""),
                    ("Seblak", "Seblak hangat dengan bumbu pedas gurih.", 10000, 20, ""),
                    ("Cireng Isi", "Cireng dengan isian gurih.", 7000, 25, ""),
                ],
            )


# PENGAMAN HALAMAN ADMIN
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("admin_login"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function


# HALAMAN LOGIN ADMIN
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("admin_login"):
        return redirect(url_for("admin"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        username_benar = hmac.compare_digest(
            username, ADMIN_USERNAME
        )
        password_benar = hmac.compare_digest(
            password, ADMIN_PASSWORD
        )

        if username_benar and password_benar:
            session.clear()
            session["admin_login"] = True
            return redirect(url_for("admin"))

        flash("Username atau password salah.", "error")

    return render_template("login.html")


# LOGOUT ADMIN
@app.route("/logout")
@admin_required
def logout():
    session.clear()
    flash("Kamu berhasil logout.", "success")
    return redirect(url_for("login"))


# HALAMAN UTAMA PEMBELI
@app.route("/")
def index():
    with koneksi() as db:
        menu = db.execute(
            "SELECT * FROM menu ORDER BY nama"
        ).fetchall()

    return render_template(
        "index.html",
        menu=menu,
        kategori=KATEGORI_PEMBELI
    )


# PROSES PEMESANAN
@app.post("/pesan")
def pesan():
    nama = request.form.get("nama_pembeli", "").strip()
    no_hp = request.form.get("no_hp", "").strip()
    kategori = request.form.get("kategori_pembeli", "").strip()
    waktu = request.form.get("waktu_ambil", "").strip()
    catatan = request.form.get("catatan", "").strip()

    if not nama or not no_hp or not waktu or kategori not in KATEGORI_PEMBELI:
        flash(
            "Lengkapi nama, nomor HP, kategori pembeli, dan waktu pengambilan.",
            "error"
        )
        return redirect(url_for("index"))

    pilihan = []

    for key, value in request.form.items():
        if key.startswith("jumlah_"):
            try:
                menu_id = int(key.replace("jumlah_", "", 1))
                qty = int(value or 0)
            except ValueError:
                continue

            if qty > 0:
                pilihan.append((menu_id, qty))

    if not pilihan:
        flash(
            "Pilih minimal satu menu dengan jumlah lebih dari 0.",
            "error"
        )
        return redirect(url_for("index"))

    with koneksi() as db:
        rincian = []
        total = 0

        for menu_id, qty in pilihan:
            item = db.execute(
                "SELECT * FROM menu WHERE id = ?",
                (menu_id,)
            ).fetchone()

            if item is None:
                flash("Ada menu yang tidak ditemukan.", "error")
                return redirect(url_for("index"))

            if qty > item["stok"]:
                flash(
                    f"Stok {item['nama']} tidak mencukupi. "
                    f"Sisa stok: {item['stok']}.",
                    "error"
                )
                return redirect(url_for("index"))

            subtotal = item["harga"] * qty
            total += subtotal
            rincian.append((item, qty, subtotal))

        kode = "KTN" + datetime.now().strftime("%y%m%d%H%M%S")

        cur = db.execute("""
            INSERT INTO pesanan
            (kode, nama_pembeli, no_hp, kategori_pembeli,
             waktu_ambil, catatan, total, status, dibuat_pada)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Menunggu', ?)
        """, (
            kode, nama, no_hp, kategori, waktu,
            catatan, total,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))

        pesanan_id = cur.lastrowid

        for item, qty, subtotal in rincian:
            db.execute("""
                INSERT INTO detail_pesanan
                (pesanan_id, menu_id, nama_menu, harga, jumlah, subtotal)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                pesanan_id, item["id"], item["nama"],
                item["harga"], qty, subtotal
            ))

            db.execute(
                "UPDATE menu SET stok = stok - ? WHERE id = ?",
                (qty, item["id"])
            )

    return render_template(
        "sukses.html",
        kode=kode,
        nama=nama,
        total=total
    )


# DASHBOARD ADMIN (WAJIB LOGIN)
@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    if request.method == "POST":
        aksi = request.form.get("aksi")

        with koneksi() as db:
            if aksi == "status":
                db.execute(
                    "UPDATE pesanan SET status = ? WHERE id = ?",
                    (
                        request.form.get("status"),
                        request.form.get("pesanan_id")
                    )
                )

            elif aksi == "tambah_menu":
                nama = request.form.get("nama", "").strip()
                deskripsi = request.form.get("deskripsi", "").strip()

                try:
                    harga = int(request.form.get("harga", "0"))
                    stok = int(request.form.get("stok", "0"))
                except ValueError:
                    flash("Harga dan stok harus berupa angka.", "error")
                    return redirect(url_for("admin"))

                if nama and harga >= 0 and stok >= 0:
                    db.execute("""
                        INSERT INTO menu
                        (nama, deskripsi, harga, stok)
                        VALUES (?, ?, ?, ?)
                    """, (nama, deskripsi, harga, stok))

            elif aksi == "stok":
                try:
                    stok = int(request.form.get("stok", "0"))

                    if stok >= 0:
                        db.execute(
                            "UPDATE menu SET stok = ? WHERE id = ?",
                            (stok, request.form.get("menu_id"))
                        )

                except ValueError:
                    flash("Stok harus berupa angka.", "error")

        flash("Perubahan berhasil disimpan.", "success")
        return redirect(url_for("admin"))

    with koneksi() as db:
        menu = db.execute(
            "SELECT * FROM menu ORDER BY nama"
        ).fetchall()

        pesanan = db.execute(
            "SELECT * FROM pesanan ORDER BY id DESC"
        ).fetchall()

        detail = db.execute("""
            SELECT d.*, p.kode
            FROM detail_pesanan d
            JOIN pesanan p ON p.id = d.pesanan_id
            ORDER BY d.id DESC
        """).fetchall()

        omzet = db.execute("""
            SELECT COALESCE(SUM(total), 0)
            FROM pesanan
            WHERE status = 'Selesai'
        """).fetchone()[0]

        jumlah_pesanan = db.execute(
            "SELECT COUNT(*) FROM pesanan"
        ).fetchone()[0]

    return render_template(
        "admin.html",
        menu=menu,
        pesanan=pesanan,
        detail=detail,
        omzet=omzet,
        jumlah_pesanan=jumlah_pesanan
    )


# CEK PESANAN PEMBELI
@app.route("/cek-pesanan", methods=["GET", "POST"])
def cek_pesanan():
    hasil = None

    if request.method == "POST":
        kode = request.form.get("kode", "").strip().upper()

        with koneksi() as db:
            hasil = db.execute(
                "SELECT * FROM pesanan WHERE kode = ?",
                (kode,)
            ).fetchone()

    return render_template("cek.html", hasil=hasil)


# FORMAT HARGA RUPIAH
@app.template_filter("rupiah")
def rupiah(value):
    return "Rp" + f"{int(value):,}".replace(",", ".")


init_db()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
