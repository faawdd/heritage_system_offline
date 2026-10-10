"""不可移动文物字段自动推断：从地址、简介/备注文本、三普对应记录中提取乡镇、村、曾用名等。

全部规则基于全国通用的行政区划后缀与行文习惯，不包含任何具体地名；
省/市/县名称由调用方按文物自身的行政区划传入，用于剥离地址前缀。
"""
import re

_CN = r'[\u4e00-\u9fa5]'
_PUNCT = '，,。；;：:、（(【[\n'

# 上级行政区划（省、地级、县级）：最短匹配，如“新疆维吾尔自治区”“吐鲁番地区”“鄯善县”
_ADMIN_CHAR = rf'(?:(?![镇乡村街社]){_CN})'
_ADMIN_HIGH = re.compile(rf'^{_ADMIN_CHAR}{{1,10}}?(?:自治区|特别行政区|自治州|自治县|自治旗|地区|盟|省|市|县|旗|区)')
# 乡镇级（含民族乡、街道、苏木）
_TOWNSHIP = re.compile(rf'(?P<n>{_CN}{{1,9}}?(?:街道办事处|街道|镇|乡|苏木|办事处))')
# 村级（村、社区、嘎查等），后缀“村委会/村民委员会”归一为“村”
_VILLAGE = re.compile(
    rf'(?P<n>{_CN}{{1,8}}?)(?P<s>村民委员会|村委会|村|社区居委会|社区|居委会|嘎查|牧委会)'
)
_TOWNSHIP_OR_VILLAGE_MARK = re.compile(r'[镇乡村]|街道|苏木|社区|嘎查')


def _strip_leading_admin(text, known_names):
    """依次剥离地址开头的省/市/县名称（含重复书写的情况），返回剩余部分。"""
    known = sorted({n for n in known_names if n}, key=len, reverse=True)
    for _ in range(8):
        text = text.lstrip(' ，,、')
        hit = next((n for n in known if text.startswith(n)), None)
        if hit:
            text = text[len(hit):]
            continue
        match = _ADMIN_HIGH.match(text)
        if not match:
            break
        rest = text[match.end():]
        # 避免把“新区镇”之类的乡镇名误当作上级区划
        if re.match(r'^(?:镇|乡|街道|苏木)', rest) or not _TOWNSHIP_OR_VILLAGE_MARK.search(rest[:40]):
            break
        text = rest
    return text


def parse_address(address, region_names=()):
    """拆分地址，返回 {'township': ..., 'village': ...}，未识别的项为空字符串。"""
    result = {'township': '', 'village': ''}
    text = re.sub(r'\s+', '', str(address or ''))
    if not text:
        return result
    text = _strip_leading_admin(text, region_names)
    # 只解析第一个标点之前的行政区划描述，避免命中后面“距某某镇政府”等方位描述
    head = re.split('[' + re.escape(_PUNCT) + ']', text, maxsplit=1)[0]

    township = _TOWNSHIP.match(head)
    if township:
        result['township'] = township.group('n')
        head = head[township.end():]
    village = _VILLAGE.match(head)
    if village:
        suffix = village.group('s')
        suffix = '村' if suffix.startswith('村') else suffix.replace('居委会', '')
        result['village'] = village.group('n') + suffix
    else:
        # 地址里写“某某1组”等形式时，从“某某村民委员会”的方位描述里补出村名
        anywhere = _VILLAGE_ANYWHERE.search(text)
        if anywhere and not _TOWNSHIP.fullmatch(anywhere.group('n')):
            result['village'] = anywhere.group('n') + '村'
    return result


