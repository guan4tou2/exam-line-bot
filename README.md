# iPAS 題庫練習 LINE Bot

這是一個用於練習證照題目的 LINE Bot 應用程式。使用者可以透過 LINE 聊天介面進行題目練習，支援多個題庫切換，並提供即時答題回饋。
僅支持單選題。  

## 功能特點

- 📚 多題庫支援：可以在不同題庫之間自由切換
- 🎯 隨機出題：每次都會從題庫中隨機選擇題目
- 🔄 選項隨機排序：選項順序會隨機排列，增加練習效果
- ✨ 即時回饋：答題後立即顯示正確答案和解釋
- 📱 美觀的介面：使用 LINE Flex Message 提供現代化的使用者介面

## 系統需求

- Python 3.7 或以上版本
- LINE Messaging API Channel
- Flask 網頁框架
- 網路伺服器（用於接收 webhook）
- uv 套件管理工具

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
```

4. 設定 LINE Bot：
   - 在 [LINE Developers Console](https://developers.line.biz/console/) 建立一個新的 Channel
   - 設定 Webhook URL 為你的伺服器網址
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

2. 在 LINE 中加入好友：
   - 掃描 QR Code 或搜尋 Bot ID
   - 將 Bot 加入好友

3. 開始使用：
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
│   └── 初級-資訊安全管理概論.json             # 題目檔案
├── templates/                 # 模板資料夾
│   ├── topic_flex_message.json    # 題目顯示模板
│   ├── answer_flex_message.json   # 答案顯示模板
│   └── database_flex_message.json # 題庫選擇模板
└── README.md                  # 說明文件
```

## 開發說明

- 使用 `python-dotenv` 管理環境變數
- 使用 LINE Messaging API v3
- 使用 Flask 處理 webhook
- 使用 Flex Message 建立互動介面

## 注意事項

- 請確保伺服器可以接收外部連線
- 環境變數檔案 (.env) 不應上傳至版本控制系統
- 建議使用 HTTPS 以確保安全性

## 授權條款

本專案採用 MIT 授權條款。詳見 [LICENSE](LICENSE) 檔案。
