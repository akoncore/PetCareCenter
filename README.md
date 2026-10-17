# Pet Care Center

Django REST API for **scheduled veterinary appointments and pet pickup/return** (single-clinic MVP, non-emergency visits).

## Installation

Python 3.12+:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Default local API: `http://127.0.0.1:8000/api/`.

## Accounts and roles

All people sign up through `/api/auth/register/`. Accounts do **not** select a clinic role at registration. Clinic administrators invite users, who accept a one-time invitation once registered with the invited email. Memberships store `clinic_admin`, `clinic_staff` or `clinic_transport`.

Bootstrap the first clinic and its administrator in Django Admin (or create a clinic with your superuser via API). Admin login: `/admin/`.

Authentication endpoints:
- `POST /api/auth/register/`
- `POST /api/auth/login/` → `{"token":"..."}`
- `POST /api/auth/logout/`
- `GET/PATCH /api/auth/me/`

For authenticated requests: `Authorization: Token <token>`.

## API endpoints

| Endpoint | Methods | Purpose |
|---|---|---|
| `/api/clinics/` | GET, POST (superuser) | Clinic catalogue |
| `/api/clinics/{id}/` | GET, PATCH (clinic admin) | Clinic details |
| `/api/clinics/{id}/dashboard/` | GET (clinic staff/admin) | Clinic counters and next bookings |
| `/api/memberships/` | GET, PATCH individual | View/manage existing clinic roles |
| `/api/invitations/` | GET, POST (clinic admin) | Invite staff, obtain one-time token |
| `/api/invitations/accept/` | POST | Accept token with matching email |
| `/api/pets/` | GET, POST, PATCH, DELETE | Owner profiles; clinic staff medical notes |
| `/api/services/` | GET, POST, PATCH, DELETE | Catalogue, admin manages services |
| `/api/appointments/` | GET, POST | View/create bookings |
| `/api/appointments/{id}/reschedule/` | POST | Change appointment time |
| `/api/appointments/{id}/cancel/` | POST | Cancel before confirmed transport |
| `/api/appointments/{id}/complete/` | POST (clinic staff/admin) | Mark visit done |
| `/api/transport/` | GET, POST | View/request pickup and return |
| `/api/transport/{id}/advance/` | POST | Approve/assign driver or update journey status |

Transport status flow: `requested → confirmed → picked_up → at_clinic → returning → completed` (or `requested → rejected`).

Example owner booking payload:

```json
{"clinic": 1, "pet": "pet-uuid", "service": 1, "starts_at": "2026-11-12T09:00:00Z"}
```

Example transport request:

```json
{"appointment": 1, "pickup_address": "Example address", "contact_phone": "+77000000000"}
```

Example staff approval: `{"status":"confirmed","assigned_driver":2}`.

## Tests and deployment caveats

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test apps.users apps.clinics apps.pets apps.booking
```

This repo provides the **backend REST API and Django Admin**, not a React frontend. The attached Word project brief additionally expects owner/clinic web interfaces; these remain future work. Driver schedule/capacity is coordinated manually, as in the MVP specification. For production, configure `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, HTTPS, a durable DB such as PostgreSQL, email delivery, file upload security and appropriate logging. SQLite cannot provide PostgreSQL row-lock guarantees for concurrent overlap checks.
