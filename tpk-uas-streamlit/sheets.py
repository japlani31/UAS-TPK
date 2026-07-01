# -*- coding: utf-8 -*-
"""
Integrasi Google Sheets untuk menyimpan hasil Tugas dan UAS.

Cara kerja:
- Kredensial Service Account disimpan di Streamlit Secrets (st.secrets["gcp_service_account"]).
- Hasil UAS masuk ke spreadsheet TERPISAH dari Tugas (kunci di st.secrets).
- Jika kredensial belum diatur, fungsi mengembalikan status "offline" agar aplikasi
  tetap berjalan dan hasil bisa diunduh manual (CSV/PDF) oleh mahasiswa/dosen.

Lihat README untuk panduan membuat Service Account dan membagikan Sheet.
"""

from datetime import datetime

try:
    import gspread
    from google.oauth2.service_account import Credentials
    _GSPREAD_ADA = True
except Exception:
    _GSPREAD_ADA = False

import streamlit as st

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

# Nama worksheet (tab) di dalam masing-masing spreadsheet
_TAB_UAS = "Hasil_UAS"
_TAB_TUGAS = "Hasil_Tugas"

# Header kolom
_HEADER = ["Waktu", "Nama", "NPM", "Nilai", "Benar", "Total",
           "Pindah_Tab", "Durasi_Detik", "Catatan"]


def _client():
    """Membuat koneksi gspread dari secrets. Mengembalikan None bila belum diatur."""
    if not _GSPREAD_ADA:
        return None
    if "gcp_service_account" not in st.secrets:
        return None
    try:
        creds = Credentials.from_service_account_info(
            dict(st.secrets["gcp_service_account"]), scopes=_SCOPES
        )
        return gspread.authorize(creds)
    except Exception:
        return None


def _buka_worksheet(spreadsheet_key, tab_name):
    """Membuka (atau membuat) tab pada spreadsheet tertentu."""
    gc = _client()
    if gc is None or not spreadsheet_key:
        return None
    try:
        sh = gc.open_by_key(spreadsheet_key)
    except Exception:
        return None
    try:
        ws = sh.worksheet(tab_name)
    except Exception:
        ws = sh.add_worksheet(title=tab_name, rows=1000, cols=len(_HEADER))
        ws.append_row(_HEADER)
    # Pastikan ada header
    try:
        if ws.row_count == 0 or not ws.acell("A1").value:
            ws.append_row(_HEADER)
    except Exception:
        pass
    return ws


def _normalisasi_key(nilai):
    """Menerima kunci polos ATAU URL lengkap Google Sheet, mengembalikan kunci saja."""
    nilai = str(nilai).strip()
    if "/d/" in nilai:
        nilai = nilai.split("/d/", 1)[1].split("/", 1)[0]
    return nilai


def _key_uas():
    return _normalisasi_key(st.secrets.get("uas_spreadsheet_key", ""))


def _key_tugas():
    return _normalisasi_key(st.secrets.get("tugas_spreadsheet_key", ""))


def npm_sudah_mengerjakan(npm, jenis="uas"):
    """Cek apakah NPM sudah pernah menyimpan hasil (satu NPM satu kesempatan)."""
    key = _key_uas() if jenis == "uas" else _key_tugas()
    tab = _TAB_UAS if jenis == "uas" else _TAB_TUGAS
    ws = _buka_worksheet(key, tab)
    if ws is None:
        return False  # mode offline: tidak bisa cek, tidak memblokir
    try:
        kolom_npm = ws.col_values(3)  # kolom C = NPM
        return str(npm).strip() in [x.strip() for x in kolom_npm]
    except Exception:
        return False


def simpan_hasil(nama, npm, nilai, benar, total,
                 pindah_tab=0, durasi_detik=0, catatan="", jenis="uas"):
    """
    Menyimpan satu baris hasil ke Google Sheet.
    Mengembalikan (status, pesan): status True bila tersimpan online, False bila offline.
    """
    key = _key_uas() if jenis == "uas" else _key_tugas()
    tab = _TAB_UAS if jenis == "uas" else _TAB_TUGAS
    ws = _buka_worksheet(key, tab)
    baris = [
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        str(nama).strip(), str(npm).strip(),
        nilai, benar, total, pindah_tab, durasi_detik, catatan,
    ]
    if ws is None:
        return False, "Google Sheet belum tersambung. Hasil belum tersimpan online."
    try:
        ws.append_row(baris, value_input_option="USER_ENTERED")
        return True, "Hasil tersimpan ke Google Sheet dosen."
    except Exception as e:
        return False, f"Gagal menyimpan: {e}"
