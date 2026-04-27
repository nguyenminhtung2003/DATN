# Giao An 2: Hieu Toan Dien Project WebQuanLi

## Phan 1. Muc tieu cua giao an

Tai lieu nay duoc viet de ban khong chi "biet web nay co dashboard", ma hieu WebQuanLi o 4 tang:

1. Hieu vai tro cua WebQuanLi trong toan he thong do an.
2. Hieu cong nghe va kieu lap trinh dang duoc dung.
3. Hieu tung module, tung API, tung luong realtime.
4. Hieu cach trinh bay truoc hoi dong bang ngon ngu ky thuat ro rang.

Project duoc phan tich:

- Thu muc project: `D:\CodingAntigravity\CodeEnhance\WebQuanLi`

Tai lieu nay duoc viet theo huong:

- giai thich tu nen tang backend web cho toi luong nghiep vu thuc te
- day cach doc code va noi lai bang loi cua ban
- bo sung cac cau hoi phan bien ma hoi dong de hoi

---

## Phan 2. Ban chat cua WebQuanLi trong do an

Neu Jetson la bo nao tren xe, thi WebQuanLi la trung tam quan tri.

WebQuanLi khong chi la "web hien thi". No la:

- backend nghiep vu
- noi luu du lieu trung tam
- noi xac thuc nguoi dung quan ly
- cau noi giua Jetson va giao dien trinh duyet
- dashboard giam sat realtime

No xu ly 3 nhom viec lon:

1. Quan ly doi xe va tai xe.
2. Nhan va luu su kien tu Jetson.
3. Phat du lieu realtime ra dashboard va gui lenh nguoc lai cho Jetson.

Mot cau mo ta gon de ban noi truoc hoi dong:

> WebQuanLi la he thong backend va giao dien quan ly trung tam. No quan ly xe, tai xe, RFID, anh mat, ket noi voi Jetson qua WebSocket, luu lich su session va canh bao vao co so du lieu, dong thoi cap nhat dashboard theo thoi gian thuc bang SSE.

---

## Phan 3. Tai sao do an can mot web quan ly rieng?

Neu chi co Jetson, he thong van co the canh bao tren xe. Nhung khi lam do an day du, can them lop web quan ly vi 4 ly do:

## 3.1 Quan ly du lieu nghiep vu

Jetson khong phai noi thuan tien de:

- them sua xoa xe
- them tai xe
- gan RFID cho tai xe
- upload anh mat

WebQuanLi giai quyet bai toan quan tri du lieu do.

## 3.2 Giam sat tu xa

Can mot man hinh de biet:

- xe nao dang online
- tai xe nao vua quet the
- co session dang chay hay khong
- vua xay ra canh bao nao
- hardware co khoe hay khong

Do la vai tro cua dashboard.

## 3.3 Luu vet va thong ke

Hoi dong rat hay hoi:

> Neu sau nay can xem lai lich su canh bao, xem tai xe nao bi nhieu, xem xe nao co su co thi xu ly the nao?

Cau tra loi:

> WebQuanLi dong vai tro he thong persistence trung tam. Moi session va alert quan trong deu duoc luu de co the truy vet, loc lich su, thong ke va phan tich sau nay.

## 3.4 Dieu khien thiet bi

WebQuanLi khong chi nhan du lieu. No con co the gui lenh nguoc lai:

- test alert
- update software demo
- sync driver registry

Day la tu duy two-way communication.

---

## Phan 4. Nen tang ly thuyet ban phai nam

## 4.1 Backend web la gi?

Backend la phan xu ly phia may chu:

- nhan HTTP request
- kiem tra quyen truy cap
- doc ghi database
- xu ly nghiep vu
- tra ve HTML hoac JSON

Trong project nay, backend duoc viet bang Python va FastAPI.

## 4.2 API la gi?

API la giao dien lap trinh giua cac thanh phan.

Vi du trong WebQuanLi:

- `GET /api/vehicles` -> lay danh sach xe
- `POST /api/drivers` -> tao tai xe
- `POST /api/drivers/{driver_id}/face` -> upload anh mat
- `GET /api/jetson/{device_id}/driver-registry` -> Jetson lay manifest tai xe

Ban nen noi:

> API la hop dong giao tiep ro rang giua frontend, backend va thiet bi.

## 4.3 ORM la gi?

ORM la cach anh xa bang du lieu trong database thanh class trong code.

O day:

- bang `vehicles` <-> class `Vehicle`
- bang `drivers` <-> class `Driver`
- bang `driver_sessions` <-> class `DriverSession`

Loi ich:

- code doc de hon viet SQL tay cho moi thao tac
- de tao quan he giua cac bang
- phu hop do an can toc do phat trien nhanh

## 4.4 Authentication va Authorization

Hai khai niem nay khac nhau:

- Authentication: ban la ai?
- Authorization: ban duoc phep lam gi?

Trong project:

- dang nhap bang username/password
- tao JWT token
- luu token vao cookie
- moi request can user thi doc token de xac thuc
- nhung API quan tri nhay cam thi buoc phai la admin

## 4.5 WebSocket va SSE khac nhau the nao?

