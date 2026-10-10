"""四普系统（第四次全国文物普查数据库）HTTP 客户端。

只读访问：登录由用户在浏览器完成，这里使用其 Cookie 调用页面与 JSON 接口。
接口均由抓包解析得到：
    POST immovableListController.do?queryRelicList            文物列表（单页最多 90 条）
    GET  tBBdataBasicController.do?goCoverView / goBasicView  封面、基本信息（服务端渲染的表单）
    POST tBBdataConstituteController.do?getData               文物构成（constituteType=1/2）
    POST tBBdataPointsController.do?getData                   测点坐标
    POST tBBdataPhotoController.do?getData                    照片
    POST tBBdataDraftController.do?getData                    图纸
    POST tBBdataOtherController.do?getData                    其他资料
    POST tBBdataSampleController.do?getData                   标本
    POST tBBdataSpecialController.do?getData                  关联专项
    POST tBThreesurveyBasicController.do?getData              三普对应记录
    POST api/mapdata/list                                     文物矢量图（本体/保护范围/建控地带）
    GET  tBCommAttchController.do?showImg&realpath=...        图片原文件
"""
import json
import re
import threading
import urllib.parse
from html.parser import HTMLParser

import requests

SIPU_HOST = '202.41.243.152:9046'
SIPU_BASE = f'http://{SIPU_HOST}'
USER_AGENT = (
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/120.0 Safari/537.36'
)
LIST_PAGE_SIZE = 90  # 服务端单页上限，超出会被截断
IMAGE_EXTENSIONS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp')
LIST_REFERER = f'{SIPU_BASE}/immovableListController.do?immovableList'


class SipuError(Exception):
    pass


class SipuAuthError(SipuError):
    """Cookie 失效，或请求被四普系统拦截（返回“HTTP 400 请求无效”页面）。"""


