#!/usr/bin/env bash
# Local self-hosted install/update for the Odds app, on a Debian/Ubuntu/
# Raspberry Pi OS machine (anything with apt). No Docker, no cloud hosting,
# no cost — PostgreSQL, the API and the scheduler all run on this machine,
# under systemd, and the API serves the built frontend itself.
#
# Safe to re-run: after `git pull`, running this again picks up new Python
# deps, applies new migrations, rebuilds the frontend, and restarts the
# services with whatever changed. It never overwrites backend/.env once it
# exists, so your ODDS_API_KEY and any tuning you've done are preserved.
#
# Usage:
#   ./install.sh                 # first install, or update after git pull
#   DB_NAME=... DB_USER=... DB_PASSWORD=... APP_PORT=... ./install.sh
#   SKIP_APT=1 ./install.sh      # skip `apt-get install` (already have deps)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$REPO_DIR/backend"
FRONTEND_DIR="$REPO_DIR/frontend"
VENV_DIR="$BACKEND_DIR/.venv"
ENV_FILE="$BACKEND_DIR/.env"

DB_NAME="${DB_NAME:-odds}"
DB_USER="${DB_USER:-odds}"
DB_PASSWORD="${DB_PASSWORD:-odds}"
APP_PORT="${APP_PORT:-8000}"
SERVICE_USER="${SUDO_USER:-$(id -un)}"

log() { printf '\n\033[1;34m==>\033[0m %s\n' "$1"; }
die() { printf '\033[1;31mErreur:\033[0m %s\n' "$1" >&2; exit 1; }

[[ $EUID -eq 0 ]] && die "Ne lance pas ce script en root — il utilise sudo lui-même quand nécessaire."

if ! command -v apt-get >/dev/null 2>&1; then
  if [[ "${SKIP_APT:-0}" != "1" ]]; then
    die "Ce script suppose une distribution basée sur apt (Debian/Ubuntu/Raspberry Pi OS). Installe manuellement python3 (>=3.11), python3-venv, postgresql, nodejs/npm, puis relance avec SKIP_APT=1."
  fi
fi

# 1. System packages ----------------------------------------------------
if [[ "${SKIP_APT:-0}" != "1" ]]; then
  log "Installation des paquets système (sudo requis)"
  sudo apt-get update -qq
  sudo apt-get install -y python3 python3-venv python3-pip postgresql postgresql-contrib nodejs npm
fi

for cmd in python3 psql node npm; do
  command -v "$cmd" >/dev/null 2>&1 || die "'$cmd' est introuvable. Installe-le (ou relance sans SKIP_APT=1)."
done

# 2. PostgreSQL: start it, create role+db if missing (idempotent) -------
log "Configuration de PostgreSQL"
sudo systemctl enable --now postgresql

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE ROLE \"$DB_USER\" WITH LOGIN PASSWORD '$DB_PASSWORD';"
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1; then
  sudo -u postgres psql -c "CREATE DATABASE \"$DB_NAME\" OWNER \"$DB_USER\";"
fi

# 3. Backend venv + deps -------------------------------------------------
log "Environnement Python et dépendances backend"
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install -q --upgrade pip
"$VENV_DIR/bin/pip" install -q -r "$BACKEND_DIR/requirements.txt"

# 4. backend/.env: generate once, never overwrite an existing one -------
if [[ ! -f "$ENV_FILE" ]]; then
  log "Génération de $ENV_FILE"
  API_KEY_VALUE="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
  cp "$REPO_DIR/.env.example" "$ENV_FILE"
  sed -i "s#^DATABASE_URL=.*#DATABASE_URL=postgresql+psycopg://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME#" "$ENV_FILE"
  sed -i "s#^API_KEY=.*#API_KEY=$API_KEY_VALUE#" "$ENV_FILE"
  echo "   Clé API générée — pense à renseigner ODDS_API_KEY (compte The Odds API) dans $ENV_FILE"
else
  log "$ENV_FILE existe déjà, conservé tel quel"
fi

# 5. Migrations -----------------------------------------------------------
log "Migrations Alembic"
(
  cd "$BACKEND_DIR"
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
  PYTHONPATH="$BACKEND_DIR" "$VENV_DIR/bin/alembic" upgrade head
)

# 6. Frontend build (served by the API itself — see FRONTEND_DIST_DIR in
#    app/main.py) --------------------------------------------------------
log "Build du frontend"
API_KEY_FOR_BUILD="$(grep '^API_KEY=' "$ENV_FILE" | cut -d= -f2-)"
(
  cd "$FRONTEND_DIR"
  npm install --no-audit --no-fund
  VITE_API_KEY="$API_KEY_FOR_BUILD" npm run build
)

# 7. systemd services -----------------------------------------------------
log "Installation des services systemd (sudo requis)"

sudo tee /etc/systemd/system/odds-api.service > /dev/null <<EOF
[Unit]
Description=Odds API (+ frontend)
After=network.target postgresql.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$BACKEND_DIR
EnvironmentFile=$ENV_FILE
Environment=PYTHONPATH=$BACKEND_DIR
ExecStart=$VENV_DIR/bin/uvicorn app.main:app --host 0.0.0.0 --port $APP_PORT
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/odds-scheduler.service > /dev/null <<EOF
[Unit]
Description=Odds scheduler (ingestion des cotes, capture de clôture, règlement auto)
After=network.target postgresql.service

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$BACKEND_DIR
EnvironmentFile=$ENV_FILE
Environment=PYTHONPATH=$BACKEND_DIR
ExecStart=$VENV_DIR/bin/python -m app.scheduler
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable odds-api odds-scheduler
sudo systemctl restart odds-api odds-scheduler

LAN_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"

log "Terminé"
echo "Application : http://localhost:$APP_PORT${LAN_IP:+  (ou http://$LAN_IP:$APP_PORT depuis le réseau local)}"
echo "Logs        : sudo journalctl -u odds-api -f    /    sudo journalctl -u odds-scheduler -f"
echo "Statut      : sudo systemctl status odds-api odds-scheduler"
if ! grep -q '^ODDS_API_KEY=.\+' "$ENV_FILE"; then
  echo ""
  echo "⚠️  ODDS_API_KEY n'est pas renseignée dans $ENV_FILE — aucune cote ne sera"
  echo "   récupérée tant que ce n'est pas fait. Puis : sudo systemctl restart odds-api odds-scheduler"
fi
echo ""
echo "Pour mettre à jour plus tard : git pull && ./install.sh"
