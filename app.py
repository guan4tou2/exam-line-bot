import re
import random
import json
import os
from dotenv import load_dotenv, find_dotenv
from flask import Flask, request, abort

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexContainer,
    FlexMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)

load_dotenv(find_dotenv())
access_token = os.getenv('ACCESS_TOKEN')
secret = os.getenv('SECRET')
configuration = Configuration(access_token=access_token)
handler = WebhookHandler(secret)

app = Flask(__name__)

# 定義全局變量
current_question = None
current_question_data = None  # 用於存儲完整的題目數據
current_database = None  # 用於追踪當前題庫


def create_database_flex_message(page=1):
    """創建題庫選擇的 Flex Message
    Args:
        page (int): 當前頁碼，從1開始
    """
    try:
        # 讀取基本模板
        with open('templates/database_flex_message.json', 'r', encoding='utf-8') as f:
            flex_message = json.load(f)

        # 獲取 database 資料夾中的所有 json 文件
        database_files = [f for f in os.listdir('database') if f.endswith('.json')]
        
        # 計算分頁資訊
        items_per_page = 10  # 每頁顯示10個題庫
        total_pages = (len(database_files) + items_per_page - 1) // items_per_page
        
        # 確保頁碼有效
        page = max(1, min(page, total_pages))
        
        # 計算當前頁的題庫
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        current_page_files = database_files[start_idx:end_idx]

        # 創建題庫氣泡列表
        bubbles = []
        for db_file in current_page_files:
            # 移除 .json 副檔名，作為題庫名稱
            db_name = db_file[:-5]
            
            # 如果題庫名稱太長，截斷它
            display_name = db_name
            if len(display_name) > 20:  # 為了在氣泡中顯示得更好
                display_name = display_name[:17] + "..."

            bubble = {
                "type": "bubble",
                "size": "micro",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": display_name,
                            "weight": "bold",
                            "size": "md",
                            "wrap": True,
                            "align": "center"
                        },
                        {
                            "type": "button",
                            "style": "primary",
                            "color": "#5A8DEE",
                            "action": {
                                "type": "message",
                                "label": "開始練習",
                                "text": f"切換到 {db_name}"
                            }
                        }
                    ]
                }
            }
            bubbles.append(bubble)

        # 添加分頁控制氣泡
        if total_pages > 1:
            navigation_contents = [
                {
                    "type": "text",
                    "text": f"第 {page}/{total_pages} 頁",
                    "weight": "bold",
                    "size": "sm",
                    "align": "center"
                }
            ]

            # 上一頁按鈕
            if page > 1:
                navigation_contents.append({
                    "type": "button",
                    "style": "secondary",
                    "action": {
                        "type": "message",
                        "label": "上一頁",
                        "text": f"題庫列表 {page-1}"
                    }
                })
            
            # 下一頁按鈕
            if page < total_pages:
                navigation_contents.append({
                    "type": "button",
                    "style": "secondary",
                    "action": {
                        "type": "message",
                        "label": "下一頁",
                        "text": f"題庫列表 {page+1}"
                    }
                })

            navigation_bubble = {
                "type": "bubble",
                "size": "micro",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "sm",
                    "contents": navigation_contents
                }
            }

            bubbles.append(navigation_bubble)

        # 更新 carousel 內容
        flex_message["contents"] = bubbles
        return flex_message

    except Exception as e:
        print(f"Error creating database flex message: {e}")
        return None


def get_question(database_name=None):
    """從指定題庫或預設題庫中讀取隨機題目"""
    try:
        file_path = f'database/{database_name}.json' if database_name else 'questions.json'
        with open(file_path, 'r', encoding='utf-8') as f:
            questions_data = json.load(f)
            questions = questions_data['questions']
            return random.choice(questions)
    except Exception as e:
        print(f"Error reading questions: {e}")
        return None