Day la cau hoi cuc hay cho hoi dong.

### WebSocket

- ket noi 2 chieu
- phu hop cho Jetson <-> backend
- Jetson vua gui event len, vua nhan command xuong

### SSE

- mot chieu tu server -> browser
- trinh duyet dang dashboard chu yeu can nhan event realtime
- don gian hon WebSocket cho browser trong bai toan nay

Mot cau tra loi de nho:

> WebSocket duoc dung o tang thiet bi vi can giao tiep hai chieu. SSE duoc dung o tang dashboard vi browser chu yeu can nhan stream su kien mot chieu, cach nay don gian va on dinh hon.

## 4.6 Server-side rendering la gi?

WebQuanLi khong phai SPA kieu React phuc tap. No dung Jinja2 de render HTML tren server.

Y nghia:

- backend tao HTML
- browser nhan HTML da render san
- giao dien admin don gian, de trien khai, de debug

Day la lua chon thuc dung cho do an.

---

## Phan 5. Cong nghe duoc chon va vi sao chon nhu vay

## 5.1 Python

WebQuanLi dung Python vi:

- dong bo ngon ngu voi Jetson
- de hoc, de mo rong
- co he sinh thai backend rat manh
- toi uu cho do an can toc do phat trien nhanh

## 5.2 FastAPI

FastAPI la framework backend hien dai cho Python.

Ly do chon:

- support async tot
- support WebSocket san
- support Pydantic cho validation schema
- to chuc router dep, ro

Trong do an nay, FastAPI giup ket hop duoc:

- page route
- JSON API
- WebSocket
- lifecycle startup

## 5.3 SQLAlchemy

SQLAlchemy giup:

- dinh nghia model du lieu
- tao quan he giua bang
- query co cau truc
- tach logic database khoi logic route

Ban khong nen noi "em dung SQLAlchemy vi no hien dai". Ban nen noi:

> Em dung SQLAlchemy de ORM hoa du lieu nghiep vu thanh object Python, giup tang toc do phat trien va de quan ly quan he xe - tai xe - session - alert.

## 5.4 SQLite

SQLite phu hop phien ban do an vi:

- nhe
- khong can server database rieng
- de dong goi demo
- du cho quy mo mot phong bao ve

Gioi han:

- khong ly tuong cho tai lon
- khong manh bang PostgreSQL trong he thong nhieu nguoi dung

Ban co the noi:

> Em chon SQLite cho ban demo de giam do phuc tap van hanh. Neu phat trien len he thong thuc te, co the nang cap sang PostgreSQL ma khong can doi qua nhieu logic nghiep vu.

## 5.5 Jinja2 Templates

Jinja2 duoc dung de render:

- `login.html`
- `dashboard.html`
- `fleet.html`
- `history.html`
- `statistics.html`

Lua chon nay phu hop vi:

- giao dien la giao dien admin noi bo
- khong can frontend framework nang
- de trinh bay trong do an

## 5.6 Pydantic

Pydantic duoc dung trong `schemas.py` de validate du lieu.

Vi du:

- `VerifyErrorData`
- `VerifySnapshotData`
- `DriverData`
- `WsCommandOut`

Day la diem rat quan trong de bao ve:

> Du lieu realtime tu Jetson khong nen tin mu quang. WebQuanLi dung schema validation de chan payload sai contract, giup dashboard va nghiep vu on dinh hon.

---

## Phan 6. Kien truc tong the cua project

Ban co the nhin project theo 6 lop:

1. Lop cau hinh va startup
2. Lop database va model
3. Lop auth va bao ve truy cap
4. Lop API va page routes
5. Lop realtime
6. Lop service nghiep vu

Thu muc `app/` duoc chia nhu sau:

- `app/main.py`: khoi dong FastAPI
- `app/config.py`: cau hinh he thong
- `app/database.py`: ket noi DB va session
- `app/models.py`: model ORM
- `app/schemas.py`: schema validate
- `app/auth/`: dang nhap va phan quyen
- `app/api/`: page routes va API routes
- `app/ws/`: xu ly WebSocket tu Jetson
- `app/core/`: event bus noi bo
- `app/services/`: nghiep vu bo tro

Neu hoi dong hoi "kien truc nay la kien truc gi?" ban co the tra loi:

> Day la kien truc backend monolith nho, chia module theo trach nhiem: route tiep nhan request, service xu ly nghiep vu, ORM lam viec voi database, websocket xu ly thiet bi, event bus lam cau noi realtime den dashboard.

---

## Phan 7. `app/main.py` - diem vao cua he thong

File `app/main.py` la noi khoi tao ung dung FastAPI.

No lam 4 viec chinh:

1. Cau hinh logging.
2. Tao `FastAPI` app voi lifecycle `lifespan`.
3. Mount thu muc static.
4. Nap toan bo router.

### 7.1 Lifecycle startup

Trong `lifespan`, project goi `init_db()`.

Y nghia:

- dam bao bang du lieu ton tai
- dam bao thu muc data/upload duoc tao
- seed user admin mac dinh
- seed mot vehicle demo mac dinh

