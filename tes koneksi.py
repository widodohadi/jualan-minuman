import os
import psycopg2
from dotenv import load_dotenv

# Memuat isi file .env
load_dotenv()

# Mengambil DATABASE_URL dari file .env
DATABASE_URL = os.getenv("DATABASE_URL")

try:
    print("Sedang menghubungkan ke Neon Database...")
    conn = psycopg2.connect(DATABASE_URL)
    cursor = conn.cursor()
    
    # Menjalankan query cek versi
    cursor.execute("SELECT version();")
    db_version = cursor.fetchone()
    
    print("\n✅ KONEKSI BERHASIL!")
    print("Info Database:", db_version[0])
    
    cursor.close()
    conn.close()
except Exception as e:
    print("\n❌ KONEKSI GAGAL:")
    print(e)