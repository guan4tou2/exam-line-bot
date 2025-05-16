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
from database import Database

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
user_selections = {}  # 添加全局變量來儲存用戶選擇
user_question_options = {}  # 添加全局變量來儲存每個用戶的題目選項順序
user_current_question = {}  # user_id: 正確答案
user_current_question_data = {}  # user_id: 題目完整資料

# 初始化數據庫
db = Database()


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
        database_files = [f for f in os.listdir(
            'database') if f.endswith('.json')]

        # 計算分頁資訊
        items_per_page = 10  # 每頁顯示10個題庫
        total_pages = (len(database_files) +
                       items_per_page - 1) // items_per_page

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


def is_multi_choice_db(database_name):
    """判斷是否為多選題庫"""
    return database_name.endswith('multi')


def create_flex_message(question_data, selected_options=None, user_id=None, is_multi=False):
    """創建 Flex Message，保持ABCD順序不變，但選項內容隨機排序
    Args:
        question_data: 題目數據
        selected_options: 已選擇的選項集合
        user_id: 用戶ID，用於追踪選項順序
        is_multi: 是否為多選題
    """
    global current_question, current_question_data, user_question_options

    # 根據題目類型選擇不同的模板文件
    template_file = 'templates/multi_flex_message.json' if is_multi else 'templates/topic_flex_message.json'
    with open(template_file, 'r', encoding='utf-8') as f:
        flex_message = json.load(f)

    # 保存當前題目數據
    current_question = question_data["answer"]  # 這裡可能是單個字母或多個字母的字符串
    current_question_data = question_data

    # 設置題目文字
    flex_message["body"]["contents"][1]["text"] = f"🧠 題目：{question_data['question_text']}"

    # 檢查是否已有固定的選項順序
    if is_multi and user_id and user_id in user_question_options and question_data["id"] == user_question_options[user_id]["id"]:
        # 使用已存在的選項順序
        new_options = user_question_options[user_id]["options"]
        current_question = user_question_options[user_id]["answer"]
    else:
        # 首次顯示題目，隨機排序選項
        options = list(question_data["options"].values())  # 獲取選項內容列表
        random.shuffle(options)  # 隨機打亂選項內容

        # 創建新的選項映射
        new_options = {}
        original_answers = list(question_data["answer"])  # 將答案字符串轉換為列表

        # 建立新的選項對應關係
        new_answers = []  # 用於存儲新的答案字母
        for i, option in enumerate(options):
            char = "ABCD"[i]
            new_options[char] = option
            # 檢查這個選項是否是原來的正確答案之一
            for original_answer in original_answers:
                if option == question_data["options"][original_answer]:
                    new_answers.append(char)

        # 更新正確答案為新的字母組合
        current_question = ''.join(sorted(new_answers))

        # 保存選項順序（僅多選題需要）
        if is_multi and user_id:
            user_question_options[user_id] = {
                "id": question_data["id"],
                "options": new_options,
                "answer": current_question
            }

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

    # 如果沒有已選擇的選項，初始化為空集合
    if selected_options is None:
        selected_options = set()

    # 設置選項按鈕（按 A,B,C,D 順序）
    for i, char in enumerate("ABCD"):
        if is_multi:
            # 多選題使用盒子樣式，有背景色變化
            background_color = "#5A8DEE" if char in selected_options else "#AAAAAA"
            option_box = {
                "type": "box",
                "layout": "vertical",
                "cornerRadius": "xxl",
                "backgroundColor": background_color,
                "action": {
                    "type": "message",
                    "text": f"選擇 {char}"
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
        else:
            # 單選題使用盒子樣式
            option_box = {
                "type": "box",
                "layout": "vertical",
                "cornerRadius": "xxl",
                "backgroundColor": "#5A8DEE",
                "action": {
                    "type": "message",
                    "text": f"選擇 {char}"
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

    # 獲取題目的作答統計
    attempt_stats = db.get_question_attempt_stats(
        question_data['id'], current_database)
    print(f"Got attempt stats: {attempt_stats}")

    # 更新 footer 中的統計信息
    if "footer" in flex_message:
        stats_box = flex_message["footer"]["contents"][0]
        if isinstance(stats_box, dict) and "contents" in stats_box:
            print(f"Updating stats in footer: {stats_box}")
            # 直接設置實際的數值，而不是使用佔位符
            stats_box["contents"][0]["text"] = f"作答次數：{attempt_stats['total_attempts']}"
            stats_box["contents"][1]["text"] = f"答對次數：{attempt_stats['correct_attempts']}"
            print(f"Updated footer stats: {stats_box}")
        else:
            print(f"Unexpected footer structure: {stats_box}")

    if user_id:
        user_current_question[user_id] = current_question
        user_current_question_data[user_id] = current_question_data

    return flex_message


def create_statistics_flex_message(user_id, database_name):
    """創建統計信息的 Flex Message"""
    try:
        # 讀取基本模板
        with open('templates/statistics_flex_message.json', 'r', encoding='utf-8') as f:
            flex_message = json.load(f)

        # 獲取統計數據
        stats = db.get_user_statistics(user_id, database_name)

        # 更新模板中的變量
        flex_message["body"]["contents"][1]["text"] = f"📚 當前題庫：{database_name}"

        # 更新統計數據
        stats_box = flex_message["body"]["contents"][2]["contents"]
        for box in stats_box:
            if box.get("type") == "box" and box.get("layout") == "baseline":
                value_text = box["contents"][1]
                if "總題目數" in box["contents"][0]["text"]:
                    value_text["text"] = str(stats['total_questions'])
                elif "已答題數" in box["contents"][0]["text"]:
                    value_text["text"] = str(stats['total_answers'])
                elif "答對題數" in box["contents"][0]["text"]:
                    value_text["text"] = str(stats['correct_answers'])
                elif "完成率" in box["contents"][0]["text"]:
                    value_text["text"] = f"{stats['completion_rate']:.1f}%"
                elif "正確率" in box["contents"][0]["text"]:
                    value_text["text"] = f"{stats['accuracy_rate']:.1f}%"
                elif "錯題數" in box["contents"][0]["text"]:
                    value_text["text"] = str(stats['total_wrong_questions'])

        # 如果有錯題練習記錄，添加相關統計
        if stats['practice_count'] > 0:
            practice_stats = {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "margin": "xl",
                "contents": [
                    {
                        "type": "text",
                        "text": "📝 錯題練習統計",
                        "weight": "bold",
                        "size": "md",
                        "color": "#1a1a1a"
                    },
                    {
                        "type": "box",
                        "layout": "baseline",
                        "contents": [
                            {
                                "type": "text",
                                "text": "練習次數",
                                "size": "sm",
                                "color": "#888888",
                                "flex": 1
                            },
                            {
                                "type": "text",
                                "text": str(stats['practice_count']),
                                "size": "sm",
                                "color": "#5A8DEE",
                                "align": "end"
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "baseline",
                        "contents": [
                            {
                                "type": "text",
                                "text": "答對次數",
                                "size": "sm",
                                "color": "#888888",
                                "flex": 1
                            },
                            {
                                "type": "text",
                                "text": str(stats['practice_correct']),
                                "size": "sm",
                                "color": "#00C851",
                                "align": "end"
                            }
                        ]
                    },
                    {
                        "type": "box",
                        "layout": "baseline",
                        "contents": [
                            {
                                "type": "text",
                                "text": "練習正確率",
                                "size": "sm",
                                "color": "#888888",
                                "flex": 1
                            },
                            {
                                "type": "text",
                                "text": f"{stats['practice_accuracy_rate']:.1f}%",
                                "size": "sm",
                                "color": "#00C851",
                                "align": "end"
                            }
                        ]
                    }
                ]
            }
            flex_message["body"]["contents"].append(practice_stats)

        return flex_message
    except Exception as e:
        print(f"Error creating statistics flex message: {e}")
        return None


def send_question(reply_token, database_name=None, user_id=None, wrong_question=None):
    """發送新題目"""
    global current_database

    try:
        # 如果沒有指定題庫名稱，使用當前題庫或第一個可用的題庫
        if database_name is None:
            if current_database:
                database_name = current_database
            else:
                database_files = [f[:-5]
                                  for f in os.listdir('database') if f.endswith('.json')]
                if not database_files:
                    raise FileNotFoundError("找不到任何題庫文件")
                database_name = database_files[0]

        current_database = database_name
        is_multi = is_multi_choice_db(database_name)

        # 更新用戶當前題庫
        if user_id:
            db.update_user_state(user_id, database_name)

        # 獲取題目
        if wrong_question:
            question_data = wrong_question['question_data']
        else:
            question_data = get_question(database_name)

        if not question_data:
            raise ValueError("無法從題庫中獲取題目")

        # 清除用戶之前的選項順序
        if user_id in user_question_options:
            del user_question_options[user_id]

        # 創建 Flex Message
        flex_content = create_flex_message(
            question_data, set(), user_id, is_multi)
        if not flex_content:
            raise ValueError("無法創建 Flex Message")

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
        # 對於多選題，顯示所有正確答案
        correct_answers = []
        for ans in question_data['answer']:
            correct_answers.append(f"{ans}. {question_data['options'][ans]}")
        correct_answer_text = "\n".join(correct_answers)

        if len(correct_answer_text) > 200:  # 限制答案長度
            correct_answer_text = correct_answer_text[:197] + "..."
        flex_message["body"]["contents"][3]["contents"][1]["text"] = correct_answer_text

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
    global is_wrong_question_practice
    try:
        message_text = event.message.text
        user_id = event.source.user_id

        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)

            # 檢查當前是否為多選題庫
            is_multi = current_database and is_multi_choice_db(
                current_database)

            # 如果是選項選擇
            if message_text.startswith("選擇 "):
                # 從消息中提取選項（例如："選擇 A. 選項內容" -> "A"）
                selected_answer = message_text.split(" ")[1].split(".")[0]

                if not is_multi:
                    # 單選題直接檢查答案
                    if user_id in user_current_question and user_id in user_current_question_data:
                        correct_answer = user_current_question[user_id]
                        question_data = user_current_question_data[user_id]
                        is_correct = selected_answer == correct_answer

                        # 記錄答題
                        db.record_answer(
                            user_id=user_id,
                            question_data=question_data,
                            user_answer=selected_answer,
                            is_correct=is_correct,
                            database_name=current_database,
                            is_wrong_question_practice=getattr(
                                globals(), 'is_wrong_question_practice', False)
                        )

                        # 清除
                        del user_current_question[user_id]
                        del user_current_question_data[user_id]

                        # 顯示結果
                        result_flex = create_answer_flex_message(
                            question_data, selected_answer, is_correct)
                        if result_flex:
                            line_bot_api.reply_message_with_http_info(
                                ReplyMessageRequest(
                                    reply_token=event.reply_token,
                                    messages=[FlexMessage(
                                        alt_text="題目回顧", contents=FlexContainer.from_dict(result_flex))]
                                )
                            )
                    return
                else:
                    # 多選題只更新選擇，不做答題判斷
                    if user_id not in user_selections:
                        user_selections[user_id] = set()
                    if selected_answer in user_selections[user_id]:
                        user_selections[user_id].remove(selected_answer)
                    else:
                        user_selections[user_id].add(selected_answer)

                    # 更新畫面
                    if user_id in user_current_question_data:
                        flex_content = create_flex_message(
                            user_current_question_data[user_id], user_selections[user_id], user_id, True)
                        line_bot_api.reply_message_with_http_info(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[FlexMessage(
                                    alt_text="選擇題選項",
                                    contents=FlexContainer.from_dict(
                                        flex_content)
                                )]
                            )
                        )
                    return

            # 如果是清除選擇（僅多選題可用）
            elif message_text == "清除選擇" and is_multi:
                if user_id in user_selections:
                    user_selections[user_id].clear()
                    if user_id in user_current_question_data:
                        flex_content = create_flex_message(
                            user_current_question_data[user_id], set(), user_id, True)
                        line_bot_api.reply_message_with_http_info(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[FlexMessage(
                                    alt_text="選擇題選項",
                                    contents=FlexContainer.from_dict(
                                        flex_content)
                                )]
                            )
                        )
                    return

            # 如果是送出答案（僅多選題可用）
            elif message_text == "送出答案" and is_multi:
                if user_id not in user_selections or not user_selections[user_id]:
                    line_bot_api.reply_message_with_http_info(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="請先選擇答案")]
                        )
                    )
                    return

                if user_id in user_current_question and user_id in user_current_question_data:
                    correct_answer = user_current_question[user_id]
                    question_data = user_current_question_data[user_id]
                    selected_answers = sorted(user_selections[user_id])

                    is_correct = (len(selected_answers) == len(correct_answer) and
                                  all(ans in correct_answer for ans in selected_answers))

                    # 記錄答題
                    db.record_answer(
                        user_id=user_id,
                        question_data=question_data,
                        user_answer=','.join(selected_answers),
                        is_correct=is_correct,
                        database_name=current_database,
                        is_wrong_question_practice=getattr(
                            globals(), 'is_wrong_question_practice', False)
                    )

                    # 重置錯題練習標記
                    if 'is_wrong_question_practice' in globals():
                        del is_wrong_question_practice

                    result_flex = create_answer_flex_message(
                        question_data,
                        ','.join(selected_answers),
                        is_correct
                    )

                    user_selections[user_id].clear()
                    if user_id in user_question_options:
                        del user_question_options[user_id]

                    if result_flex:
                        line_bot_api.reply_message_with_http_info(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[FlexMessage(
                                    alt_text="題目回顧", contents=FlexContainer.from_dict(result_flex))]
                            )
                        )
                return

            # 如果是查看統計
            elif message_text == "查看統計":
                current_db = db.get_user_state(user_id)
                if current_db:
                    stats_flex = create_statistics_flex_message(
                        user_id, current_db)
                    line_bot_api.reply_message_with_http_info(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[FlexMessage(
                                alt_text="答題統計", contents=FlexContainer.from_dict(stats_flex))]
                        )
                    )
                else:
                    line_bot_api.reply_message_with_http_info(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="請先選擇題庫開始練習")]
                        )
                    )
                return

            # 如果是練習錯題
            elif message_text == "練習錯題":
                current_db = db.get_user_state(user_id)
                if current_db:
                    wrong_questions = db.get_wrong_questions(
                        user_id, current_db)
                    if wrong_questions:
                        # 隨機選擇一道錯題
                        wrong_question = random.choice(wrong_questions)
                        # 發送題目時標記為錯題練習
                        is_wrong_question_practice = True
                        send_question(event.reply_token,
                                      current_db, user_id, wrong_question)
                    else:
                        line_bot_api.reply_message_with_http_info(
                            ReplyMessageRequest(
                                reply_token=event.reply_token,
                                messages=[TextMessage(text="目前沒有錯題記錄")]
                            )
                        )
                else:
                    line_bot_api.reply_message_with_http_info(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[TextMessage(text="請先選擇題庫開始練習")]
                        )
                    )
                return

            # 如果是切換題庫請求
            elif message_text == "切換題庫":
                flex_content = create_database_flex_message(page=1)
                if flex_content:
                    line_bot_api.reply_message_with_http_info(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[FlexMessage(
                                alt_text="選擇題庫", contents=FlexContainer.from_dict(flex_content))]
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
                                messages=[FlexMessage(
                                    alt_text=f"選擇題庫 - 第{page}頁", contents=FlexContainer.from_dict(flex_content))]
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
                database_name = message_text[4:]
                send_question(event.reply_token, database_name, user_id)

            # 如果是"下一題"請求
            elif message_text == "下一題":
                send_question(event.reply_token, user_id=user_id)

            # 如果是其他消息，顯示題庫選擇
            else:
                flex_content = create_database_flex_message(page=1)
                if flex_content:
                    line_bot_api.reply_message_with_http_info(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[
                                TextMessage(text="請選擇要練習的題庫："),
                                FlexMessage(
                                    alt_text="選擇題庫", contents=FlexContainer.from_dict(flex_content))
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