Ban nen nho:

> Startup cua web khong chi la "mo server", ma la pha dam bao moi tai nguyen can thiet cho nghiep vu da san sang.

### 7.2 Router aggregation

Sau startup, `main.py` include nhieu router:

- auth
- dashboard
- vehicles
- alerts
- sessions
- control
- sse
- pages
- ws

Dieu nay cho thay he thong khong don tat ca vao mot file.

---

## Phan 8. `app/database.py` - nen tang lam viec voi CSDL

File nay chua 4 phan quan trong:

1. Tao async engine
2. Tao session factory
3. Dinh nghia base class cho ORM
4. Tao `get_db()` va `init_db()`

## 8.1 Async engine

Project dung SQLAlchemy async.

Y nghia:

- phu hop FastAPI async
- tranh block event loop khi xu ly nhieu request I/O

## 8.2 `get_db()`

`get_db()` la dependency de router co session database.

Mau tu duy:

- route muon query DB thi `Depends(get_db)`
- session duoc mo va dong dung cach

## 8.3 `init_db()`

Ham nay:

- import model de metadata duoc dang ky
- tao thu muc data va upload
- tao bang neu chua co
- seed admin user
- seed vehicle demo

Day la ly do project moi clone ve van co the chay demo nhanh.

## Phan 9. `app/models.py` - trai tim du lieu nghiep vu

Day la file cuc ky quan trong.

Ban can hieu tung bang theo nghiep vu, khong chi theo cot du lieu.

## 9.1 `User`

Luu:

- `username`
- `hashed_password`
- `role`
- `created_at`

Vai tro:

- quan ly nguoi dang nhap vao web
- tach user he thong khoi driver ngoai doi

Dieu nay rat quan trong. `User` khong phai `Driver`.

## 9.2 `Vehicle`

Luu:

- bien so xe
- ten xe
- `device_id`
- so dien thoai quan ly
- trang thai active

### Tai sao `device_id` quan trong?

`device_id` la khoa noi giua:

- xe trong database
- Jetson vat ly dang ket noi qua WebSocket

No cho phep backend tra loi:

- Jetson nay la cua xe nao?
- event nay can day vao dashboard nao?
- lenh nay can gui nguoc ve thiet bi nao?

## 9.3 `Driver`

Luu:

- ten
- tuoi
- gioi tinh
- so dien thoai
- `rfid_tag`
- `face_image_path`
- `vehicle_id`
- `is_active`

Day la bang cho thay duoc mo hinh nghiep vu cua do an:

- moi tai xe co the RFID
- co anh mat de dong bo xuong Jetson
- co the duoc gan vao mot xe

## 9.4 `HardwareStatus`

Luu tinh trang:

- nguon
- cellular
- GPS
- camera
- RFID
- speaker

Bang nay giup dashboard giam sat suc khoe he thong.

## 9.5 `DriverSession`

Bang nay luu lan xe duoc mo session boi mot tai xe.

Cot chinh:

- `vehicle_id`
- `driver_id`
- `checkin_at`
- `checkout_at`

Khi `checkout_at` la `None`, do la session dang active.

## 9.6 `SystemAlert`

Bang nay luu canh bao:

- loai alert
- muc alert
- EAR/MAR/pitch neu co
- toa do neu co
- snapshot neu co
- message
- timestamp

Day la bang co gia tri de thong ke va bao cao.

## 9.7 Enum `AlertType` va `AlertLevel`

Project khong luu string tuy y cho alert, ma dung enum:

- `DROWSINESS`
- `FACE_MISMATCH`
- `TEST`

Va:

- `LEVEL_1`
- `LEVEL_2`
- `LEVEL_3`
- `CRITICAL`

Day giup du lieu chat che hon, tranh sai chinh ta nghiep vu.

---

## Phan 10. `app/schemas.py` - hop dong du lieu

Neu `models.py` la hop dong voi database, thi `schemas.py` la hop dong voi request/response va WebSocket payload.

## 10.1 Nhom schema CRUD

Gom:

- `DriverCreate`
- `DriverUpdate`
- `VehicleCreate`
- `VehicleUpdate`

Tac dung:

- kiem tra du lieu gui len API
- tranh route nhan payload thieu key hoac sai kieu

## 10.2 Nhom schema realtime

Rat quan trong cho do an:

- `DriverData`
- `VerifyErrorData`
- `VerifySnapshotData`
- `HardwareData`
- `AlertData`
- `SessionStartData`
- `SessionEndData`
- `WsCommandOut`

Day la lop khoa contract giua Jetson va WebQuanLi.

### Vi sao day la diem manh?

Vi backend khong tin payload "gui sao cung duoc".
No validate du lieu den tu Jetson.

Vi du:

- `verify_error.reason` chi cho phep:
  - `MISSING_VERIFIER`
  - `LOW_CONFIDENCE`
  - `NO_FACE_FRAME`
  - `NO_ENROLLMENT`
  - `UNKNOWN_ERROR`

- `verify_snapshot.status` chi cho phep:
  - `DEMO_VERIFIED`
  - `VERIFIED`
  - `MISMATCH`

