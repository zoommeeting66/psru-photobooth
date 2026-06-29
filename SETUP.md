# SETUP — ติดตั้งระบบตามลำดับ (พร้อมใช้งานจริง)

มี 4 ระดับ เลือกตามความต้องการ — แต่ละระดับ "ใช้งานได้จริง" ในขอบเขตของตัวเอง

| ระดับ | ได้อะไร | เวลา | เหมาะกับ |
|-------|---------|------|----------|
| **0. Local Dev** | รันบนเครื่องตัวเอง (SQLite, AI จำลอง) | ~5 นาที | ทดลอง/พัฒนา |
| **1. One-command (Docker)** | ทั้งสแต็กจริง (Postgres+API+Frontend) | ~10 นาที | เดโม/งานอีเวนต์จริง |
| **2. Cloud Deploy** | ขึ้น cloud มี URL สาธารณะ | ~30 นาที | เปิดใช้จริงออนไลน์ |
| **3. Real AI (Phase 2)** | AI สร้างฉากจริง (GPU+Triton) | — | โปรดักชันเต็มรูปแบบ |

> **AI pipeline ปัจจุบันเป็น mock** — สร้าง "ภาพ branded จริง" (โลโก้/กรอบ/QR/ลายน้ำ/หมายเลข)
> ได้โดยไม่ต้องมี GPU เหมาะกับเดโม/บูธ ส่วนการสร้างฉาก AI จริงอยู่ที่ระดับ 3

---

## ระดับ 0 — Local Dev (เร็วสุด)

```bash
# 1) Backend → http://localhost:8000  (เอกสาร API: /docs)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload

# 2) Frontend → http://localhost:3000  (เปิดอีก terminal)
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```
เปิด **http://localhost:3000** → ทดสอบ Kiosk flow ได้เลย
ตรวจระบบ: `cd backend && pytest -q` (11 ผ่าน) · `cd e2e && npm install && npm test`

---

## ระดับ 1 — One-command Docker (แนะนำสำหรับใช้งานจริงบนเครื่องเดียว)

**ต้องมี:** Docker + Docker Compose

```bash
# จาก root ของ repo — build + รันทั้งสแต็ก (Postgres + API + Frontend)
docker compose up --build
```
- Frontend: **http://localhost:3000** · API: **http://localhost:8000/docs**
- ข้อมูลอยู่ใน Postgres (volume `pgdata`), ไฟล์ภาพอยู่ใน `./data`
- Auth เป็น dev mode (หน้า Dashboard เลือก role เข้าสู่ระบบได้)

### เปิด Keycloak (OIDC จริง) — ถ้าต้องการ
```bash
docker compose --profile auth up --build          # เพิ่มบริการ keycloak (:8080)
```
แล้วแก้ใน `docker-compose.yml` ที่ service `api` ปลดคอมเมนต์:
```yaml
OIDC_ISSUER: http://localhost:8080/realms/psru
```
- Keycloak admin: http://localhost:8080 (admin/admin)
- ผู้ใช้เดโมในรีลม `psru` (รหัส = ชื่อผู้ใช้): `admin` / `operator` / `executive`
- สร้างผู้ใช้จริง + เปิด **MFA** (Authentication → Required actions → Configure OTP)

### ก่อนใช้งานจริง (Production hardening)
1. เปลี่ยน `JWT_SECRET`, รหัส Postgres, รหัส Keycloak admin ให้เป็นความลับจริง
2. ตั้ง `PUBLIC_BASE_URL` เป็นโดเมนจริง (https) และจำกัด CORS เป็นโดเมน PSRU
3. วาง reverse proxy + HTTPS (เช่น **Caddy** — ได้ TLS อัตโนมัติ):
   ```
   booth.psru.ac.th     → frontend:3000
   api-booth.psru.ac.th → api:8000
   ```
4. ตั้ง backup ของ Postgres (`pg_dump` รายวัน) และ retention ของโฟลเดอร์ `data`

---

## ระดับ 2 — Cloud Deploy (มี URL สาธารณะ)

ลำดับการ deploy (ทำตามนี้):