_SENTENCE_SPLIT = re.compile(r'[。；;\n]')
_BATCH = re.compile(r'第([一二三四五六七八九十百零\d]+)批')
_FULL_DATE = re.compile(r'(\d{4})年(\d{1,2})月(\d{1,2})日')
_ALIAS = re.compile(
    r'(?:原名称?为|原称|又名|亦称|又称|俗称|旧称|曾用名为?|曾称)(?P<n>[^，,。；;、（）()\s]{2,20})'
)
_NOT_A_NAME = re.compile(r'位于|地处|坐落|分布|距|座落')
_VILLAGE_ANYWHERE = re.compile(rf'(?P<n>{_CN}{{1,8}}?)(?:村民委员会|村委会)')
_DAMAGE = re.compile(r'损毁|破坏|坍塌|倒塌|垮塌|风蚀|盗掘|盗扰|盗洞|开裂|残损|塌陷|毁坏|冲毁|雨蚀|酥碱')
_DAMAGE_NEGATED = re.compile(r'(?:未|无|没有|不曾|尚未|免受)[^，,；;]{0,6}(?:损毁|破坏|坍塌|倒塌|垮塌|风蚀|盗掘|盗扰|盗洞|开裂|残损|塌陷|毁坏|冲毁)')
_RELOCATE = re.compile(r'将其迁|迁建至|整体(?:搬迁|迁)|本体(?:被)?(?:搬迁|迁)|原址(?:被)?(?:搬迁|迁)|异地(?:迁|保护|重建)')
_NOT_HERITAGE_SUBJECT = re.compile(r'村民|居民|住户|牧民|农户')
_MARKER = re.compile(r'保护标志|标志碑|标志牌|说明牌|界桩|保护碑')
_MARKER_NEGATION = re.compile(r'未(?:设|立|见)|无保护标志|没有|尚无|缺失')

_CN_DIGITS = {'零': 0, '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}


def _sentences(text):
    return [s.strip() for s in _SENTENCE_SPLIT.split(text or '') if s.strip()]


def _trim(text, limit):
    return text if len(text) <= limit else text[:limit - 1] + '…'


def infer_from_text(text, name=''):
    """从简介/备注等自由文本推断字段，只返回有把握的项。"""
    result = {}
    sentences = _sentences(text)

    for sentence in sentences:
        alias = _ALIAS.search(sentence)
        if alias and alias.group('n') != name and not _NOT_A_NAME.search(alias.group('n')):
            result['former_name'] = _trim(alias.group('n'), 200)
            break

    for sentence in sentences:
        if '保护单位' in sentence and '尚未核定' not in sentence:
            batch = _BATCH.search(sentence)
            if batch:
                result['protection_announced_batch'] = batch.group(0)
                date = _FULL_DATE.search(sentence)
                if date:
                    result['protection_announced_date'] = '-'.join(
                        f'{int(g):02d}' if i else g for i, g in enumerate(date.groups())
                    )
                break

    damage = [s for s in sentences if _DAMAGE.search(s) and not _DAMAGE_NEGATED.search(s)]
    if damage:
        result['damage_cause'] = _trim('；'.join(damage[:2]), 400)

    relocate = next(
        (s for s in sentences if _RELOCATE.search(s) and not _NOT_HERITAGE_SUBJECT.search(s)), '')
    if relocate:
        result['is_relocated'] = True
        result['relocation_note'] = _trim(relocate, 400)

    marker = [s for s in sentences if _MARKER.search(s)]
    if marker:
        result['has_marker_stele'] = not any(_MARKER_NEGATION.search(s) for s in marker)

    return result


def infer_from_threesurvey(records, name=''):
    """三普对应记录：三普编号、三普时期名称（与现名不同则视为曾用名）。"""
    codes, former = [], ''
    for record in records or []:
        code = str(record.get('unit_no') or '').strip()
        if code and code not in codes:
            codes.append(code)
        old_name = str(record.get('unit_name') or '').strip()
        if old_name and old_name != name and not former and not _NOT_A_NAME.search(old_name):
            former = old_name
    result = {}
    if codes:
        result['previous_survey_code'] = _trim('、'.join(codes), 50)
    if former:
        result['former_name'] = _trim(former, 200)
    return result


def infer_all(*, address, region_names, text, name, threesurvey, change_label='', photo_labels=()):
    """汇总推断结果。优先级：三普编号 > 文本；曾用名文本优先于三普名称。"""
    result = {}
    result.update({k: v for k, v in parse_address(address, region_names).items() if v})
    three = infer_from_threesurvey(threesurvey, name)
    from_text = infer_from_text(text, name)
    result.update(three)
    result.update(from_text)
    if 'former_name' in three and 'former_name' not in from_text:
        result['former_name'] = three['former_name']

    if any('保护标志' in label for label in photo_labels):
        result['has_marker_stele'] = True
    if re.search(r'消失|灭失', change_label or ''):
        result['is_disappeared'] = True
    if re.search(r'搬迁|迁建|迁移', change_label or ''):
        result['is_relocated'] = True
    return result
