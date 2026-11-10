WEBSITE PRE-ORDER KANTIN SEKOLAH

Konsep:
- Pembeli: orang tua/wali siswa, guru/staf sekolah, dan pengunjung.
- Tidak ada kolom kelas siswa.
- Siswa tetap dapat membeli langsung di kantin.
- Pembeli memilih menu, jumlah, dan waktu pengambilan.
- Admin mengelola stok dan status pesanan.

MENJALANKAN DI WINDOWS:
1. Ekstrak ZIP.
2. Buka folder kantin-preorder-baru di VS Code.
3. Buka Terminal > New Terminal.
4. Jalankan:
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
5. Buka http://127.0.0.1:5000
6. Halaman admin: http://127.0.0.1:5000/admin

DEPLOY KE RENDER:
- Build Command: pip install -r requirements.txt
- Start Command: gunicorn app:app
- Untuk menyimpan database secara persisten di Render, pasang Persistent Disk
  pada /var/data dan atur environment variable DATA_DIR=/var/data.
- Jangan gunakan halaman /admin untuk transaksi sungguhan sebelum ditambahkan login admin.
- Ganti SECRET_KEY melalui environment variable sebelum produksi.

Catatan:
Database kantin.db dibuat otomatis saat aplikasi pertama kali dijalankan.