class _FormParser(HTMLParser):
    """提取服务端渲染表单的当前取值：输入框、已选单选/复选项（含选项文字）、文本域、下拉框。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.items = []  # (name, kind, value, title)
        self._textarea = None
        self._select = None
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ('script', 'style'):
            self._skip += 1
        elif tag == 'input':
            kind = (a.get('type') or 'text').lower()
            if kind in ('button', 'submit', 'file', 'image', 'reset'):
                return
            if kind in ('radio', 'checkbox') and 'checked' not in a:
                return
            self.items.append((a.get('name') or a.get('id'), kind, a.get('value') or '', a.get('title') or a.get('label') or ''))
        elif tag == 'textarea':
            self._textarea = [a.get('name') or a.get('id'), '']
        elif tag == 'select':
            self._select = a.get('name') or a.get('id')
        elif tag == 'option' and self._select and 'selected' in a:
            self.items.append((self._select, 'select', a.get('value') or '', ''))

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self._skip = max(0, self._skip - 1)
        elif tag == 'textarea' and self._textarea:
            self.items.append((self._textarea[0], 'textarea', self._textarea[1].strip(), ''))
            self._textarea = None
        elif tag == 'select':
            self._select = None

    def handle_data(self, data):
        if self._textarea is not None and not self._skip:
            self._textarea[1] += data


def parse_form(html: str) -> dict:
    """返回 {'values': {name: 值或值列表}, 'labels': {name: {值: 选项文字}}, 'unnamed': [无name文本框的值]}。"""
    parser = _FormParser()
    parser.feed(html)
    values, labels, unnamed = {}, {}, []
    for name, kind, value, title in parser.items:
        if not name:
            if kind == 'text' and value:
                unnamed.append(value)
            continue
        if kind == 'checkbox' or (name in values and kind in ('radio', 'hidden', 'select')):
            current = values.get(name)
            if current is None:
                values[name] = [value] if kind == 'checkbox' else value
            else:
                lst = current if isinstance(current, list) else [current]
                if value and value not in lst:
                    lst.append(value)
                values[name] = lst if len(lst) > 1 or kind == 'checkbox' else lst[0]
        else:
            values[name] = value
        if title and kind in ('radio', 'checkbox'):
            labels.setdefault(name, {})[value] = title
    return {'values': values, 'labels': labels, 'unnamed': unnamed}


def dms_to_decimal(text):
    """'44-23-27.6046' / '44°23′27.6″' -> 44.391001...；无法解析返回 None。"""
    if text in (None, ''):
        return None
    try:
        return float(text)
    except (TypeError, ValueError):
        pass
    nums = re.findall(r'\d+(?:\.\d+)?', str(text))
    if len(nums) < 2:
        return None
    deg = float(nums[0])
    minute = float(nums[1])
    second = float(nums[2]) if len(nums) > 2 else 0.0
    return deg + minute / 60 + second / 3600


class SipuClient:
    def __init__(self, cookie: str, timeout: int = 30, retries: int = 3):
        cookie = (cookie or '').strip()
        if cookie and '=' not in cookie:
            cookie = f'JSESSIONID={cookie}'
        self.cookie = cookie
        self.timeout = timeout
        self.retries = retries
        self._local = threading.local()

    def _session(self):
        sess = getattr(self._local, 'session', None)
        if sess is None:
            sess = requests.Session()
            sess.headers.update({
                'User-Agent': USER_AGENT,
                'Cookie': self.cookie,
                'Accept': 'application/json, text/javascript, */*; q=0.01',
            })
            self._local.session = sess
        return sess

    def _request(self, method, path, data=None, referer=LIST_REFERER):
        url = path if path.startswith('http') else f'{SIPU_BASE}/{path}'
        headers = {'Referer': referer, 'X-Requested-With': 'XMLHttpRequest'}
        if method == 'POST':
            headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        last = None
        for attempt in range(self.retries):
            try:
                resp = self._session().request(method, url, data=data, headers=headers, timeout=self.timeout)
                if resp.status_code >= 500:
                    raise SipuError(f'四普系统返回 {resp.status_code}')
                return resp
            except (requests.RequestException, SipuError) as exc:
                last = exc
        raise SipuError(f'请求四普系统失败：{last}')

    def post_json(self, path, data=None, referer=LIST_REFERER):
        resp = self._request('POST', path, data=data or {}, referer=referer)
        try:
            return json.loads(resp.content.decode('utf-8', errors='replace'))
        except ValueError:
            raise SipuAuthError('四普系统返回了非 JSON 内容，Cookie 可能已失效或请求被拦截，请重新登录后复制最新 Cookie')

    def get_html(self, path, referer=LIST_REFERER):
        resp = self._request('GET', path, referer=referer)
        text = resp.content.decode('utf-8', errors='replace')
        if '<title>HTTP 400' in text:
            raise SipuAuthError('四普系统拒绝了请求，Cookie 可能已失效，请重新登录后复制最新 Cookie')
        return text

    # ── 列表 ────────────────────────────────────────────────────────────
    def list_page(self, page, category='', keyword='', page_size=LIST_PAGE_SIZE, user_county=''):
        form = {
            'page': str(page), 'pageSize': str(page_size), 'searchInputValue': keyword,
            'sortField': 'code', 'sortType': 'asc', 'backStatus': '0',
        }
        if category:
            form['category'] = category
        if user_county:
            form['userCounty'] = user_county
        payload = self.post_json('immovableListController.do?queryRelicList', form)
        return payload.get('data') or [], int(payload.get('count') or 0)

    def detect_account_scope(self):
        """读取列表页内嵌的账号角色与辖区：roleStatus 15=区县、25=市级、35=省级、45=国家。"""
        html = self.get_html('immovableListController.do?immovableList')
        scope = {}
        for var, key in (('roleStatus', 'role'), ('userProvince', 'province'), ('userCity', 'city'), ('userCounty', 'county')):
            match = re.search(r"const\s+" + var + r"\s*=\s*[\"'](\w*)[\"']", html)
            scope[key] = match.group(1) if match else ''
        return scope

    def load_dictionaries(self):
        """从列表页内嵌的 JSON 字典读取子类别名称、保护级别。"""
        html = self.get_html('immovableListController.do?immovableList')
        result = {}
        for var, key in (('allCategoryDict', 'category'), ('rankDict', 'rank')):
            match = re.search(r"const\s+" + var + r"\s*=\s*JSON\.parse\('(.*?)'\)", html)
            result[key] = {}
            if match:
                try:
                    result[key] = {i['typecode']: i['typename'] for i in json.loads(match.group(1))}
                except (ValueError, KeyError, TypeError):
                    pass
        return result

    # ── 详情 ────────────────────────────────────────────────────────────
    def _detail_referer(self, cul_rid):
        return f'{SIPU_BASE}/tBBdataBasicController.do?viewDetail&id={urllib.parse.quote(cul_rid)}'

    def fetch_form(self, cul_rid, which):
        rid = urllib.parse.quote(cul_rid)
        if which == 'cover':
            path = f'tBBdataBasicController.do?goCoverView&type=&culRid={rid}&searchtype=&threeIds='
        else:
            path = f'tBBdataBasicController.do?goBasicView&type=&culRid={rid}'
        return parse_form(self.get_html(path, referer=self._detail_referer(cul_rid)))

    def fetch_rows(self, controller_path, cul_rid, extra_query=''):
        """分页读取 getData 类接口，返回全部 rows。"""
        rows, page = [], 1
        while True:
            path = f'{controller_path}?getData{extra_query}&currpage={page}&pagecount=100'
            payload = self.post_json(path, {'culRid': cul_rid}, referer=self._detail_referer(cul_rid))
            batch = payload.get('rows') or []
            rows.extend(batch)
            if not batch or len(rows) >= int(payload.get('total') or 0):
                return rows
            page += 1

    def fetch_photo_link_label(self, photo_id):
        """照片“关联类型”文字（如 全景照片、保护标志处），由 tstypeN 代码在服务端解析。"""
        payload = self.post_json(
            'queryController.do?selectPhotoLinktype&isView=1', {'id': photo_id, 'typecode': ''},
        )
        return re.sub(r'<[^>]+>', '', payload.get('html') or '').strip()

    def fetch_mapdata_rings(self, cul_rid):
        payload = self.post_json(
            'api/mapdata/list', {'id': cul_rid, 'table': '5'}, referer=self._detail_referer(cul_rid),
        )
        result = {'body': [], 'protection': [], 'control': []}
        for item in ((payload.get('data') or {}).get('data')) or []:
            try:
                geom = json.loads(item.get('geojson') or '')
            except ValueError:
                continue
            if geom.get('type') == 'Polygon':
                candidates = geom.get('coordinates') or []
            elif geom.get('type') == 'MultiPolygon':
                candidates = [ring for poly in (geom.get('coordinates') or []) for ring in poly]
            else:
                candidates = []
            rings = [
                [[round(float(pt[0]), 7), round(float(pt[1]), 7)] for pt in ring]
                for ring in candidates if isinstance(ring, list) and len(ring) >= 3
            ]
            region = item.get('region_type') or ''
            if '本体' in region:
                result['body'].extend(rings)
            elif '保护' in region:
                result['protection'].extend(rings)
            elif '建' in region or '控' in region:
                result['control'].extend(rings)
        return result

    def download_image(self, real_path):
        """下载原图；仅处理图片扩展名（PDF 等附件四普只返回图标），失败时返回 None。"""
        if not real_path.lower().endswith(IMAGE_EXTENSIONS):
            return None
        url = f'tBCommAttchController.do?showImg&realpath={urllib.parse.quote(real_path, safe="/")}'
        resp = self._request('GET', url)
        content_type = resp.headers.get('Content-Type', '')
        data = resp.content
        if resp.status_code != 200 or not data or not content_type.startswith('image/'):
            return None
        if not (data[:3] == b'\xff\xd8\xff' or data[:8] == b'\x89PNG\r\n\x1a\n' or data[:3] == b'GIF' or data[:2] == b'BM'):
            return None
        return data
