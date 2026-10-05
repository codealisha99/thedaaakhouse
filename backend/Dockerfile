# thedaaakhouse backend — production image foundation.
# NOTE: not built here (Docker daemon unavailable); review before first build.
FROM python:3.12-slim

WORKDIR /srv/app

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/

ENV BACKEND_HOST=0.0.0.0 \
    BACKEND_PORT=8001 \
    DATA_DIR=/srv/app/data \
    ENVIRONMENT=production

EXPOSE 8001

# Migrate, then serve. ENVIRONMENT=production REQUIRES a real JWT_SECRET
# or the process exits (see app/core/config.py).
CMD ["sh", "-c", "python -m alembic -c backend/alembic.ini upgrade head && python -m uvicorn app.main:app --host ${BACKEND_HOST} --port ${BACKEND_PORT} --app-dir backend"]
