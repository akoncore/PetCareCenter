# Pet Care Center

Django REST API for **scheduled veterinary appointments and pet pickup/return** (single-clinic MVP, non-emergency visits).

## Installation

Python 3.12+ and Docker Compose (or an existing Redis server):

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
docker compose up -d --wait redis
python manage.py migrate
python manage.py runserver
```

`runserver` now uses Daphne/ASGI and serves both HTTP and WebSocket, including admin static files in development. Create an administrator only when needed with `python manage.py createsuperuser`.

Configuration examples are in [.env.example](.env.example). Export variables in your shell; the file is not loaded automatically. Redis is bound to loopback by Compose. Database 0 is used for the cache, database 1 for channel messages. Redis contains disposable data; the application database remains the source of truth. To stop the local service: `docker compose stop redis`.

Default local API prefix: `/api/`.

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

## Redis cache

Anonymous `GET /api/clinics/` responses are cached for 60 seconds (`CLINIC_CACHE_TTL`; set to `0` to disable). Authenticated requests, requests with query parameters and reads inside database transactions bypass the cache. Personal records and permissions are never cached.

Clinic saves/deletions invalidate the cache **after transaction commit**, including changes made through Django Admin. Versioned keys prevent an earlier in-flight response from overwriting the new generation. Bulk ORM updates and raw SQL bypass model signals: call `transaction.on_commit(invalidate_catalogue)` from `apps.clinics.cache` after such changes. Redis failures fall back to database reads and emit a warning. If invalidation fails, an old cache entry can remain until its TTL expires.

## WebSocket updates

Subscribe to `/ws/appointments/<id>/` or `/ws/transport/<id>/` after obtaining the object ID through REST. The socket is read-only. Send the login token in the **first JSON message within 5 seconds**, never in the URL:

```javascript
// token comes from POST /api/auth/login/; id is an appointment the user can view.
const scheme = location.protocol === "https:" ? "wss" : "ws";
const socket = new WebSocket(`${scheme}://${location.host}/ws/appointments/${id}/`);
socket.onopen = () => socket.send(JSON.stringify({ type: "authenticate", token }));
socket.onmessage = async ({ data }) => {
  const event = JSON.parse(data);
  if (event.type === "ready" || event.type === "changed") {
    const response = await fetch(`/api/appointments/${event.id}/`, {
      headers: { Authorization: `Token ${token}` },
    });
    if (response.ok) renderAppointment(await response.json());
  }
};
```

Messages are `{"type":"ready","resource":"appointment","id":1}` and `{"type":"changed","resource":"appointment","id":1}` (or `resource: "transport"`). Clients may send `{"type":"ping"}` and receive `{"type":"pong"}`. Apply the same pattern to `/api/transport/<id>/`. Implement reconnect with backoff and refetch after every `ready`; refresh periodically as a fallback. Reconnect long-lived sockets at least once per hour.

REST and WebSocket share the same visibility rules. Owners and clinic staff/admins can subscribe to their appointments and transport requests; assigned active drivers can subscribe to their transport requests. Token validity and access are checked again before each event or application ping, so logout, user deactivation or role revocation stops further delivery. Configure exact browser origins using `WEBSOCKET_ALLOWED_ORIGINS` (comma-separated, including scheme and port). Unlisted or missing origins are rejected; non-browser clients must also send an allowed Origin header.

Close codes: `4400` invalid message, `4401` missing/revoked authentication, `4403` inaccessible or missing resource, `1013` Redis temporarily unavailable. The maximum inbound application message is 2 KiB.

Notifications run after a successful commit, including model saves from Admin. Rollbacks emit no events. Payloads contain only object IDs; retrieve current data through REST. Delivery is best effort, with no replay or guaranteed delivery during Redis outages. `QuerySet.update()`, bulk operations and raw SQL bypass signals; use `transaction.on_commit(lambda: publish_change("appointment", appointment_id))` from `apps.booking.events` when those operations need notifications.

## Logging and health checks

Application logs are JSON on stderr, with timestamp, level, event, request ID, route template, HTTP status and duration. Each HTTP response contains `X-Request-ID`. Error logs include exception type and stack locations; request bodies, tokens, headers, query strings, exception messages and local variables are excluded. Set `LOG_LEVEL` to control verbosity; use your deployment's log collector for retention and rotation.

- `GET /health/live/`: process responds (`200`).
- `GET /health/ready/`: checks database query, cache read/write and channel Redis connectivity (`200` when all pass, `503` otherwise).

For an ASGI deployment, run Daphne behind your HTTPS proxy (which must forward WebSocket upgrades):

```bash
daphne -b 127.0.0.1 -p 8000 --access-log /dev/null \
  --websocket_timeout 3600 --websocket-max-message-size 2048 \
  --websocket-max-frame-size 2048 settings.asgi:application
```

The application already logs HTTP requests; disabling Daphne's separate access log avoids recording raw URLs. Configure static/media serving separately outside development. Redis cache and channel URLs may use `rediss://` and injected credentials for a hosted Redis instance; do not expose the development Compose Redis port publicly.

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
python manage.py test apps.users apps.clinics apps.pets apps.booking apps.core
```

Start Redis before running tests. The suite exercises actual Redis caching and channel delivery, transaction rollback/commit behavior, permission revocation, broker failure handling, HTTP logging and readiness. CI starts its own Redis service and uses Redis databases 14/15. Run tests only against a disposable development/test Redis instance.

This repo provides the **backend REST API and Django Admin**, not a React frontend. The attached Word project brief additionally expects owner/clinic web interfaces; these remain future work. Driver schedule/capacity is coordinated manually, as in the MVP specification. For production, configure `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, HTTPS, a durable DB such as PostgreSQL, email delivery, file upload security and appropriate logging. SQLite cannot provide PostgreSQL row-lock guarantees for concurrent overlap checks.