1. **ฐานข้อมูล** — สร้าง PostgreSQL แบบ managed (Neon / Supabase / Railway) → ได้ `DATABASE_URL`
   (เปลี่ยน prefix เป็น `postgresql+asyncpg://...`)
2. **Object Storage** *(แนะนำสำหรับหลาย instance)* — S3 / Cloudflare R2 / MinIO
   *(หมายเหตุ: `storage.py` ปัจจุบันเป็น local FS — ถ้า deploy หลาย instance ให้เปลี่ยนเป็น S3 ก่อน, เป็น Phase 2 item; instance เดียวใช้ volume ได้)*
3. **Backend (API)** — deploy ด้วย Docker (`./backend/Dockerfile`) ขึ้น **Render / Railway / Fly.io / VM**
   ตั้ง env: `DATABASE_URL`, `PUBLIC_BASE_URL=https://api-booth...`, `JWT_SECRET`, (ถ้าใช้ OIDC) `OIDC_ISSUER`
4. **Keycloak** *(ถ้าใช้ OIDC)* — deploy แยก หรือใช้ Keycloak managed → import `backend/keycloak/realm-export.json`
   ตั้ง `KC_HOSTNAME` ให้ตรงโดเมนจริง
5. **Frontend** — 2 ทางเลือก:
   - **Vercel** (ง่ายสุด): import repo, root = `frontend/`, ตั้ง env `NEXT_PUBLIC_API_BASE=https://api-booth...`
   - **Docker** (`./frontend/Dockerfile`): build ด้วย `--build-arg NEXT_PUBLIC_API_BASE=https://api-booth...`
6. **CORS** — แก้ `backend/app/config.py` → `cors_origins` ให้มีโดเมน frontend จริง (เลิกใช้ `*`)
7. **ตรวจรับ (smoke test)**:
   ```bash
   curl https://api-booth.psru.ac.th/api/v1/health
   # เปิด frontend → ทดสอบ kiosk flow → ภาพ + QR ขึ้น → login dashboard
   ```

> **GitHub Pages** (ที่เปิดไว้แล้ว) เสิร์ฟ `index.html` แบบ static = โหมดสาธิต (mock) ไม่มี backend
> เหมาะกับโชว์ UI; ถ้าจะให้ทำงานจริงต้องใช้ frontend (Next.js) + backend ตามด้านบน

---

## ระดับ 3 — Real AI Pipeline (Phase 2)

เปลี่ยนจาก mock เป็นโมเดลจริง (อ้างอิง `docs/04-ai-workflow.md`, `docs/07-deployment-architecture.md`):

1. จัดหา **GPU** (on-prem หรือ cloud) + ติดตั้ง **NVIDIA Triton Inference Server**
2. โหลดโมเดล: **SAM 2** (segmentation), **SDXL + ControlNet** (scene), **IC-Light** (relighting), **IP-Adapter** (outfit)
3. ใน `backend/app/pipeline.py` แทนฟังก์ชันแต่ละ stage (ตอนนี้เป็น `await asyncio.sleep`) ด้วยการเรียก Triton
4. เปลี่ยน job queue: `BackgroundTasks` → **Redis + Celery** (มี redis ใน compose แล้ว) + เปลี่ยน WS hub → Redis pub/sub
5. ย้าย storage → **S3/R2** + signed URL · เพิ่ม **autoscale GPU** (KEDA ตาม queue depth)

---

## สรุปลำดับสั้นๆ (เริ่มเลย)

```
อยากลองเร็ว         → ระดับ 0  (uvicorn + npm run dev)
อยากใช้งานจริงในงาน → ระดับ 1  (docker compose up --build)
อยากเปิดออนไลน์      → ระดับ 2  (DB managed → API → Frontend → CORS)
อยาก AI จริง        → ระดับ 3  (GPU + Triton + แก้ pipeline.py)
```

ดูการใช้งานแต่ละหน้าจอที่ [`USAGE.md`](USAGE.md) · สถาปัตยกรรม/ต้นทุน/แผนที่ [`docs/`](docs/)
