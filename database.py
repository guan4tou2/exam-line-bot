import sqlite3
from datetime import datetime
import json


class Database:
    def __init__(self, db_file="user_records.db"):
        self.db_file = db_file
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_file)

    def init_db(self):
        """初始化數據庫表結構"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 用戶當前狀態表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_states (
                    user_id TEXT PRIMARY KEY,
                    current_database TEXT,
                    last_active TIMESTAMP
                )
            ''')

            # 答題記錄表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS answer_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    question_id INTEGER,
                    database_name TEXT,
                    user_answer TEXT,
                    correct_answer TEXT,
                    is_correct BOOLEAN,
                    answer_time TIMESTAMP,
                    question_data TEXT,
                    is_wrong_question_practice BOOLEAN DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES user_states(user_id)
                )
            ''')

            # 錯題統計表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS wrong_questions (
                    user_id TEXT,
                    question_id INTEGER,
                    database_name TEXT,
                    wrong_count INTEGER DEFAULT 1,
                    last_wrong_time TIMESTAMP,
                    PRIMARY KEY (user_id, question_id, database_name),
                    FOREIGN KEY (user_id) REFERENCES user_states(user_id)
                )
            ''')

            conn.commit()

    def update_user_state(self, user_id, database_name):
        """更新用戶當前使用的題庫"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO user_states (user_id, current_database, last_active)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    current_database = excluded.current_database,
                    last_active = excluded.last_active
            ''', (user_id, database_name, datetime.now()))
            conn.commit()

    def get_user_state(self, user_id):
        """獲取用戶當前狀態"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT current_database FROM user_states WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            return result[0] if result else None

    def record_answer(self, user_id, question_data, user_answer, is_correct, database_name, is_wrong_question_practice=False):
        """記錄用戶答題"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 記錄答題歷史
            cursor.execute('''
                INSERT INTO answer_records 
                (user_id, question_id, database_name, user_answer, correct_answer, 
                is_correct, answer_time, question_data, is_wrong_question_practice)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_id,
                question_data['id'],
                database_name,
                user_answer,
                question_data['answer'],
                is_correct,
                datetime.now(),
                json.dumps(question_data),
                is_wrong_question_practice
            ))

            # 如果答錯了，更新錯題統計
            if not is_correct:
                cursor.execute('''
                    INSERT INTO wrong_questions (user_id, question_id, database_name, wrong_count, last_wrong_time)
                    VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(user_id, question_id, database_name) DO UPDATE SET
                        wrong_count = wrong_count + 1,
                        last_wrong_time = excluded.last_wrong_time
                ''', (user_id, question_data['id'], database_name, datetime.now()))

            conn.commit()

    def get_wrong_questions(self, user_id, database_name=None, limit=10):
        """獲取用戶的錯題列表"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            query = '''
                SELECT w.question_id, w.database_name, w.wrong_count, 
                       MAX(a.question_data) as question_data
                FROM wrong_questions w
                JOIN answer_records a ON w.question_id = a.question_id 
                    AND w.user_id = a.user_id 
                    AND w.database_name = a.database_name
                WHERE w.user_id = ?
            '''
            params = [user_id]

            if database_name:
                query += ' AND w.database_name = ?'
                params.append(database_name)

            query += '''
                GROUP BY w.question_id, w.database_name
                ORDER BY w.wrong_count DESC, w.last_wrong_time DESC
                LIMIT ?
            '''
            params.append(limit)

            cursor.execute(query, params)
            results = cursor.fetchall()

            wrong_questions = []
            for row in results:
                question_data = json.loads(row[3])
                wrong_questions.append({
                    'question_id': row[0],
                    'database_name': row[1],
                    'wrong_count': row[2],
                    'question_data': question_data
                })

            return wrong_questions

    def get_total_questions(self, database_name):
        """獲取指定題庫的總題目數"""
        try:
            with open(f'database/{database_name}.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                return len(data.get('questions', []))
        except Exception as e:
            print(f"Error getting total questions: {e}")
            return 0

    def get_user_statistics(self, user_id, database_name):
        """獲取用戶的答題統計"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 修改查詢，使用DISTINCT計算不重複的題目數
            query = '''
                SELECT 
                    COUNT(DISTINCT question_id) as total_answers,
                    COUNT(DISTINCT CASE WHEN is_correct = 1 THEN question_id END) as correct_answers,
                    (SELECT COUNT(DISTINCT question_id) FROM wrong_questions 
                     WHERE user_id = ? AND database_name = ?) as total_wrong_questions
                FROM answer_records
                WHERE user_id = ? 
                AND database_name = ?
                AND is_wrong_question_practice = 0
            '''

            cursor.execute(
                query, (user_id, database_name, user_id, database_name))
            result = cursor.fetchone()

            total_answers = result[0] or 0  # 避免 None 值
            correct_answers = result[1] or 0
            total_wrong_questions = result[2] or 0

            # 獲取題庫總題目數
            total_questions = self.get_total_questions(database_name)

            # 獲取錯題練習的統計
            cursor.execute('''
                SELECT 
                    COUNT(DISTINCT question_id) as practice_count,
                    COUNT(DISTINCT CASE WHEN is_correct = 1 THEN question_id END) as practice_correct
                FROM answer_records
                WHERE user_id = ? 
                AND database_name = ?
                AND is_wrong_question_practice = 1
            ''', (user_id, database_name))

            practice_result = cursor.fetchone()
            practice_count = practice_result[0] or 0
            practice_correct = practice_result[1] or 0

            return {
                'total_answers': total_answers,
                'correct_answers': correct_answers,
                'accuracy_rate': (correct_answers / total_answers * 100) if total_answers > 0 else 0,
                'total_wrong_questions': total_wrong_questions,
                'total_questions': total_questions,
                'completion_rate': (total_answers / total_questions * 100) if total_questions > 0 else 0,
                'practice_count': practice_count,
                'practice_correct': practice_correct,
                'practice_accuracy_rate': (practice_correct / practice_count * 100) if practice_count > 0 else 0
            }

    def get_question_attempt_stats(self, question_id, database_name):
        """获取题目的作答统计信息"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # 查询题目的作答次数和答对次数
                query = '''
                    SELECT 
                        COUNT(*) as total_attempts,
                        SUM(CASE WHEN is_correct = 1 THEN 1 ELSE 0 END) as correct_attempts
                    FROM answer_records
                    WHERE question_id = ? 
                    AND database_name = ?
                    AND is_wrong_question_practice = 0
                '''

                cursor.execute(query, (question_id, database_name))
                result = cursor.fetchone()

                return {
                    'total_attempts': result[0] or 0,  # 避免 None 值
                    'correct_attempts': result[1] or 0
                }
        except Exception as e:
            print(f"Error getting question attempt stats: {e}")
            return {
                'total_attempts': 0,
                'correct_attempts': 0
            }
