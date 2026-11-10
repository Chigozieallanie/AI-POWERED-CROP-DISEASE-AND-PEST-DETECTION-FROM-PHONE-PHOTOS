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

## Production notes

- Run one server process. The app rate limiter and each model interpreter live in memory.
- Keep access logs off, because query strings can hold partner coordinates.
- Put HTTPS and an upload size limit in front of the service, for example with nginx or Caddy. Set the proxy to forward client IPs, or per-IP limits will apply to the proxy.
- Quality-check limits in `app/config.py` are starting values. Tune them on real phone photos.