def create_flex_message(question_data):
    """創建 Flex Message，保持ABCD順序不變，但選項內容隨機排序"""
    global current_question, current_question_data

    with open('templates/topic_flex_message.json', 'r', encoding='utf-8') as f:
        flex_message = json.load(f)

    # 保存當前題目數據
    current_question = question_data["answer"]
    current_question_data = question_data

    # 設置題目文字
    flex_message["body"]["contents"][1]["text"] = f"🧠 題目：{question_data['question_text']}"

    # 獲取選項內容並隨機打亂
    options = list(question_data["options"].values())  # 獲取選項內容列表
    random.shuffle(options)  # 隨機打亂選項內容

    # 創建新的選項映射
    new_options = {}
    original_answer = question_data["answer"]  # 保存原始正確答案

    # 建立新的選項對應關係
    for i, option in enumerate(options):
        char = "ABCD"[i]
        new_options[char] = option
        # 如果這個選項是原來的正確答案，更新答案字母
        if option == question_data["options"][original_answer]:
            current_question = char  # 更新正確答案為新的選項字母

    # 更新題目數據中的選項
    current_question_data = question_data.copy()
    current_question_data["options"] = new_options
    current_question_data["answer"] = current_question

    # 創建選項容器
    options_container = {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": []
    }

    # 設置選項按鈕（按 A,B,C,D 順序）
    for i, char in enumerate("ABCD"):
        option_box = {
            "type": "box",
            "layout": "vertical",
            "cornerRadius": "xxl",
            "backgroundColor": "#5A8DEE",
            "action": {
                "type": "message",
                "text": f"選擇 {char}. {new_options[char]}"
            },
            "contents": [
                {
                    "type": "box",
                    "layout": "horizontal",
                    "paddingAll": "lg",
                    "contents": [
                        {
                            "type": "text",
                            "text": f"{char}. {new_options[char]}",
                            "color": "#ffffff",
                            "wrap": True,
                            "size": "sm",
                            "flex": 1
                        }
                    ]
                }
            ]
        }
        options_container["contents"].append(option_box)

    # 更新 flex message 中的選項容器
    flex_message["body"]["contents"][3] = options_container

    return flex_message


def send_question(reply_token, database_name=None):
    """發送新題目"""
    global current_database

    try:
        # 如果沒有指定題庫名稱，使用當前題庫或第一個可用的題庫
        if database_name is None:
            if current_database:
                database_name = current_database
            else:
                # 獲取 database 目錄下的所有 json 文件
                database_files = [f[:-5] for f in os.listdir('database') if f.endswith('.json')]
                if not database_files:
                    raise FileNotFoundError("找不到任何題庫文件")
                database_name = database_files[0]  # 使用第一個找到的題庫
        
        current_database = database_name  # 更新當前題庫

        # 檢查題庫文件是否存在
        file_path = f'database/{database_name}.json'
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"找不到題庫文件：{file_path}")

        question_data = get_question(database_name)
        if not question_data:
            raise ValueError("無法從題庫中獲取題目")

        flex_content = create_flex_message(question_data)
        if not flex_content:
            raise ValueError("無法創建 Flex Message")

        # 更新題庫名稱
        flex_content["body"]["contents"][0]["text"] = f"📚 題庫：{database_name}"

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[FlexMessage(
                        alt_text=f"iPAS {database_name}題目",
                        contents=FlexContainer.from_dict(flex_content)
                    )]
                )
            )
    except FileNotFoundError as e:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text=f"抱歉，{str(e)}")]
                )
            )
    except Exception as e:
        print(f"Error in send_question: {e}")
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=[TextMessage(text="抱歉，讀取題目時發生錯誤。請稍後再試或切換其他題庫。")]
                )
            )


