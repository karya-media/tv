# IPTV Playlist Management & Validation System

Sistem untuk mengelola playlist IPTV yang dipecah per kategori, memvalidasi
stream, membandingkan dengan XMLTV EPG, menghasilkan laporan, dan
menerbitkan **satu master playlist** yang selalu bisa diakses lewat **satu
URL tetap** — meskipun sumbernya berupa banyak file kategori terpisah.

## Arsitektur: Clean Architecture

```
src/iptv_manager/
├── domain/           # Entities & ports. Tanpa dependency ke library luar.
├── application/      # Use cases (ImportPlaylist, MergePlaylists, ...).
├── infrastructure/    # Adapter konkret: parser M3U, validator HTTP/FFprobe,
│                      # repository SQLAlchemy, publisher GitHub.
└── interfaces/        # Entrypoint: CLI (dipakai GitHub Actions), REST API,
                        # scheduler.
```

Aturan dependency: `domain -> application -> infrastructure -> interfaces`.
Layer domain tidak pernah tahu soal aiohttp, SQLAlchemy, atau FastAPI —
supaya setiap adapter (misalnya SQLite -> PostgreSQL, atau target publish)
bisa diganti tanpa merombak logic inti.

## Cara kerja "banyak file, satu link"

1. Setiap kategori disimpan sebagai file `.m3u` terpisah di
   `data/categories/`.
2. GitHub Actions menjalankan use case `MergePlaylists`, yang menggabungkan
   semua file kategori menjadi satu `data/master/master.m3u` — sekaligus
   menghapus duplikat dan menormalkan metadata.
3. Master playlist itu diterbitkan ke dua lokasi (bisa dipilih salah satu
   atau keduanya lewat `IPTV_PUBLISH_TARGET`):
   - **Raw GitHub URL** (auto, tanpa build step tambahan):
     `https://raw.githubusercontent.com/<owner>/<repo>/<branch>/data/master/master.m3u`
   - **GitHub Pages** (perlu Pages diaktifkan, sumber dari `docs/`):
     `https://<owner>.github.io/<repo>/master.m3u`
4. Kamu masukkan salah satu URL itu ke aplikasi pemutar (VLC, TiviMate,
   dll) — link-nya tidak pernah berubah, isinya yang otomatis ter-update.

## Status Pengembangan

- [x] **Phase 1** — Arsitektur, struktur folder, konfigurasi, inisialisasi
- [ ] **Phase 2** — Playlist parser, merger, duplicate detection
- [ ] **Phase 3** — Stream validator, XMLTV validator, logo validator
- [ ] **Phase 4** — Report generator, GitHub Actions automation
- [ ] **Phase 5** — Web dashboard, REST API, auth, scheduler

## Instalasi (development)

```bash
python3.13 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # lalu isi IPTV_GITHUB_REPOSITORY dst.
pytest
```