Ban nen nhan manh voi hoi dong:

> Trong he thong phan tan, contract du lieu la rat quan trong. Em da khoa chat enum cho cac event nhay cam de giam nguy co sai lech giua ben thiet bi va ben dashboard.

---

## Phan 11. Authentication va Authorization

Hai file can nam:

- `app/auth/router.py`
- `app/auth/dependencies.py`

## 11.1 Luong dang nhap

`GET /login` -> hien form dang nhap.

`POST /login`:

1. Lay form tu request
2. Tim `User` trong database
3. Verify password hash
4. Tao JWT token
5. Luu vao cookie `access_token`
6. Redirect ve dashboard

## 11.2 Tai sao dung cookie thay vi luu local storage?

Trong project nay, cookie co y nghia:

- hop voi web admin server-rendered
- trinh duyet gui kem cookie tu dong
- de bao ve route qua dependency

## 11.3 `get_current_user`

Dependency nay:

- doc cookie `access_token`
- decode JWT
- tim user tu database
- neu loi thi redirect ve `/login`

Day la ly do page route va API route deu co the duoc bao ve thong nhat.

## 11.4 `check_admin`

Dependency nay dung cho cac route nhu:

- tao xe
- cap nhat xe
- tao tai xe
- upload anh mat
- gui lenh control

Y nghia:

- viewer co the xem
- admin moi duoc sua va dieu khien

---

## Phan 12. `app/api/pages.py` - lop giao dien trang

File nay phuc vu render HTML.

No gom nhung page chinh:

- `/history`
- `/fleet`
- `/statistics`

## 12.1 `fleet_page`

No tai:

- danh sach vehicle
- danh sach driver

Sau do render `fleet.html`.

Trang nay la noi admin:

- xem xe
- xem tai xe
- quan ly mapping xe - tai xe - RFID

## 12.2 `history_page`

Trang nay cho xem lich su alert voi:

- bo loc ngay
- bo loc xe
- bo loc loai canh bao
- phan trang

Y nghia nghiep vu:

- sau khi demo, co the xem lai he thong da phat hien gi
- phuc vu bao cao, thong ke, truy vet

## 12.3 `statistics_page` va `/api/statistics/summary`

Trang statistics la man hinh thong ke.

API summary tinh:

- so alert theo ngay
- ban do nhiet theo gio
- top driver bi nhieu alert
- tong so session
- tong gio lai xe
- trung binh gio moi session

Day la diem rat dep khi bao ve, vi no cho thay du an khong chi canh bao tuc thoi ma con co tang phan tich.

---

## Phan 13. `app/api/dashboard.py` - trang tong quan

Trang `/` la dashboard chinh.

No lay:

- danh sach xe active
- vehicle mac dinh dang xem
- `device_id`
- cached state tu event bus
- active session hien tai
- recent alerts
- latest hardware status

### Diem kien truc can hieu

Dashboard khong chi phu thuoc vao database.
No con ket hop:

- du lieu persistent tu DB
- du lieu realtime trong bo nho tu event bus

Noi cach khac:

- DB cho lich su va trang thai co luu vet
- event bus cho "hien tai dang dien ra cai gi"

---

## Phan 14. `app/api/vehicles.py` - module quan tri xe, tai xe, anh mat, registry

Day la mot trong nhung file quan trong nhat cua project.

No chua 4 cum nghiep vu:

1. Quan ly xe
2. Quan ly tai xe
3. Upload anh mat
4. Build va sync driver registry xuong Jetson

## 14.1 Quan ly xe

API:

- `GET /api/vehicles`
- `POST /api/vehicles`
- `PUT /api/vehicles/{vehicle_id}`

No dam bao:

- bien so xe khong trung
- `device_id` khong trung

Day la ly do `_ensure_unique_vehicle()` ton tai.

## 14.2 Quan ly tai xe

API:

- `GET /api/drivers`
- `POST /api/drivers`
- `PUT /api/drivers/{driver_id}`

No dam bao `rfid_tag` khong trung.

Y nghia:

- mot the RFID phai anh xa ro rang den mot tai xe

## 14.3 Upload anh mat

API:

- `POST /api/drivers/{driver_id}/face`

No lam:

1. Kiem tra driver ton tai
2. Kiem tra content-type
3. Kiem tra kich thuoc file
4. Luu file vao `static/faces`
5. Ghi `face_image_path` vao DB
6. Neu driver da gan xe thi tu dong ban lenh sync registry xuong Jetson

Day la logic rat hay de ban trinh bay:

> Khi quan ly vien upload anh mat moi cho tai xe, backend khong chi luu file, ma con chu dong kich hoat viec dong bo xuong thiet bi dang online. Nhu vay luong nghiep vu lien mach hon.

## 14.4 Build driver registry manifest

API:

- `GET /api/jetson/{device_id}/driver-registry`

Manifest tra ve:

- `device_id`
- `generated_at`
- danh sach driver
  - `name`
  - `rfid_tag`
  - `face_image_url`

Logic chon driver:

- xe phai active
- driver phai gan dung xe
- driver phai active
- driver phai co `face_image_path`

