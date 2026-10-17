# Pet Care Center — backend MVP (Phase 1)

The project document scopes a **single clinic**, scheduled non-emergency care and manual transport assignment. This branch adds the core API workflow while preserving existing users, pets, clinics, invitations and memberships.

## Start
Install Django, djangorestframework and Pillow in your environment, then run:

```bash
python manage.py migrate
python manage.py test apps.booking
python manage.py runserver
```

Authenticate through Django session login (including DRF browsable API) or configure your preferred token/JWT auth separately.

## API
- `GET /api/services/` — active clinic services
- `GET /api/appointments/` — owner's bookings or clinic staff's bookings
- `POST /api/appointments/` — book pet, service, clinic, starts_at
- `POST /api/appointments/{id}/cancel/` — owner cancels before transport confirmation
- `GET /api/transport/` — allowed transport requests
- `POST /api/transport/` — pickup_address, contact_phone, appointment
- `POST /api/transport/{id}/advance/` — clinic staff confirms/rejects and assigns driver, then assigned driver advances trip

Example advance: `{"status":"confirmed","assigned_driver":3}`. Trip status order: requested → confirmed → picked_up → at_clinic → returning → completed. Rejection can happen from requested.

Services are created via Django Admin. Do not use this demo configuration in production: move secret key to environment, turn off DEBUG, configure ALLOWED_HOSTS and hardened auth.

## Remaining before complete MVP
Add owner registration/login and pet CRUD endpoints, clinic staff dashboard, appointment rescheduling, in-app reminders, driver capacity rules and production-safe concurrent slot enforcement. Backend code and migrations have not been executed in the connected GitHub environment.
