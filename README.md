#  題目練習 LINE Bot

這是一個用於練習證照題目的 LINE Bot 應用程式。使用者可以透過 LINE 聊天介面進行題目練習，支援多個題庫切換，並提供即時答題回饋。
僅支持單選題。  

## 功能特點

- 📚 多題庫支援：可以在不同題庫之間自由切換
- 🎯 隨機出題：每次都會從題庫中隨機選擇題目
- 🔄 選項隨機排序：選項順序會隨機排列，增加練習效果
- ✨ 即時回饋：答題後立即顯示正確答案和解釋
- 📱 美觀的介面：使用 LINE Flex Message 提供現代化的使用者介面
- 🔒 安全連接：支援 SSL/HTTPS 加密連接

## 系統需求

- Python 3.7 或以上版本
- LINE Messaging API Channel
- Flask 網頁框架
- 網路伺服器（用於接收 webhook）
- uv 套件管理工具
- OpenSSL（用於生成 SSL 證書）

## 安裝步驟

1. 安裝 uv（如果尚未安裝）：
```bash
# 使用 pip 安裝 uv
pip install uv

# 或使用 curl 安裝（Linux/macOS）
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. 安裝所需套件：
```bash
# 建立虛擬環境並安裝依賴
uv venv
source .venv/bin/activate  # Linux/macOS
# 或在 Windows 上：
# .venv\Scripts\activate

# 安裝依賴
uv sync
```

3. 設定環境變數：
   - 建立 `.env` 檔案
   - 填入以下內容：
```
ACCESS_TOKEN=你的_LINE_Channel_Access_Token
SECRET=你的_LINE_Channel_Secret
PORT=8080  # 可選，預設為 8080
```

4. 設定免費域名（使用 DuckDNS）：
```bash
# 1. 註冊 DuckDNS
# 訪問 https://www.duckdns.org/ 並使用 GitHub 或其他方式登入

# 2. 創建子域名
# - 在 domains 頁面添加新的子域名（例如：mybot.duckdns.org）
# - 記下 token 值

# 3. 安裝更新腳本
mkdir -p ~/duckdns
cd ~/duckdns
token="你的DuckDNS令牌"
domain="你的子域名"

# 創建更新腳本
cat > duck.sh << EOF
echo url="https://www.duckdns.org/update?domains=$domain&token=$token&ip=" | curl -k -o ~/duckdns/duck.log -K -
EOF

# 設定執行權限
chmod 700 duck.sh

# 測試更新
./duck.sh

# 4. 設定自動更新（每5分鐘）
(crontab -l 2>/dev/null; echo "*/5 * * * * ~/duckdns/duck.sh >/dev/null 2>&1") | crontab -
```

5. 設定 SSL 證書：

使用 Certbot：
```bash
# 安裝 Certbot（Ubuntu/Debian）
sudo apt update
sudo apt install certbot

# 確保 80 和 443 端口未被占用
sudo lsof -i :80
sudo lsof -i :443

# 生成證書（使用 --standalone 模式）
sudo certbot certonly --standalone -d YOUR_DOMAIN.duckdns.org \
    --agree-tos \
    --no-eff-email \
    --register-unsafely-without-email

# 複製證書到專案目錄
sudo mkdir -p ssl
sudo cp /etc/letsencrypt/live/YOUR_DOMAIN.duckdns.org/fullchain.pem ssl/cert.pem
sudo cp /etc/letsencrypt/live/YOUR_DOMAIN.duckdns.org/privkey.pem ssl/key.pem
sudo chown -R $USER:$USER ssl/

# 設定自動更新證書
sudo certbot renew --dry-run

# 添加定時更新任務（每天檢查一次）
(crontab -l 2>/dev/null; echo "0 0 * * * sudo certbot renew --quiet") | crontab -
```

注意事項：
1. DuckDNS 相關：
   - 定期檢查 DuckDNS 更新腳本的運行狀態
   - 確保 token 安全保存
   - 如果 IP 變更，DuckDNS 會自動更新

2. SSL 證書相關：
   - 確保 80 和 443 端口未被占用
   - 證書有效期為 90 天，系統會自動更新
   - 定期檢查證書狀態：`sudo certbot certificates`
   - 檢查自動更新是否正常：`systemctl status certbot.timer`

6. 設定 LINE Bot：
   - 在 [LINE Developers Console](https://developers.line.biz/console/) 建立一個新的 Channel
   - 設定 Webhook URL 為 `https://YOUR_DOMAIN.duckdns.org:8080`
   - 開啟 "Use webhook" 選項

## 題庫格式

題庫檔案應放在 `database` 資料夾中，使用 JSON 格式：
檔名會作為題庫名稱顯示  

```json
{
    "questions": [
        {
            "id": 1,
            "question_text": "題目內容",
            "options": {
                "A": "選項A",
                "B": "選項B",
                "C": "選項C",
                "D": "選項D"
            },
            "answer": "B"
        }
    ]
}
```

## 使用方法

1. 啟動伺服器：

```bash
uv run app.py
```

1. 在 LINE 中加入好友：
   - 掃描 QR Code 或搜尋 Bot ID
   - 將 Bot 加入好友

2. 開始使用：
   - 發送任何訊息開始練習
   - 點選「切換題庫」可以更換題庫
   - 選擇答案後會顯示正確答案
   - 點選「下一題」繼續練習

## 檔案結構

```
.
├── app.py                      # 主程式
├── requirements.txt            # 相依套件清單
├── .env                       # 環境變數設定
├── database/                  # 題庫資料夾
│   ├── 技術.json              # 技術題庫
│   └── 管理.json              # 管理題庫
├── templates/                 # 模板資料夾
│   ├── topic_flex_message.json    # 題目顯示模板
│   ├── answer_flex_message.json   # 答案顯示模板
│   └── database_flex_message.json # 題庫選擇模板
├── ssl/                      # SSL 證書目錄
│   ├── cert.pem              # SSL 證書
│   └── key.pem               # SSL 私鑰
└── README.md                  # 說明文件
```

## 開發說明

- 使用 `python-dotenv` 管理環境變數
- 使用 LINE Messaging API v3
- 使用 Flask 處理 webhook
- 使用 Flex Message 建立互動介面
- 支援 SSL/HTTPS 安全連接

## 安全性建議

1. SSL/HTTPS：
   - 使用 DuckDNS 提供免費域名
   - 使用 Certbot 申請 Let's Encrypt 證書
   - 設定證書和 DNS 自動更新
   - 定期檢查更新腳本運行狀態
   - 確保證書權限正確設置

2. 環境變數：
   - 環境變數檔案 (.env) 不應上傳至版本控制系統
   - 生產環境建議使用環境變數管理系統

3. 存取控制：
   - 確保伺服器防火牆設定正確
   - 只開放必要的端口
   - 使用反向代理（如 Nginx）增加安全性

## 注意事項

- 請確保伺服器可以接收外部連線
- 使用 HTTPS 以確保安全性
- 定期更新相依套件以修補安全漏洞
- 生產環境建議使用 process manager（如 PM2）管理程序

## 授權條款

本專案採用 MIT 授權條款。詳見 [LICENSE](LICENSE) 檔案。
