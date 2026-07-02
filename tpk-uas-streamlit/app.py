# -*- coding: utf-8 -*-
"""
UAS Teori Pengambilan Keputusan (TPK) - Universitas Muhammadiyah Metro
Ardiansyah Japlani, S.E., M.B.A. - FEB UM Metro.

Aplikasi fokus tunggal: Ujian Akhir Semester Teori Pengambilan Keputusan dengan pengaman anti-contek,
watermark identitas, simpan hasil, dan QR code bukti (Nama + NPM).
"""

import io
import time
import hashlib
import random
import urllib.parse
from datetime import datetime

import streamlit as st
import streamlit.components.v1 as components

# Jembatan JS -> Python untuk membaca hitungan pindah tab dari browser
try:
    from streamlit_javascript import st_javascript
    _JS_ADA = True
except Exception:
    _JS_ADA = False

# ---- Impor bank soal UAS (wajib) ----
import uas_soal

# ---- Impor modul opsional (tidak boleh membuat aplikasi gagal) ----
try:
    import sheets
    _SHEETS_ADA = True
except Exception:
    _SHEETS_ADA = False

# QR code untuk bukti hasil (Nama + NPM)
try:
    import qrcode
    _QR_ADA = True
except Exception:
    _QR_ADA = False

# Pillow untuk membuat kartu hasil (gambar yang bisa disimpan mahasiswa)
try:
    from PIL import Image, ImageDraw, ImageFont
    _PIL_ADA = True
except Exception:
    _PIL_ADA = False


st.set_page_config(page_title="UAS TPK - UM Metro",
                   page_icon="🎓", layout="centered",
                   initial_sidebar_state="collapsed")


# ============================================================
#  UTILITAS
# ============================================================
def seed_dari_npm(npm):
    """Mengubah NPM menjadi angka acak stabil (sama di semua perangkat)."""
    h = hashlib.md5(str(npm).strip().encode("utf-8")).hexdigest()
    return int(h, 16) % (2 ** 32)


def ambil_soal_uas(npm):
    """
    Mengambil paket soal unik untuk satu NPM.
    - Memilih JUMLAH_SOAL_PER_MAHASISWA soal acak dari bank 250.
    - Mengacak urutan opsi tiap soal (bila ACAK_OPSI True).
    Struktur tiap item: {"q": teks, "opts": [(indeks_asli, teks_opsi), ...], "a_asli": indeks_benar}
    """
    rnd = random.Random(seed_dari_npm(npm))
    idx = list(range(len(uas_soal.UAS_BANK)))
    rnd.shuffle(idx)
    pilih = idx[: uas_soal.JUMLAH_SOAL_PER_MAHASISWA]

    paket = []
    for i in pilih:
        q = uas_soal.UAS_BANK[i]
        opts = list(enumerate(q["o"]))  # [(0,'A'),(1,'B'),...]
        if uas_soal.ACAK_OPSI:
            rnd.shuffle(opts)
        paket.append({"q": q["q"], "opts": opts, "a_asli": q["a"]})
    return paket


