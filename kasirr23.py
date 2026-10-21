import os
import sqlite3
import zlib
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st

# ======================================================================
# KONFIGURASI
# ======================================================================
DB_FILE = "kasir_minuman.db"
WIB = timezone(timedelta(hours=7))
OWNER_PIN = os.getenv("OWNER_PIN", "1234")  # ganti PIN pemilik di sini
DEFAULT_TOPIC = os.getenv("NTFY_TOPIC", "kedai-widodo-7391")

st.set_page_config(page_title="Kedai Minuman UMKM", page_icon="🧋", layout="wide")


# ======================================================================
# DATABASE & HELPER
# ======================================================================
def db():
    return sqlite3.connect(DB_FILE)


def init_db():
    conn = db()
    c = conn.cursor()
    c.execute(
        """CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT, kategori TEXT,
            harga_reguler INTEGER, harga_large INTEGER,
            stok INTEGER, gambar TEXT)"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS transaksi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama_pembeli TEXT, menu TEXT, ukuran TEXT,
            jumlah INTEGER, total_harga INTEGER, metode_bayar TEXT,
            waktu TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"""
    )
    # Kolom uang diterima & kembalian (aman untuk database lama)
    for kol in ("uang_diterima", "kembalian"):
        try:
            c.execute(f"ALTER TABLE transaksi ADD COLUMN {kol} INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass
    # Kedai hanya menjual Kopi & Teh: hapus menu contoh lama kategori Susu/Buah
    c.execute(
        "DELETE FROM menu WHERE kategori IN ('Susu','Buah') AND nama IN "
        "('Matcha Latte','Coklat Dingin','Jus Alpukat','Jus Mangga')"
    )
    # Menu contoh otomatis jika belum ada menu Kopi/Teh
    if c.execute("SELECT COUNT(*) FROM menu WHERE kategori IN ('Kopi','Teh')").fetchone()[0] == 0:
        contoh = [
            ("Kopi Susu Gula Aren", "Kopi", 15000, 20000, 30),
            ("Americano", "Kopi", 12000, 16000, 25),
            ("Caramel Latte", "Kopi", 18000, 23000, 20),
            ("Cappuccino", "Kopi", 16000, 21000, 20),
            ("Thai Tea", "Teh", 12000, 16000, 30),
            ("Lemon Tea", "Teh", 10000, 14000, 30),
            ("Teh Tarik", "Teh", 12000, 16000, 25),
            ("Es Teh Manis", "Teh", 6000, 9000, 40),
        ]
        c.executemany(
            "INSERT INTO menu (nama, kategori, harga_reguler, harga_large, stok, gambar) VALUES (?,?,?,?,?,'')",
            contoh,
        )
    conn.commit()
    conn.close()


init_db()


def rupiah(x):
    return "Rp " + f"{int(x):,}".replace(",", ".")


def gambar_svg(nama, kategori, tinggi=140):
    """Ilustrasi gelas minuman (SVG) yang dibuat otomatis, tanpa perlu internet."""
    n = str(nama).lower()
    peta = [
        ("aren", "#b9824f", "#f5e6d3"), ("americano", "#3a2314", None),
        ("caramel", "#c98a45", "#f8ead2"), ("thai", "#e8742c", "#fff1e0"),
        ("lemon", "#f2c94c", None), ("matcha", "#8fbf5a", "#f3f9e8"),
        ("coklat", "#6b3a24", "#f0dccb"), ("alpukat", "#a5d06a", "#e9f5d0"),
        ("mangga", "#ffb62e", None),
    ]
    dasar = {"Kopi": "#6f4a2e", "Teh": "#e3913a", "Susu": "#e9d3c0", "Buah": "#ff8a65"}
    latar = {
        "Kopi": ("#fdebd3", "#f6d1a8"), "Teh": ("#ffe9d1", "#ffd0a0"),
        "Susu": ("#ede7ff", "#d9ccff"), "Buah": ("#e6f7d9", "#c9eeaa"),
    }
    warna, krim = dasar.get(kategori, "#a855f7"), None
    for kunci, w, k in peta:
        if kunci in n:
            warna, krim = w, k
            break
    b1, b2 = latar.get(kategori, ("#f3e8ff", "#fce7f3"))
    uid = zlib.crc32(f"{nama}{kategori}".encode()) & 0xFFFFFF

    cup = "M62 40 L138 40 L130 118 Q129 124 123 124 L77 124 Q71 124 70 118 Z"
    liq = "M63.6 56 L136.4 56 L130 118 Q129 124 123 124 L77 124 Q71 124 70 118 Z"
    x = [
        f'<svg viewBox="0 0 200 140" width="100%" height="{tinggi}" xmlns="http://www.w3.org/2000/svg">',
        f'<defs><linearGradient id="g{uid}" x1="0" y1="0" x2="1" y2="1">',
        f'<stop offset="0" stop-color="{b1}"/><stop offset="1" stop-color="{b2}"/></linearGradient>',
        f'<clipPath id="c{uid}"><path d="{liq}"/></clipPath></defs>',
        f'<rect width="200" height="140" fill="url(#g{uid})"/>',
        '<circle cx="28" cy="30" r="5" fill="#fff" opacity=".6"/>',
        '<circle cx="172" cy="52" r="7" fill="#fff" opacity=".5"/>',
        '<circle cx="165" cy="112" r="4" fill="#fff" opacity=".6"/>',
        '<ellipse cx="100" cy="130" rx="48" ry="6" fill="#000" opacity=".1"/>',
        '<line x1="116" y1="14" x2="106" y2="70" stroke="#ec4899" stroke-width="5" stroke-linecap="round"/>',
        f'<path d="{cup}" fill="#ffffff" fill-opacity=".45"/>',
        f'<g clip-path="url(#c{uid})"><rect x="55" y="56" width="90" height="70" fill="{warna}"/>',
    ]
    if krim:
        x.append(f'<rect x="55" y="56" width="90" height="17" fill="{krim}"/>')
    x += [
        '<rect x="78" y="80" width="18" height="18" rx="4" fill="#fff" opacity=".35" transform="rotate(-12 87 89)"/>',
        '<rect x="104" y="90" width="17" height="17" rx="4" fill="#fff" opacity=".3" transform="rotate(14 112 98)"/>',
        '<rect x="88" y="104" width="15" height="15" rx="4" fill="#fff" opacity=".3" transform="rotate(-6 95 111)"/>',
    ]
    if "thai" in n or "coklat" in n:  # boba
        for cx, cy in [(82, 117), (94, 119), (106, 118), (118, 117), (88, 110), (112, 110)]:
            x.append(f'<circle cx="{cx}" cy="{cy}" r="4.5" fill="#2b1b12"/>')
    x.append("</g>")
    x += [
        f'<path d="{cup}" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-opacity=".9"/>',
        '<path d="M70 52 L75 112" stroke="#fff" stroke-width="3" stroke-linecap="round" opacity=".55"/>',
        '<path d="M64 36 Q100 8 136 36 Z" fill="#fff" fill-opacity=".55" stroke="#fff" stroke-width="2"/>',
        '<rect x="56" y="34" width="88" height="8" rx="4" fill="#fff" opacity=".95"/>',
    ]
    if kategori == "Buah" or "lemon" in n:  # irisan buah di bibir gelas
        x += [
            f'<circle cx="142" cy="42" r="11" fill="{warna}" stroke="#fff" stroke-width="2.5"/>',
            '<path d="M142 33 V51 M133 42 H151 M135.5 35.5 L148.5 48.5 M148.5 35.5 L135.5 48.5" stroke="#fff" stroke-width="1.3" opacity=".8"/>',
        ]
    x.append("</svg>")
    return f'<div style="border-radius:12px;overflow:hidden">{"".join(x)}</div>'


def now_wib():
    return datetime.now(WIB).strftime("%Y-%m-%d %H:%M:%S")


def get_trx(trx_id):
    conn = db()
    df = pd.read_sql("SELECT * FROM transaksi WHERE id = ?", conn, params=(int(trx_id),))
    conn.close()
    return df.iloc[0].to_dict() if not df.empty else None


def _angka(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def buat_struk(t):
    """Teks struk (lebar 34 karakter, cocok untuk printer thermal)."""
    w = 34
    garis = "-" * w
    jumlah = int(t["jumlah"])
    satuan = int(t["total_harga"]) // max(jumlah, 1)
    rincian = f"{jumlah} x {rupiah(satuan)}"
    total = rupiah(t["total_harga"])
    diterima = _angka(t.get("uang_diterima"))
    extra = []
    if diterima > 0:
        dt, kb = rupiah(diterima), rupiah(_angka(t.get("kembalian")))
        extra = ["DITERIMA".ljust(w - len(dt)) + dt, "KEMBALI".ljust(w - len(kb)) + kb]
    baris = [
        "KEDAI MINUMAN UMKM".center(w),
        "Terima kasih sudah mampir!".center(w),
        garis,
        f"No    : #{int(t['id']):05d}",
        f"Waktu : {t['waktu']}",
        f"Nama  : {t['nama_pembeli']}",
        f"Bayar : {t['metode_bayar']}",
        garis,
        f"{t['menu']} ({t['ukuran']})",
        rincian.ljust(w - len(total)) + total,
        garis,
        "TOTAL".ljust(w - len(total)) + total,
        *extra,
        garis,
        "Simpan struk ini sebagai bukti".center(w),
        "pembayaran. Sampai jumpa lagi!".center(w),
    ]
    return "\n".join(baris)


def tampil_struk(t, key):
    teks = buat_struk(t)
    st.markdown(f'<div class="struk">{teks}</div>', unsafe_allow_html=True)
    st.download_button(
        "⬇️ Unduh Struk (.txt)",
        data=teks,
        file_name=f"struk_{int(t['id']):05d}.txt",
        mime="text/plain",
        key=f"dl_{key}",
        use_container_width=True,
    )


def kirim_notif(topik, judul, pesan):
    """Kirim push notification ke HP lewat ntfy.sh (gratis, tanpa akun).
    Judul dikirim sebagai header HTTP, jadi harus huruf biasa (tanpa emoji)."""
    st.session_state.notif_error = ""
    if not topik.strip():
        st.session_state.notif_error = "nama topik kosong"
        return False
    judul = judul.encode("ascii", "ignore").decode().strip() or "Kasir"
    try:
        r = requests.post(
            f"https://ntfy.sh/{topik.strip()}",
            data=pesan.encode("utf-8"),
            headers={"Title": judul, "Priority": "high", "Tags": "coffee,moneybag"},
            timeout=8,
        )
        if not r.ok:
            st.session_state.notif_error = f"server menolak (HTTP {r.status_code})"
        return r.ok
    except Exception as e:
        st.session_state.notif_error = f"{type(e).__name__}: {str(e)[:80]}"
        return False


# ======================================================================
# STYLING
# ======================================================================
st.markdown(
    """
<style>
.block-container {padding-top: 1.5rem;}
.main-header {
    background: linear-gradient(135deg, #6b11ff 0%, #a855f7 55%, #ec4899 100%);
    padding: 26px; border-radius: 18px; color: white; text-align: center;
    margin-bottom: 22px; box-shadow: 0 10px 30px rgba(107,17,255,.25);
}
.main-header h1 {margin: 0; font-size: 2.1rem;}
.main-header p {margin: 4px 0 0; opacity: .9;}
.badge {display:inline-block; padding:2px 10px; border-radius:999px;
        font-size:.75rem; font-weight:600;}
.badge-ok {background:#dcfce7; color:#166534;}
.badge-low {background:#fef3c7; color:#92400e;}
.badge-out {background:#fee2e2; color:#991b1b;}
.harga {font-size:.9rem; color:#6b7280;}
.noimg {height:140px; display:flex; align-items:center; justify-content:center;
        font-size:3.2rem; border-radius:12px;
        background:linear-gradient(135deg,#f3e8ff,#fce7f3);}
.struk {
    font-family: 'Courier New', monospace; white-space: pre; font-size: .85rem;
    background: #fffef7; color: #222; padding: 18px 20px; border-radius: 6px;
    border: 1px dashed #bbb; box-shadow: 0 4px 14px rgba(0,0,0,.12);
    margin-bottom: 10px; overflow-x: auto;
}
div[data-testid="stMetric"] {
    background: linear-gradient(135deg,#faf5ff,#fdf2f8);
    border: 1px solid #e9d5ff; padding: 14px 18px; border-radius: 14px;
}
div.stButton > button[kind="primary"] {
    background: linear-gradient(135deg,#6b11ff,#a855f7); border: none;
}
</style>
<div class="main-header">
    <h1>🧋 Kedai Minuman UMKM</h1>
    <p>Sistem Kasir & Pengelolaan Penjualan Modern</p>
</div>
""",
    unsafe_allow_html=True,
)

# ======================================================================
# SIDEBAR
# ======================================================================
st.sidebar.markdown("### ⚙️ Pengaturan & Navigasi")
role = st.sidebar.radio("Akses Pengguna", ["Kasir", "Pemilik (Owner)"])

st.sidebar.markdown("---")
st.sidebar.markdown("### 🔔 Notifikasi HP")
st.sidebar.text_input(
    "Nama topik ntfy",
    value=DEFAULT_TOPIC,
    key="ntfy_topic",
    help="Pasang aplikasi ntfy di HP, lalu subscribe ke topik yang sama.",
)
if st.sidebar.button("Kirim notifikasi tes", use_container_width=True):
    ok = kirim_notif(
        st.session_state.ntfy_topic, "Tes Kasir", "Notifikasi dari Kedai Minuman UMKM berhasil! 🎉"
    )
    st.sidebar.success("Terkirim ✅") if ok else st.sidebar.error(f"Gagal kirim: {st.session_state.get('notif_error', '')}")


# ======================================================================
# CALLBACK: PROSES PESANAN
# ======================================================================
def set_uang(nominal):
    st.session_state.uang = int(nominal)


def proses_pesanan():
    s = st.session_state
    nama = s.get("nama", "").strip()
    menu_id = s.get("menu_id")
    ukuran = s.get("ukuran", "Reguler")
    jumlah = int(s.get("jumlah", 1))
    metode = s.get("metode", "Tunai (Cash)")
    uang = int(s.get("uang", 0))

    if not nama:
        s.flash = ("error", "Nama pembeli / No. Meja wajib diisi!")
        return
    conn = db()
    cur = conn.cursor()
    row = cur.execute(
        "SELECT nama, harga_reguler, harga_large, stok FROM menu WHERE id = ?", (menu_id,)
    ).fetchone()
    if not row:
        s.flash = ("error", "Menu tidak ditemukan.")
        conn.close()
        return
    nama_menu, h_reg, h_large, stok = row
    if stok < jumlah:
        s.flash = ("error", f"Stok tidak mencukupi! Sisa stok: {stok}")
        conn.close()
        return

    total = (h_large if ukuran == "Large" else h_reg) * jumlah
    if metode.startswith("Tunai"):
        if uang < total:
            s.flash = ("error", f"Uang diterima kurang {rupiah(total - uang)}!")
            conn.close()
            return
        kembalian = uang - total
    else:  # QRIS: dibayar pas
        uang, kembalian = total, 0
    cur.execute("UPDATE menu SET stok = stok - ? WHERE id = ?", (jumlah, menu_id))
    cur.execute(
        """INSERT INTO transaksi (nama_pembeli, menu, ukuran, jumlah, total_harga, metode_bayar,
                                 waktu, uang_diterima, kembalian)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (nama, nama_menu, ukuran, jumlah, total, metode, now_wib(), uang, kembalian),
    )
    trx_id = cur.lastrowid
    conn.commit()
    conn.close()

    # Notifikasi ke HP pemilik
    terkirim = kirim_notif(
        s.get("ntfy_topic", ""),
        "Pesanan Baru!",
        f"{nama} beli {jumlah}x {nama_menu} ({ukuran})\nTotal {rupiah(total)} via {metode}",
    )
    s.struk_id = trx_id
    s.flash = (
        "success",
        f"🎉 Pesanan atas nama {nama} berhasil disimpan!"
        + (f" 💵 Kembalian: {rupiah(kembalian)}." if metode.startswith("Tunai") else "")
        + ("  📲 Notifikasi terkirim." if terkirim else f"  (notifikasi HP gagal: {s.get('notif_error', '')})"),
    )
    s.nama = ""
    s.jumlah = 1
    s.uang = 0


# ======================================================================
# HALAMAN KASIR
# ======================================================================
def halaman_pos():
    st.subheader("🛒 Katalog & Pemesanan")
    conn = db()
    df = pd.read_sql("SELECT * FROM menu WHERE kategori IN ('Kopi','Teh') ORDER BY kategori, nama", conn)
    conn.close()

    if df.empty:
        st.warning("Belum ada menu. Tambahkan dulu di halaman 'Kelola Menu'.")
        return

    kategori = ["Semua"] + sorted(df["kategori"].unique().tolist())
    pilih_kat = st.radio("Kategori:", kategori, horizontal=True)
    df_tampil = df if pilih_kat == "Semua" else df[df["kategori"] == pilih_kat]

    if "menu_id" not in st.session_state or st.session_state.menu_id not in df["id"].values:
        st.session_state.menu_id = int(df["id"].iloc[0])

    kiri, kanan = st.columns([3, 2], gap="large")

    # ---- Katalog kartu menu ----
    with kiri:
        kolom = 3
        rows = list(df_tampil.itertuples())
        for i in range(0, len(rows), kolom):
            cols = st.columns(kolom)
            for col, m in zip(cols, rows[i : i + kolom]):
                with col, st.container(border=True):
                    if m.gambar and str(m.gambar).startswith("http"):
                        try:
                            st.image(m.gambar, use_container_width=True)
                        except Exception:
                            st.markdown(gambar_svg(m.nama, m.kategori), unsafe_allow_html=True)
                    else:
                        st.markdown(gambar_svg(m.nama, m.kategori), unsafe_allow_html=True)
                    st.markdown(f"**{m.nama}**")
                    st.markdown(
                        f'<span class="harga">Reguler {rupiah(m.harga_reguler)} · Large {rupiah(m.harga_large)}</span>',
                        unsafe_allow_html=True,
                    )
                    if m.stok <= 0:
                        badge = '<span class="badge badge-out">Habis</span>'
                    elif m.stok <= 5:
                        badge = f'<span class="badge badge-low">Sisa {m.stok}</span>'
                    else:
                        badge = f'<span class="badge badge-ok">Stok {m.stok}</span>'
                    st.markdown(badge, unsafe_allow_html=True)
                    dipilih = st.session_state.menu_id == m.id
                    if st.button(
                        "✅ Dipilih" if dipilih else "Pilih",
                        key=f"pilih_{m.id}",
                        use_container_width=True,
                        type="primary" if dipilih else "secondary",
                        disabled=m.stok <= 0,
                    ):
                        st.session_state.menu_id = int(m.id)
                        st.rerun()

    # ---- Panel pesanan ----
    with kanan:
        terpilih = df[df["id"] == st.session_state.menu_id].iloc[0]
        with st.container(border=True):
            st.markdown("### 📝 Pesanan Baru")
            st.markdown(gambar_svg(terpilih["nama"], terpilih["kategori"], 110), unsafe_allow_html=True)
            st.markdown(f"Menu: **{terpilih['nama']}** ({terpilih['kategori']})")
            st.text_input("Nama Pembeli / No. Meja", key="nama", placeholder="Contoh: Kak Siti / Meja 03")
            c1, c2 = st.columns(2)
            ukuran = c1.selectbox("Ukuran", ["Reguler", "Large"], key="ukuran")
            maks = max(int(terpilih["stok"]), 1)
            c2.number_input("Jumlah", min_value=1, max_value=maks, value=1, key="jumlah")
            metode = st.selectbox("Metode Pembayaran", ["Tunai (Cash)", "QRIS"], key="metode")

            harga = terpilih["harga_large"] if ukuran == "Large" else terpilih["harga_reguler"]
            total = int(harga) * int(st.session_state.get("jumlah", 1))
            st.info(f"💰 Total Harga: **{rupiah(total)}**")
            if metode.startswith("Tunai"):
                st.number_input("💵 Uang Diterima (Rp)", min_value=0, step=1000, key="uang")
                q = st.columns(4)
                q[0].button("Pas", on_click=set_uang, args=(total,), use_container_width=True)
                q[1].button("20rb", on_click=set_uang, args=(20000,), use_container_width=True)
                q[2].button("50rb", on_click=set_uang, args=(50000,), use_container_width=True)
                q[3].button("100rb", on_click=set_uang, args=(100000,), use_container_width=True)
                uang_now = int(st.session_state.get("uang", 0))
                if uang_now >= total and uang_now > 0:
                    st.success(f"Kembalian: **{rupiah(uang_now - total)}**")
                elif uang_now > 0:
                    st.warning(f"Uang kurang {rupiah(total - uang_now)}")
            st.button(
                "Proses Pembayaran & Cetak Struk",
                type="primary",
                use_container_width=True,
                on_click=proses_pesanan,
            )

            flash = st.session_state.pop("flash", None)
            if flash:
                (st.success if flash[0] == "success" else st.error)(flash[1])

        # Struk terakhir
        if st.session_state.get("struk_id"):
            t = get_trx(st.session_state.struk_id)
            if t:
                st.markdown("#### 🧾 Struk Terakhir")
                tampil_struk(t, "terakhir")


def halaman_kelola_menu():
    st.subheader("📦 Kelola Menu Minuman")
    with st.form("tambah_menu_form", clear_on_submit=True):
        st.markdown("##### ➕ Tambah Menu Baru")
        c1, c2 = st.columns(2)
        nama_menu = c1.text_input("Nama Menu Minuman")
        kategori = c2.selectbox("Kategori", ["Kopi", "Teh"])
        c3, c4, c5 = st.columns(3)
        h_reg = c3.number_input("Harga Reguler (Rp)", min_value=0, step=500)
        h_larg = c4.number_input("Harga Large (Rp)", min_value=0, step=500)
        stok = c5.number_input("Stok Awal", min_value=0, value=10)
        img_url = st.text_input("URL Gambar (Opsional)", placeholder="https://...")
        if st.form_submit_button("Simpan Menu Baru", type="primary"):
            if nama_menu.strip():
                conn = db()
                conn.execute(
                    "INSERT INTO menu (nama, kategori, harga_reguler, harga_large, stok, gambar) VALUES (?,?,?,?,?,?)",
                    (nama_menu.strip(), kategori, h_reg, h_larg, stok, img_url.strip()),
                )
                conn.commit()
                conn.close()
                st.success(f"Menu '{nama_menu}' berhasil ditambahkan!")
                st.rerun()
            else:
                st.error("Nama menu wajib diisi.")

    conn = db()
    df = pd.read_sql("SELECT * FROM menu WHERE kategori IN ('Kopi','Teh') ORDER BY kategori, nama", conn)
    conn.close()

    st.markdown("---")
    st.markdown("##### 📋 Daftar Menu Saat Ini")
    st.dataframe(df, use_container_width=True, hide_index=True)

    if not df.empty:
        st.markdown("##### 🔧 Tambah Stok / Hapus Menu")
        opsi = {f"{r.nama} (stok {r.stok})": int(r.id) for r in df.itertuples()}
        label = st.selectbox("Pilih menu", list(opsi.keys()))
        mid = opsi[label]
        c1, c2, c3 = st.columns([2, 1, 1])
        tambah = c1.number_input("Tambah stok sebanyak", min_value=1, value=10, key="tambah_stok")
        if c2.button("➕ Tambah Stok", use_container_width=True):
            conn = db()
            conn.execute("UPDATE menu SET stok = stok + ? WHERE id = ?", (int(tambah), mid))
            conn.commit()
            conn.close()
            st.rerun()
        if c3.button("🗑️ Hapus Menu", use_container_width=True):
            conn = db()
            conn.execute("DELETE FROM menu WHERE id = ?", (mid,))
            conn.commit()
            conn.close()
            st.rerun()


# ======================================================================
# HALAMAN PEMILIK
# ======================================================================
def halaman_owner():
    if not st.session_state.get("owner_ok"):
        st.subheader("🔐 Masuk sebagai Pemilik")
        pin = st.text_input("Masukkan PIN", type="password")
        if st.button("Masuk", type="primary"):
            if pin == OWNER_PIN:
                st.session_state.owner_ok = True
                st.rerun()
            else:
                st.error("PIN salah.")
        return

    st.subheader("📊 Laporan Omset & Riwayat Transaksi")
    conn = db()
    df = pd.read_sql("SELECT * FROM transaksi ORDER BY id DESC", conn)
    conn.close()

    if df.empty:
        st.info("Belum ada data transaksi yang tercatat.")
        return

    hari_ini = datetime.now(WIB).strftime("%Y-%m-%d")
    df_hari = df[df["waktu"].astype(str).str.startswith(hari_ini)]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Omset", rupiah(df["total_harga"].sum()))
    c2.metric("Omset Hari Ini", rupiah(df_hari["total_harga"].sum()))
    c3.metric("Jumlah Transaksi", f"{len(df)}")
    c4.metric("Gelas Terjual", f"{int(df['jumlah'].sum())}")

    g1, g2 = st.columns(2)
    with g1:
        st.markdown("##### 🏆 Omset per Menu")
        st.bar_chart(df.groupby("menu")["total_harga"].sum())
    with g2:
        st.markdown("##### 💳 Metode Pembayaran")
        st.bar_chart(df.groupby("metode_bayar")["total_harga"].sum())

    st.markdown("---")
    st.markdown("##### 📋 Riwayat Transaksi")
    st.dataframe(df, use_container_width=True, hide_index=True)

    # ---- Lihat struk & hapus pemesan ----
    st.markdown("---")
    st.markdown("##### 🧾 Lihat Struk / 🗑️ Hapus Pemesan")
    opsi = {
        f"#{int(r.id):05d} · {r.nama_pembeli} · {r.menu} · {rupiah(r.total_harga)}": int(r.id)
        for r in df.itertuples()
    }
    label = st.selectbox("Pilih transaksi", list(opsi.keys()))
    trx_id = opsi[label]
    t = get_trx(trx_id)

    kiri, kanan = st.columns(2, gap="large")
    with kiri:
        tampil_struk(t, f"owner_{trx_id}")
    with kanan:
        with st.container(border=True):
            st.markdown(f"**Hapus pesanan atas nama:** {t['nama_pembeli']}")
            st.caption("Menghapus transaksi akan menghapus nama pemesan, data pesanan, dan struknya.")
            kembalikan = st.checkbox("Kembalikan stok menu", value=True)
            yakin = st.checkbox("Saya yakin ingin menghapus")
            if st.button("🗑️ Hapus Pemesan & Struk", type="primary", disabled=not yakin, use_container_width=True):
                conn = db()
                if kembalikan:
                    conn.execute(
                        "UPDATE menu SET stok = stok + ? WHERE nama = ?", (int(t["jumlah"]), t["menu"])
                    )
                conn.execute("DELETE FROM transaksi WHERE id = ?", (trx_id,))
                conn.commit()
                conn.close()
                if st.session_state.get("struk_id") == trx_id:
                    st.session_state.struk_id = None
                st.toast(f"Pesanan {t['nama_pembeli']} dan struknya dihapus", icon="🗑️")
                st.rerun()

    if st.sidebar.button("Keluar (Logout Pemilik)", use_container_width=True):
        st.session_state.owner_ok = False
        st.rerun()


# ======================================================================
# ROUTING
# ======================================================================
if role == "Kasir":
    halaman = st.sidebar.selectbox("Pilih Modul Halaman", ["Kasir & POS", "Kelola Menu"])
    if halaman == "Kasir & POS":
        halaman_pos()
    else:
        halaman_kelola_menu()
else:
    halaman_owner()