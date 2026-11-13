# Crop backend

FastAPI service with PostgreSQL and PostGIS. It provides the partner API, the phone app's update endpoints, and the staff admin site. The phone app does not need this server for diagnosis.

## Run

```bash
cp .env.example .env        # then replace every value
docker compose up -d --build
docker compose exec api python -m app.cli seed
docker compose exec api python -m app.cli publish-content
```

- API docs: http://127.0.0.1:8010/docs
- Admin site: http://127.0.0.1:8010/admin

## Staff commands

Run inside the `api` container with `python -m app.cli`:

| Command | Purpose |
|---|---|
| `seed` | Load plans, classes, advice and sample places |
| `create-key --slug acme --name "Acme" --plan starter` | Create an organisation if needed, and print its API key once |
| `import-places file.csv` | Add places. Columns match `content/sample_places.csv`. |
| `create-worker --slug acme --phone 0772123456 --name "Amina" --role admin` | Add a paid-tier worker who signs in by phone |
| `publish-content` | Build a new content pack for phones |
| `publish-model path/` | Install a trained model folder (`model.tflite`, `model_card.json`), then restart the API |

## Test

The tests need the database container, a `crop_test` database with PostGIS, and a `crop_tester` role.

```bash
docker compose up -d db
docker compose exec db psql -U crop -d crop -c "CREATE DATABASE crop_test"
docker compose exec db psql -U crop -d crop -c "CREATE ROLE crop_tester LOGIN PASSWORD 'test-only' SUPERUSER"
docker compose exec db psql -U crop -d crop_test -c "CREATE EXTENSION postgis"
env -u PYTHONPATH uv run pytest
```

`env -u PYTHONPATH` is only needed on machines where ROS adds its packages to the Python path.

## Paid tier

Workers sign in with a 6-digit code sent to their phone. Only numbers that staff or `create-worker` added can sign in. Farmer records, scan sync and reports need a plan with `worker_tools`. Organisations upgrade by paying with mobile money and sending the transaction reference. Staff check the payment, then use **Approve** on the request in the admin site.

Sign-in codes are written to the server log while `OTP_SENDER=log`. That is for development only. Connect a real SMS or phone-verification provider before real workers sign in.

## Production notes

- Run one server process. The app rate limiter and each model interpreter live in memory.
- Keep access logs off, because query strings can hold partner coordinates.
- Put HTTPS and an upload size limit in front of the service, for example with nginx or Caddy. Set the proxy to forward client IPs, or per-IP limits will apply to the proxy.
- Quality-check limits in `app/config.py` are starting values. Tune them on real phone photos.