Day la "single source of truth" cho Jetson.

## 14.5 Dispatch sync command

API:

- `POST /api/vehicles/{vehicle_id}/sync-driver-registry`

No se:

- kiem tra xe ton tai
- kiem tra Jetson co dang online trong `manager.active` hay khong
- neu online, gui lenh:
  - `action = sync_driver_registry`
  - `manifest_url = ...`

Day la diem ket noi truc tiep giua web va thiet bi.

---

## Phan 15. `app/api/control.py` - gui lenh dieu khien xuong Jetson

File nay xu ly cac thao tac dieu khien:

- upload update file demo
- test alert
- log test alert

## 15.1 Tai sao no ton tai?

Vi he thong khong chi "monitor", ma con "control".

## 15.2 Test alert

Khi admin bam nut test:

- web gui command qua WebSocket xuong Jetson
- Jetson co the bat/tat buzzer hoac co che canh bao demo

Y nghia:

- giup demo nhanh truoc hoi dong
- giup kiem tra ket noi 2 chieu dang hoat dong

## 15.3 Upload update

Trong do an hien tai, update software chi la demo-safe.

Ban nen noi that:

> Chuc nang upload update hien tai duoc giu o muc mo phong cap nhat phan mem phuc vu demo, chua phai co che OTA production-day du co hash, rollback va system service management.

Noi thang nhu vay se duoc danh gia tot hon noi qua.

---

## Phan 16. `app/api/alerts.py` va `app/api/sessions.py`

Hai file nay phuc vu truy van du lieu nghiep vu.

## 16.1 Alerts API

`GET /api/alerts`

Ho tro:

- filter theo ngay
- filter theo xe
- filter theo loai alert
- pagination

No tra ve JSON phu hop cho page history hoac mo rong API sau nay.

## 16.2 Sessions API

`GET /api/vehicles/{vehicle_id}/sessions`
`GET /api/vehicles/{vehicle_id}/sessions/active`

Tac dung:

- xem lich su ca lai xe
- xem xe co dang co session active hay khong

Day la du lieu nghiep vu cot loi, vi alert nen duoc dat trong boi canh mot session cu the.

## Phan 17. `app/core/event_bus.py` - cau noi WebSocket -> SSE

Day la file cuc ky quan trong de hieu realtime.

Neu khong co event bus, backend se rat kho:

- nhan event tu Jetson qua WebSocket
- roi lap tuc day sang browser dang mo dashboard

## 17.1 Event bus dang lam gi?

No la bo dem trong bo nho:

- WebSocket handler publish event vao channel theo `vehicle:{device_id}`
- SSE endpoint subscribe channel do
- browser nhan event theo dong stream

## 17.2 Tai sao phai cache state?

`event_bus` co `_vehicle_state`.

Muc dich:

- khi browser vua mo dashboard
- no co the nhan ngay state gan nhat
- khong can doi den event moi tiep theo

Day la mot chon lua kien truc rat thuc dung.

## 17.3 Backpressure va queue

Moi subscriber co mot `Queue(maxsize=50)`.

Neu browser doc cham:

- event cu co the bi bo bot
- event moi duoc uu tien day vao

Do la co che tranh nghen bo nho.

Ban nen nho:

> Trong realtime dashboard, gia tri cao nhat la state moi nhat, khong phai giu moi frame hay moi event nho. Vi vay event bus dung queue gioi han va uu tien du lieu moi.

---

## Phan 18. `app/api/sse.py` - streaming du lieu ra browser

SSE endpoint:

- `GET /sse/vehicle/{device_id}`

No:

1. Subscribe vao channel cua xe
2. Cho event moi tu queue
3. Format theo chuan `text/event-stream`
4. Gui keepalive neu tam thoi khong co event
5. Unsubscribe khi browser ngat ket noi

### Vi sao phai co keepalive?

Vi stream lau co the bi reverse proxy hoac trinh duyet cho la "chet".

Keepalive giup:

- giu ket noi song
- dashboard on dinh hon

---

## Phan 19. `app/ws/jetson_handler.py` - diem tiep nhan thiet bi

Day la file quan trong nhat cua WebQuanLi ve mat ket noi thiet bi.

No co 3 trach nhiem lon:

1. Quan ly ket noi Jetson
2. Validate va xu ly event tu Jetson
3. Publish event sang dashboard va ghi DB khi can

## 19.1 `ConnectionManager`

Class nay luu:

- `active`: danh sach WebSocket dang online theo `device_id`
- `last_seen`: lan cuoi thay thiet bi
- `_offline_tasks`: task xu ly offline timeout

No cho phep:

- biet xe nao dang online
- gui command nguoc lai cho dung thiet bi
- xu ly truong hop mat ket noi

## 19.2 Ket noi WebSocket `/ws/jetson/{device_id}`

Khi Jetson ket noi:

1. backend accept WebSocket
2. tra `device_id` trong DB
3. lay `vehicle.id`, `manager_phone`, `plate_number`
4. neu `device_id` chua dang ky thi dong ket noi
5. publish event `connection = online`