def create_answer_flex_message(question_data, selected_answer, is_correct):
    """創建答案回覆的 Flex Message"""
    try:
        with open('templates/answer_flex_message.json', 'r', encoding='utf-8') as f:
            flex_message = json.load(f)

        # 設置答對/答錯的文字和顏色
        flex_message["body"]["contents"][0]["text"] = "✅ 答對了！" if is_correct else "❌ 答錯了！"
        flex_message["body"]["contents"][0]["color"] = "#00C851" if is_correct else "#ff4444"

        # 設置題目文字（如果太長則截斷）
        question_text = question_data['question_text']
        if len(question_text) > 100:  # 限制題目長度
            question_text = question_text[:97] + "..."
        flex_message["body"]["contents"][2]["text"] = question_text

        # 設置正確答案（如果太長則截斷）
        correct_answer = question_data['options'][question_data['answer']]
        if len(correct_answer) > 40:  # 限制答案長度
            correct_answer = correct_answer[:37] + "..."
        flex_message["body"]["contents"][3]["contents"][1]["text"] = correct_answer

        return flex_message
    except Exception as e:
        print(f"Error creating answer flex message: {e}")
        return None


@app.route("/", methods=['POST'])
def callback():
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info(
            "Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """處理收到的消息"""
    try:
        message_text = event.message.text

        # 準備 API 客戶端
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            # 如果是選項回答
            if message_text.startswith("選擇 "):
                selected_answer = message_text.split(" ")[1].split(".")[0]  # 獲取選擇的選項（A、B、C、D）

                # 檢查答案並回覆
                if current_question and current_question_data:
                    is_correct = selected_answer == current_question
                    result_flex = create_answer_flex_message(current_question_data, selected_answer, is_correct)

                    if result_flex:
                        line_bot_api.reply_message_with_http_info(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[FlexMessage(alt_text="題目回顧", contents=FlexContainer.from_dict(result_flex))]
                            )
                        )
                    else:
                        line_bot_api.reply_message_with_http_info(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="抱歉，無法顯示答案回覆")]
                            )
                        )

            # 如果是切換題庫請求
            elif message_text == "切換題庫":
                flex_content = create_database_flex_message(page=1)
                if flex_content:
                    line_bot_api.reply_message_with_http_info(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[FlexMessage(alt_text="選擇題庫", contents=FlexContainer.from_dict(flex_content))]
                        )
                    )
                else:
                    line_bot_api.reply_message_with_http_info(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="抱歉，無法讀取題庫列表")]
                        )
                    )

            # 如果是題庫列表分頁請求
            elif message_text.startswith("題庫列表 "):
                try:
                    page = int(message_text.split(" ")[1])
                    flex_content = create_database_flex_message(page=page)
                    if flex_content:
                        line_bot_api.reply_message_with_http_info(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[FlexMessage(alt_text=f"選擇題庫 - 第{page}頁", contents=FlexContainer.from_dict(flex_content))]
                            )
                        )
                except (ValueError, IndexError):
                    line_bot_api.reply_message_with_http_info(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="無效的頁碼")]
                        )
                    )

            # 如果是選擇特定題庫
            elif message_text.startswith("切換到 "):
                database_name = message_text[4:]  # 取得題庫名稱
                send_question(event.reply_token, database_name)

            # 如果是"下一題"請求
            elif message_text == "下一題":
                send_question(event.reply_token)  # 使用當前題庫

            # 如果是其他消息，顯示題庫選擇
            else:
                flex_content = create_database_flex_message(page=1)
                if flex_content:
                    line_bot_api.reply_message_with_http_info(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[
                                TextMessage(text="請選擇要練習的題庫："),
                                FlexMessage(alt_text="選擇題庫", contents=FlexContainer.from_dict(flex_content))
                            ]
                        )
                    )
                else:
                    line_bot_api.reply_message_with_http_info(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="抱歉，無法讀取題庫列表")]
                        )
                    )

    except Exception as e:
        print(f"Error in handle_message: {str(e)}")
        # 如果發生錯誤，嘗試發送一個簡單的錯誤訊息
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="處理訊息時發生錯誤，請稍後再試")]
                    )
                )
        except Exception as inner_e:
            print(f"Error sending error message: {str(inner_e)}")


if __name__ == "__main__":
    port = int(os.environ.get('PORT', 8080))
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False,
        threaded=True,
        ssl_context=(
            'ssl/cert.pem',
            'ssl/key.pem'
        )
    )
