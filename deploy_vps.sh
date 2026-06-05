#!/bin/bash
set -euo pipefail

# ============================================================
# LogSage AI — VPS Deployment Script
# Tested on Ubuntu 22.04 LTS
# Run as root or with sudo privileges
# ============================================================

APP_DIR="/opt/logsage-ai"
APP_USER="logsage"
REPO_URL="https://github.com/YOUR_USERNAME/LogSage-AI.git"  # UPDATE THIS
DOMAIN=""  # Set your domain if you have one, leave empty for IP-only
PORT=8501

echo "=== Step 1: System Update ==="
apt-get update && apt-get upgrade -y
apt-get install -y python3.10 python3.10-venv python3-pip git curl nginx certbot python3-certbot-nginx ufw

echo "=== Step 2: Create App User ==="
id -u $APP_USER &>/dev/null || useradd -m -s /bin/bash $APP_USER

echo "=== Step 3: Install Ollama ==="
curl -fsSL https://ollama.com/install.sh | sh
systemctl enable ollama
systemctl start ollama
sleep 5
ollama pull llama3
echo "Ollama and llama3 ready"

echo "=== Step 4: Clone Project ==="
mkdir -p $APP_DIR
git clone $REPO_URL $APP_DIR || (cd $APP_DIR && git pull)
chown -R $APP_USER:$APP_USER $APP_DIR

echo "=== Step 5: Python Virtual Environment ==="
cd $APP_DIR
sudo -u $APP_USER python3.10 -m venv venv
sudo -u $APP_USER venv/bin/pip install --upgrade pip
sudo -u $APP_USER venv/bin/pip install -r requirements.txt

echo "=== Step 6: Environment Config ==="
cat > $APP_DIR/.env << EOF
OLLAMA_HOST=http://localhost:11434
DB_PATH=$APP_DIR/data/logsage.db
MODEL_NAME=llama3
EOF
mkdir -p $APP_DIR/data
chown -R $APP_USER:$APP_USER $APP_DIR/data

echo "=== Step 7: Systemd Service ==="
cat > /etc/systemd/system/logsage.service << EOF
[Unit]
Description=LogSage AI Streamlit Application
After=network.target ollama.service
Requires=ollama.service

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/venv/bin/streamlit run app.py \\
    --server.port=$PORT \\
    --server.address=127.0.0.1 \\
    --server.headless=true \\
    --browser.gatherUsageStats=false
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=logsage

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable logsage
systemctl start logsage
sleep 5
systemctl status logsage --no-pager

echo "=== Step 8: Nginx Reverse Proxy ==="
cat > /etc/nginx/sites-available/logsage << EOF
server {
    listen 80;
    server_name ${DOMAIN:-_};

    client_max_body_size 20M;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
    }
}
EOF

ln -sf /etc/nginx/sites-available/logsage /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx

echo "=== Step 9: Firewall ==="
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

echo "=== Step 10: SSL (if domain is set) ==="
if [ -n "$DOMAIN" ]; then
    certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@$DOMAIN
    echo "SSL configured for $DOMAIN"
fi

echo ""
echo "=== Deployment Complete ==="
SERVER_IP=\$(curl -s ifconfig.me)
echo "LogSage AI is running at: http://\$SERVER_IP"
[ -n "$DOMAIN" ] && echo "Also available at: https://$DOMAIN"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status logsage    — check app status"
echo "  sudo journalctl -u logsage -f    — live logs"
echo "  sudo systemctl restart logsage   — restart app"
echo "  ollama list                      — check models"