Dieu nay cho thay backend khong cho thiet bi la ket noi vo danh.

## 19.3 Hai nhom message

Day la diem kien truc rat dep:

### Nhom A: msg toc do cao hoac chi de realtime

Gom:

- `driver`
- `gps`
- `ota_status`
- `verify_error`
- `verify_snapshot`

Nhom nay:

- validate schema
- publish vao event bus
- khong bat buoc ghi DB

Ly do:

- de dashboard thay ngay
- giam tai database
- phan biet su kien diagnostic voi du lieu nghiep vu can luu vet

### Nhom B: msg can nghiep vu va persistence

Gom:

- `hardware`
- `session_start`
- `session_end`
- `alert`
- `face_mismatch`

Nhom nay:

- validate schema
- ghi vao database neu can
- publish event de dashboard cap nhat

Day la cach tach "realtime transient" va "business persistence".

## 19.4 Xu ly `driver`

Khi Jetson gui:

```json
{
  "type": "driver",
  "data": {
    "name": "...",
    "rfid": "..."
  }
}
```

Backend co the enrich them:

- ten tai xe neu chua co
- `face_image_path`
- `driver_phone`
- `driver_age`
- `driver_gender`

Du lieu enrich nay giup dashboard hien thi dep hon ma khong bat Jetson phai gui tat ca.

## 19.5 Xu ly `session_start`

Khi Jetson gui `session_start`:

1. validate payload
2. tim driver theo RFID
3. neu khong tim thay -> publish `verify_error UNKNOWN_ERROR`
4. neu tim thay -> tao hoac tai su dung session
5. publish event `session_start` da enrich thong tin tai xe

Day la noi session duoc "chinh thuc hoa" o backend.

## 19.6 Xu ly `session_end`

Backend dong session dang active cua xe.

Neu co session:

- gan `checkout_at`
- publish event `session_end`

## 19.7 Xu ly `alert`

Backend:

- map muc `WARNING/DANGER/CRITICAL` sang enum noi bo
- tim session active
- tao `SystemAlert`
- publish event `alert`

Day la luong canh bao buon ngu.

## 19.8 Xu ly `face_mismatch`

Day la su kien nhay cam.

Khi backend nhan `face_mismatch`:

- validate payload
- tao `SystemAlert` loai `FACE_MISMATCH`
- muc `CRITICAL`
- publish event realtime
- neu co so dien thoai quan ly thi co the gui SMS

Ban nen nhan manh voi hoi dong:

> `face_mismatch` chi duoc dung cho nghi ngo sai nguoi lai, khong dung cho loi he thong nhu thieu verifier hay khong co frame. Dieu nay giup phan cap nghiem trong dung nghiep vu.

## 19.9 Xu ly offline timeout

Neu Jetson disconnect:

- backend publish `connection = offline`
- tao background task
- sau 5 phut neu van offline thi dong session dang mo

Do la co che fail-safe muc backend.

---

## Phan 20. `app/services/jetson_session_service.py` - tach nghiep vu session khoi websocket

File nay chua cac ham:

- `resolve_driver_by_rfid`
- `get_active_session`
- `start_or_reuse_session`
- `close_active_session`
- `create_drowsiness_alert`

Tai sao tach ra service?

Vi `ws/jetson_handler.py` da qua nhieu trach nhiem neu vua nhan socket vua viet het nghiep vu.

Tach service giup:

- de test hon
- de doc hon
- co the tai su dung logic session/alert

### `start_or_reuse_session`

Ham nay kha hay:

- neu da co session active cung driver -> tai su dung
- neu dang co session active cua driver khac -> dong session cu va mo session moi

Day la logic nghiep vu thuc te.

### `create_drowsiness_alert`

Ham nay gan alert voi:

- vehicle
- driver dang active neu co
- session dang active neu co

Y nghia:

- alert khong bi "treo" vo chu
- lich su sau nay de truy vet hon

---

## Phan 21. Luong nghiep vu tong the tu Jetson den dashboard

Bay gio la phan ban bat buoc phai hieu de bao ve.

## 21.1 Luong xac minh va mo session

1. Tai xe quet RFID tai Jetson.
2. Jetson gui event `driver`.
3. Backend nhan `driver`, enrich thong tin, day sang dashboard.
4. Jetson thuc hien verify mat.
5. Neu thanh cong, Jetson gui `verify_snapshot VERIFIED`.
6. Jetson gui `session_start`.
7. Backend tim driver theo RFID.
8. Backend tao hoac reuse `DriverSession`.
9. Dashboard nhan `session_start` va hien tai xe dang chay.

## 21.2 Luong loi verify

1. Tai xe quet RFID.
2. Jetson khong verify duoc vi:
   - thieu verifier
   - khong co enrollment
   - khong co face frame
   - low confidence
3. Jetson gui `verify_error`.
4. Backend validate schema va publish cho dashboard.
5. Dashboard hien ly do ky thuat, nhung khong ghi sai vao `face_mismatch`.

## 21.3 Luong mismatch that