def suntik_anti_contek():
    """
    Mencegah seleksi teks, salin-tempel, klik kanan, dan pintasan papan ketik,
    baik di desktop MAUPUN di HP (perbaikan callout iOS/Android).
    """
    # 1) CSS: berlaku pada dokumen utama (mematikan seleksi & long-press di HP)
    st.markdown(
        """
        <style>
        html, body, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] * {
            -webkit-user-select: none !important;
            -moz-user-select: none !important;
            -ms-user-select: none !important;
            user-select: none !important;
            -webkit-touch-callout: none !important;   /* mematikan menu long-press HP */
            -webkit-tap-highlight-color: transparent !important;
        }
        /* Kotak input tetap boleh diketik */
        input, textarea { -webkit-user-select: text !important; user-select: text !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    # 2) JS: memblokir event salin/klik-kanan/pintasan + menghitung pindah tab
    components.html(
        """
        <script>
        const d = window.parent.document;
        const blok = ['contextmenu','copy','cut','paste','selectstart','dragstart'];
        blok.forEach(function(ev){
            d.addEventListener(ev, function(e){ e.preventDefault(); return false; }, {capture:true});
        });
        d.addEventListener('keydown', function(e){
            const k = (e.key||'').toLowerCase();
            if ((e.ctrlKey || e.metaKey) && ['c','x','v','a','u','s','p'].indexOf(k) !== -1){
                e.preventDefault(); return false;
            }
            if (e.key === 'PrintScreen'){ e.preventDefault(); }
        }, {capture:true});

        // Hitung berapa kali mahasiswa meninggalkan halaman (pindah tab / pindah aplikasi).
        // Disimpan pada window utama (window.parent.__vtCount) lalu dibaca Python via st_javascript.
        const W = window.parent;
        if (!W.__vtHook){
            W.__vtHook = true;
            if (typeof W.__vtCount === 'undefined') W.__vtCount = 0;
            const naik = function(){ if (W.document.hidden){ W.__vtCount = (W.__vtCount||0) + 1; } };
            W.document.addEventListener('visibilitychange', naik, true);
            // Cadangan untuk sebagian browser HP saat pindah aplikasi
            W.addEventListener('pagehide', naik, true);
        }
        </script>
        """,
        height=0,
    )


def baca_pindah_tab():
    """Membaca jumlah pindah tab langsung dari browser (jembatan JS -> Python)."""
    if not _JS_ADA:
        return 0
    try:
        v = st_javascript("(window.parent.__vtCount)||0", key="vt_read")
        return int(v) if v is not None else 0
    except Exception:
        return 0


def suntik_watermark(nama, npm):
    """
    Menempel watermark Nama + NPM transparan menutupi seluruh layar.
    Pengganti 'anti-screenshot' (yang mustahil di web): bila mahasiswa
    screenshot dan menyebarkan soal, identitasnya ikut tercetak.
    """
    teks = f"{nama} · {npm}"
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' width='320' height='180'>"
        "<text x='20' y='100' fill='%23888888' font-size='18' "
        "font-family='sans-serif' transform='rotate(-30 160 90)'>"
        + urllib.parse.quote(teks) +
        "</text></svg>"
    )
    data_uri = "data:image/svg+xml;utf8," + svg
    st.markdown(
        f"""
        <style>
        #wm-overlay {{
            position: fixed; inset: 0; z-index: 100000;
            pointer-events: none; opacity: 0.22;
            background-image: url("{data_uri}");
            background-repeat: repeat;
        }}
        </style>
        <div id="wm-overlay"></div>
        """,
        unsafe_allow_html=True,
    )


def buat_qr_png(data):
    """Membuat QR code (PNG bytes) berisi data teks. None bila library tak ada."""
    if not _QR_ADA:
        return None
    qr = qrcode.QRCode(box_size=6, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def buat_kartu_hasil(nama, npm, nilai, benar, total, waktu_str):
    """
    Membuat kartu hasil (PNG) yang bisa disimpan mahasiswa:
    berisi identitas, nilai, dan QR code (Nama + NPM).
    """
    if not _PIL_ADA:
        return None
    W, H = 640, 380
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)

    def font(sz, bold=False):
        try:
            nama_f = "arialbd.ttf" if bold else "arial.ttf"
            return ImageFont.truetype(nama_f, sz)
        except Exception:
            return ImageFont.load_default()

    # Bingkai
    d.rectangle([6, 6, W - 7, H - 7], outline="#1f4e79", width=3)
    d.rectangle([6, 6, W - 7, 64], fill="#1f4e79")
    d.text((24, 20), "BUKTI PENGERJAAN UAS TPK", font=font(20, True), fill="white")

    y = 88
    baris = [
        ("Nama", nama),
        ("NPM", npm),
        ("Nilai", str(nilai)),
        ("Benar", f"{benar} / {total}"),
        ("Waktu", waktu_str),
    ]
    for label, val in baris:
        d.text((28, y), f"{label}", font=font(16, True), fill="#333333")
        d.text((150, y), f": {val}", font=font(16), fill="#000000")
        y += 34

    # QR code (Nama + NPM saja)
    qr_png = buat_qr_png(f"{nama}|{npm}")
    if qr_png:
        qr_img = Image.open(io.BytesIO(qr_png)).resize((150, 150))
        img.paste(qr_img, (W - 180, 110))
        d.text((W - 180, 266), "QR: Nama & NPM", font=font(12), fill="#555555")

    d.text((24, H - 40), "FEB Universitas Muhammadiyah Metro · Sah dengan bukti tersimpan di dosen",
           font=font(11), fill="#777777")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ============================================================
#  HALAMAN: UAS (satu-satunya halaman)
# ============================================================
def halaman_uas():
    st.header("🎓 Ujian Akhir Semester (UAS) Teori Pengambilan Keputusan")
    _mesin_ujian(
        judul="UAS",
        jenis="uas",
        durasi_menit=uas_soal.DURASI_UAS_MENIT,
        paket_fn=ambil_soal_uas,
    )


# ============================================================
#  MESIN UJIAN (dipakai Tugas & UAS)
# ============================================================
def _mesin_ujian(judul, jenis, durasi_menit, paket_fn):
    ns = f"{jenis}_"  # namespace session_state

    # ---------- Tahap 1: identitas ----------
    if not st.session_state.get(ns + "mulai"):
        st.markdown(
            f"""
            **Ketentuan {judul}:**
            - Jumlah soal: **{uas_soal.JUMLAH_SOAL_PER_MAHASISWA if jenis=='uas' else 'sesuai bank'}**, setiap mahasiswa berbeda.
            - Waktu: **{durasi_menit} menit**, tidak ada waktu tambahan.
            - Ujian **tidak dapat diulang**. Satu NPM satu kesempatan.
            - Salin-tempel dan klik kanan dinonaktifkan. Perpindahan tab dicatat.
            - Kerjakan sendiri dengan jujur. Allah Maha Melihat.
            """
        )
        nama = st.text_input("Nama lengkap", key=ns + "nama_in")
        npm = st.text_input("NPM", key=ns + "npm_in")
        setuju = st.checkbox("Saya mengerjakan sendiri dengan jujur dan amanah.", key=ns + "setuju")

        if st.button(f"Mulai {judul}", type="primary", key=ns + "btn_mulai"):
            if not nama.strip() or not npm.strip():
                st.error("Nama dan NPM wajib diisi.")
                return
            if not setuju:
                st.error("Centang pernyataan kejujuran terlebih dahulu.")
                return
            # Cek satu NPM satu kesempatan (bila Sheet tersambung)
            if _SHEETS_ADA and sheets.npm_sudah_mengerjakan(npm, jenis=jenis):
                st.error("NPM ini sudah pernah mengerjakan. Ujian tidak dapat diulang.")
                return
            st.session_state[ns + "mulai"] = True
            st.session_state[ns + "nama"] = nama.strip()
            st.session_state[ns + "npm"] = npm.strip()
            st.session_state[ns + "paket"] = paket_fn(npm.strip())
            st.session_state[ns + "start_ts"] = time.time()
            st.session_state[ns + "selesai"] = False
            st.session_state[ns + "vt_reset"] = False  # akan direset di halaman ujian
            st.rerun()
        return

    # ---------- Tahap 3: hasil ----------
    if st.session_state.get(ns + "selesai"):
        _tampilkan_hasil(ns, judul, jenis)
        return

    # ---------- Tahap 2: pengerjaan ----------
    suntik_anti_contek()
    suntik_watermark(st.session_state[ns + "nama"], st.session_state[ns + "npm"])
    # Reset penghitung pindah tab sekali di awal ujian
    if not st.session_state.get(ns + "vt_reset"):
        components.html("<script>window.parent.__vtCount = 0;</script>", height=0)
        st.session_state[ns + "vt_reset"] = True
    paket = st.session_state[ns + "paket"]
    durasi_detik = durasi_menit * 60

    # Timer + deteksi pindah tab dalam FRAGMENT: hanya panel ini yang menyegar
    # tiap detik, sehingga form soal TIDAK ikut dirender ulang (mencegah tampil ganda).
    @st.fragment(run_every=1.0)
    def _panel_timer():
        st.session_state[ns + "pindah_live"] = baca_pindah_tab()
        sisa = int(durasi_detik - (time.time() - st.session_state[ns + "start_ts"]))
        if sisa <= 0:
            _finalisasi(ns, jenis, otomatis=True)
            st.rerun()
        menit, detik = divmod(max(sisa, 0), 60)
        warna = "red" if sisa <= 60 else ("orange" if sisa <= 120 else "green")
        st.markdown(
            f"<div style='position:sticky;top:0;background:#111;padding:8px 12px;border-radius:8px;"
            f"z-index:999;text-align:center;font-size:20px;color:{warna};'>"
            f"⏱️ Sisa waktu: <b>{menit:02d}:{detik:02d}</b></div>",
            unsafe_allow_html=True,
        )
        _p = st.session_state.get(ns + "pindah_live", 0)
        if _p > 0:
            st.warning(f"⚠️ Terdeteksi keluar dari halaman {_p} kali. Aktivitas ini tercatat dan dilaporkan ke dosen.")
    _panel_timer()
    st.caption(f"Peserta: {st.session_state[ns+'nama']} · NPM {st.session_state[ns+'npm']}")
    with st.form(ns + "form_ujian"):
        jawaban = {}
        for i, s in enumerate(paket):
            st.markdown(f"**{i+1}. {s['q']}**")
            teks_opsi = [o[1] for o in s["opts"]]
            pilih = st.radio("", teks_opsi, index=None, key=f"{ns}soal_{i}",
                             label_visibility="collapsed")
            jawaban[i] = pilih
            st.divider()
        kirim = st.form_submit_button("✅ Selesai & Kirim", type="primary")

    if kirim:
        st.session_state[ns + "jawaban_final"] = jawaban
        _finalisasi(ns, jenis, otomatis=False)
        st.rerun()



def _finalisasi(ns, jenis, otomatis):
    """Menghitung nilai, menyimpan ke Sheet, mengunci sesi."""
    paket = st.session_state[ns + "paket"]
    jawaban = st.session_state.get(ns + "jawaban_final", {})
    # Bila submit otomatis, ambil jawaban terakhir dari widget
    if not jawaban:
        jawaban = {}
        for i, s in enumerate(paket):
            teks = st.session_state.get(f"{ns}soal_{i}")
            jawaban[i] = teks

    benar = 0
    for i, s in enumerate(paket):
        teks_pilih = jawaban.get(i)
        if teks_pilih is None:
            continue
        # cocokkan teks pilihan -> indeks asli opsi
        for orig_idx, teks in s["opts"]:
            if teks == teks_pilih:
                if orig_idx == s["a_asli"]:
                    benar += 1
                break

    total = len(paket)
    nilai = round(benar / total * 100, 1) if total else 0
    durasi = int(time.time() - st.session_state[ns + "start_ts"])
    pindah = st.session_state.get(ns + "pindah_live", 0)

    st.session_state[ns + "hasil"] = {
        "benar": benar, "total": total, "nilai": nilai,
        "durasi": durasi, "pindah": pindah, "otomatis": otomatis,
    }

    # Simpan ke Google Sheet
    status, pesan = False, "Mode offline."
    if _SHEETS_ADA:
        catatan = "Waktu habis (auto submit)" if otomatis else "Selesai normal"
        if pindah > 0:
            catatan += f"; pindah tab {pindah}x"
        status, pesan = sheets.simpan_hasil(
            st.session_state[ns + "nama"], st.session_state[ns + "npm"],
            nilai, benar, total, pindah_tab=pindah, durasi_detik=durasi,
            catatan=catatan, jenis=jenis,
        )
    st.session_state[ns + "simpan_status"] = status
    st.session_state[ns + "simpan_pesan"] = pesan
    st.session_state[ns + "selesai"] = True


def _tampilkan_hasil(ns, judul, jenis):
    h = st.session_state[ns + "hasil"]
    st.success(f"{judul} selesai. Terima kasih, {st.session_state[ns+'nama']}.")
    if h["otomatis"]:
        st.warning("Waktu habis. Jawaban dikirim otomatis.")

    c1, c2, c3 = st.columns(3)
    c1.metric("Nilai", h["nilai"])
    c2.metric("Benar", f"{h['benar']}/{h['total']}")
    c3.metric("Waktu", f"{h['durasi']//60}m {h['durasi']%60}d")

    if h["pindah"] > 0:
        st.warning(f"Tercatat berpindah tab / meninggalkan halaman **{h['pindah']} kali**.")

    if st.session_state.get(ns + "simpan_status"):
        st.info("✅ " + st.session_state.get(ns + "simpan_pesan", ""))
    else:
        st.error("⚠️ " + st.session_state.get(ns + "simpan_pesan", "Hasil belum tersimpan online."))
        st.caption("Simpan bukti hasil di bawah dan laporkan ke dosen bila diminta.")

    # ---------- Bukti hasil: QR (Nama + NPM) + kartu unduh ----------
    st.divider()
    st.subheader("Bukti hasil kamu")
    nama = st.session_state[ns + "nama"]
    npm = st.session_state[ns + "npm"]
    waktu_str = datetime.now().strftime("%d-%m-%Y %H:%M")

    kolom_qr, kolom_info = st.columns([1, 2])
    qr_png = buat_qr_png(f"{nama}|{npm}")
    with kolom_qr:
        if qr_png:
            st.image(qr_png, caption="QR: Nama & NPM", width=160)
        else:
            st.caption("QR tidak tersedia (library qrcode belum terpasang).")
    with kolom_info:
        st.write(f"**Nama:** {nama}")
        st.write(f"**NPM:** {npm}")
        st.write("QR ini berisi identitasmu. Tunjukkan/simpan sebagai bukti telah mengerjakan.")

    kartu = buat_kartu_hasil(nama, npm, h["nilai"], h["benar"], h["total"], waktu_str)
    if kartu:
        st.download_button(
            "⬇️ Simpan Kartu Hasil (PNG)",
            data=kartu,
            file_name=f"UAS_{npm}_{nama.replace(' ', '_')}.png",
            mime="image/png",
            type="primary",
        )
    elif qr_png:
        st.download_button(
            "⬇️ Simpan QR (PNG)", data=qr_png,
            file_name=f"QR_{npm}.png", mime="image/png",
        )

    st.caption("Halaman ini terkunci. Ujian tidak dapat diulang.")


# ============================================================
#  APLIKASI (halaman tunggal: UAS)
# ============================================================
def main():
    st.caption("FEB Universitas Muhammadiyah Metro · Ardiansyah Japlani, S.E., M.B.A.")
    halaman_uas()


if __name__ == "__main__":
    main()
