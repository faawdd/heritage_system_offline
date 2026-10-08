from __future__ import annotations

import re
import unicodedata

from django.contrib.auth.hashers import check_password, make_password
from django.core.exceptions import ValidationError


SECURITY_QUESTION_BANK = [
    {'id': 'childhood_city', 'text': '您童年成长的城市或乡镇是？'},
    {'id': 'first_school', 'text': '您就读的第一所学校名称是？'},
    {'id': 'first_pet', 'text': '您养过的第一只宠物叫什么？'},
    {'id': 'favorite_teacher', 'text': '您最难忘的一位老师姓什么？'},
    {'id': 'first_job', 'text': '您的第一份工作是什么？'},
    {'id': 'favorite_book', 'text': '您少年时期最喜欢的一本书是？'},
    {'id': 'favorite_dish', 'text': '您最喜欢的一道家常菜是？'},
    {'id': 'first_trip', 'text': '您第一次独自旅行去了哪里？'},
    {'id': 'childhood_nickname', 'text': '您小时候家人常叫您的昵称是？'},
    {'id': 'favorite_sport', 'text': '您最喜欢的一项运动是？'},
    {'id': 'parent_hometown', 'text': '您父亲或母亲的出生地是？'},
    {'id': 'memorable_teacher_subject', 'text': '您学生时代最喜欢哪一门课程？'},
]
QUESTION_TEXT_BY_ID = {item['id']: item['text'] for item in SECURITY_QUESTION_BANK}

LOGIN_WAIT_THRESHOLD = 5
LOGIN_LOCK_THRESHOLD = 10
LOGIN_WAIT_SECONDS = 120
RECOVERY_WAIT_THRESHOLD = 5
RECOVERY_WAIT_SECONDS = 900


def normalize_answer(answer: object) -> str:
    value = unicodedata.normalize('NFKC', str(answer or '')).casefold()
    return re.sub(r'\s+', '', value)


def hash_security_questions(raw_questions: object) -> list[dict[str, str]]:
    if not isinstance(raw_questions, list) or len(raw_questions) != 3:
        raise ValidationError('必须设置恰好 3 个密码保护问题')

    question_ids = []
    hashed_questions = []
    for item in raw_questions:
        if not isinstance(item, dict):
            raise ValidationError('密码保护问题格式错误')
        question_id = str(item.get('question_id') or '').strip()
        answer = normalize_answer(item.get('answer'))
        if question_id not in QUESTION_TEXT_BY_ID:
            raise ValidationError('包含无效的密码保护问题')
        if len(answer) < 2:
            raise ValidationError('每个密码保护答案至少需要 2 个字符')
        question_ids.append(question_id)
        hashed_questions.append({
            'question_id': question_id,
            'answer_hash': make_password(answer),
        })

    if len(set(question_ids)) != 3:
        raise ValidationError('请选择 3 个不同的密码保护问题')
    return hashed_questions


def public_security_questions(stored_questions: object) -> list[dict[str, str]]:
    if not isinstance(stored_questions, list) or len(stored_questions) != 3:
        return []
    prompts = []
    for item in stored_questions:
        question_id = str(item.get('question_id') or '') if isinstance(item, dict) else ''
        question_text = QUESTION_TEXT_BY_ID.get(question_id)
        if not question_text:
            return []
        prompts.append({'question_id': question_id, 'question': question_text})
    return prompts


def verify_security_answers(stored_questions: object, raw_answers: object) -> bool:
    if not isinstance(stored_questions, list) or len(stored_questions) != 3:
        return False
    if not isinstance(raw_answers, list) or len(raw_answers) != 3:
        return False

    answers_by_id = {}
    for item in raw_answers:
        if isinstance(item, dict):
            question_id = str(item.get('question_id') or '').strip()
            if question_id in answers_by_id:
                return False
            answers_by_id[question_id] = normalize_answer(item.get('answer'))

    if len(answers_by_id) != 3:
        return False

    for item in stored_questions:
        if not isinstance(item, dict):
            return False
        question_id = str(item.get('question_id') or '')
        answer = answers_by_id.get(question_id)
        answer_hash = str(item.get('answer_hash') or '')
        if not answer or not answer_hash or not check_password(answer, answer_hash):
            return False
    return True