1. Jetson co du thong tin de verify.
2. Ket qua la `MISMATCH`.
3. Jetson gui `verify_snapshot MISMATCH`.
4. Sau do gui `face_mismatch`.
5. Backend tao `SystemAlert FACE_MISMATCH`.
6. Dashboard hien canh bao nghiem trong.
7. Co the gui SMS cho quan ly.

## 21.4 Luong canh bao buon ngu

1. Jetson phat hien mat mo, ngam lau, ngap dau hoac yawning.
2. Jetson gui `alert`.
3. Backend tao `SystemAlert DROWSINESS`.
4. Dashboard cap nhat realtime.
5. History va statistics co the truy van lai duoc.

## 21.5 Luong upload anh mat va sync registry

1. Admin vao `/fleet`.
2. Tao hoac sua tai xe.
3. Upload anh mat.
4. Web luu file vao `static/faces`.
5. Cap nhat `face_image_path`.
6. Neu tai xe da gan xe va Jetson online:
   - web gui command `sync_driver_registry`
7. Jetson goi `manifest_url`.
8. Jetson tai anh mat ve local cache.
9. FaceVerifier local dung du lieu do de verify.

Day la luong lien thong giua hai project.

---

## Phan 22. Cach doc code WebQuanLi cho nguoi moi

Neu ban muon on bai nhanh ma van co chieu sau, doc theo thu tu nay:

1. `app/main.py`
2. `app/database.py`
3. `app/models.py`
4. `app/schemas.py`
5. `app/auth/router.py`
6. `app/auth/dependencies.py`
7. `app/api/dashboard.py`
8. `app/api/vehicles.py`
9. `app/core/event_bus.py`
10. `app/api/sse.py`
11. `app/ws/jetson_handler.py`
12. `app/services/jetson_session_service.py`

Cach doc:

- doc de hieu "module nay giai quyet bai toan gi"
- sau do moi doc "ham nay lam tung buoc nao"

Khong nen doc theo kieu:

- lao vao tung dong syntax
- roi mat dinh huong nghiep vu

---

## Phan 23. Diem manh ky thuat cua WebQuanLi

Ban nen noi duoc it nhat 6 diem manh sau:

1. Co phan tach ro giua API, auth, realtime, DB, service.
2. Co validate contract du lieu realtime bang Pydantic.
3. Co co che event bus de cau noi WebSocket voi SSE.
4. Co luu session va alert vao DB de phuc vu lich su va thong ke.
5. Co mapping ro giua `device_id`, `vehicle`, `driver`, `rfid_tag`, `face_image_path`.
6. Co co che sync driver registry xuong Jetson theo huong web la source of truth.

Neu hoi dong hoi "diem hay nhat trong kien truc web la gi?" ban co the noi:

> Diem hay nhat la em tach du lieu realtime can hien ngay tren dashboard ra khoi du lieu nghiep vu can luu database. Cac event nhu `verify_error`, `verify_snapshot` duoc xu ly nhu diagnostic realtime, trong khi `session_start`, `alert`, `face_mismatch` moi di vao persistence.

## Phan 24. Gioi han hien tai va cach noi trung thuc

Khong co do an nao hoan hao. Dieu quan trong la noi dung.

## 24.1 Chua phai he thong cloud-scale

Event bus hien tai la in-memory.

Y nghia:

- de trien khai
- phu hop demo
- nhung chua phai distributed bus kieu Redis/Kafka

## 24.2 Database hien tai la SQLite

Hop cho demo, nhung neu nhieu user va nhieu xe:

- nen nang cap sang PostgreSQL

## 24.3 Auth o muc do an

Dang dung JWT cookie va role co ban.

Neu mo rong san pham:

- co the them refresh token
- audit log
- CSRF hardening
- password policy

## 24.4 OTA dang la demo-safe

Khong nen noi day la OTA production.

## 24.5 Event enrich va dashboard tap trung vao 1 xe demo

Khi mo rong nhieu xe cung luc:

- can toi uu dashboard va layout monitoring

Ban nen noi nhu sau:

> Em chu dong gioi han pham vi o muc do an de uu tien tinh on dinh va tinh giai thich duoc. Kien truc da mo duong cho mo rong, nhung phien ban hien tai duoc toi uu cho demo va bao ve.

---

## Phan 25. Cac cau hoi hoi dong hay hoi va cach tra loi

## Cau 1. Tai sao web lai dung ca WebSocket va SSE?

Tra loi:

> Vi Jetson can giao tiep hai chieu voi backend, nen em dung WebSocket. Con dashboard browser chu yeu chi can nhan stream su kien realtime, nen em dung SSE de don gian hoa client va giu ket noi on dinh.

## Cau 2. Tai sao khong dung React hoac SPA?

Tra loi:

> Vi day la he thong quan tri noi bo cho do an. Em uu tien su don gian, toc do trien khai, de debug va de trinh bay. Jinja2 server-rendered dap ung du nhu cau, trong khi van ket hop duoc SSE cho realtime.

## Cau 3. Tai sao luu alert vao database ma verify_error thi khong?

Tra loi:

> Vi `verify_error` chu yeu la diagnostic realtime, co tinh chat ky thuat va tan suat co the cao. Con `alert`, `session_start`, `face_mismatch` la su kien nghiep vu quan trong can luu vet de truy vet va thong ke.

## Cau 4. Tai sao can `device_id`?

Tra loi:

> `device_id` la dinh danh ket noi giua Jetson vat ly va xe trong he thong. Nho do backend biet event den tu xe nao va lenh can gui ve thiet bi nao.

## Cau 5. Tai sao khong de Jetson tu luu het?

Tra loi:

> Jetson xu ly edge va ra quyet dinh nhanh, nhung he thong quan ly can mot noi luu trung tam de xem lich su, thong ke, quan ly fleet va dong bo du lieu tai xe. Vi vay WebQuanLi dong vai tro trung tam persistence va administration.

## Cau 6. Neu Jetson gui payload sai thi sao?

Tra loi:

> Backend validate bang Pydantic schema. Payload sai contract se bi log loi va bo qua, tranh lam hong dashboard hoac gay sai nghiep vu.

## Cau 7. Tai sao co event bus trong bo nho?

Tra loi:

> Event bus trong bo nho la lua chon thuc dung cho quy mo do an. No giup noi WebSocket voi SSE rat nhe, it phu thuoc ha tang. Neu mo rong he thong, em co the thay bang Redis pub/sub hoac message broker.

## Cau 8. Tai sao upload anh mat xong lai sync xuong Jetson?

Tra loi:

> Vi WebQuanLi duoc xem la noi quan ly du lieu chuan. Khi du lieu tai xe thay doi, thiet bi edge can cache lai de verify offline va realtime, nen em bo sung co che sync registry tu web xuong Jetson.

---

## Phan 26. Mau thuyet trinh 2-3 phut cho rieng WebQuanLi

Ban co the noi:

> Trong he thong cua em, WebQuanLi dong vai tro backend va dashboard trung tam. Em phat trien bang Python FastAPI, dung SQLAlchemy va SQLite de quan ly du lieu xe, tai xe, session va canh bao. He thong co lop auth dung JWT cookie de bao ve cac thao tac quan tri. Voi phan realtime, Jetson ket noi len backend bang WebSocket de gui event nhu session, alert, verify_error, verify_snapshot va nhan lenh nguoc lai nhu test alert hay sync registry. Ben trong backend, em dung mot event bus in-memory de chuyen su kien sang SSE, tu do dashboard trong trinh duyet cap nhat theo thoi gian thuc. Mot diem quan trong nua la WebQuanLi la nguon du lieu chuan cho mapping xe - tai xe - RFID - anh mat. Khi admin upload anh mat cho tai xe, backend co the tao manifest va gui lenh de Jetson dong bo du lieu xac minh. Nhu vay web khong chi hien thi, ma con quan tri, luu vet va dieu phoi he thong.

---

## Phan 27. Cach tu on de nho duoc lau

Ban nen hoc theo 4 vong:

### Vong 1: Hoc vai tro tung cum file

Tu hoi:

- `main.py` de lam gi?
- `models.py` de lam gi?
- `schemas.py` de lam gi?
- `jetson_handler.py` de lam gi?

### Vong 2: Hoc luong nghiep vu

Tu ke lai bang mieng:

- tu luc quet RFID den luc mo session
- tu luc co alert den luc vao lich su
- tu luc upload anh den luc Jetson sync

### Vong 3: Hoc phan bien

Tap tra loi cac cau:

- tai sao dung SSE?
- tai sao dung SQLite?
- tai sao khong SPA?
- tai sao khong luu verify_error vao DB?

### Vong 4: Hoc noi bang loi cua chinh ban

Muc tieu cuoi cung khong phai thuoc van.
Muc tieu la ban co the tu dien dat lai.

---

## Phan 28. Checklist tu tin truoc hoi dong

Truoc khi bao ve, ban nen tu check:

- Toi co phan biet duoc `User` va `Driver` khong?
- Toi co giai thich duoc `device_id` dung de lam gi khong?
- Toi co noi duoc vi sao dung WebSocket va SSE song song khong?
- Toi co ke duoc luong `driver -> verify_snapshot -> session_start` khong?
- Toi co noi duoc vi sao `face_mismatch` la event nghiem trong hon `verify_error` khong?
- Toi co noi duoc vai tro cua event bus khong?
- Toi co noi duoc registry sync tu web xuong Jetson khong?
- Toi co noi trung thuc duoc gioi han hien tai khong?

Neu ban tra loi duoc nhung cau nay, ban da hieu WebQuanLi o muc kha vung.

---

## Phan 29. Ket luan de ghi nho

Ban hay nho mot cau tong ket nay:

> WebQuanLi la backend quan tri va giam sat trung tam cua he thong. No quan ly xe, tai xe, RFID va anh mat; tiep nhan du lieu realtime tu Jetson qua WebSocket; day du lieu sang dashboard qua SSE; luu session va canh bao vao co so du lieu; dong thoi gui lenh va dong bo registry xuong thiet bi khi can.

Khi ban noi duoc cau nay va giai thich duoc tung ve sau no, ban se rat tu tin truoc hoi dong.
