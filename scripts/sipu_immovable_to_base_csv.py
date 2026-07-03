#!/usr/bin/env python3
"""
抓取四普系统不可移动文物列表，并转换为本系统“基础数据导入（CSV）”可直接使用的模板。

示例：
python3 scripts/sipu_immovable_to_base_csv.py \
  --base-url http://202.41.243.152:9046 \
  --jsessionid B7B35CAB7A603378896959F2C455E8CA \
  --user-county 650421 \
  --output data/sipu_base_data.csv
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import re
import sys
import threading
import time
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests


CSV_HEADERS = [
    "采集编号",
    "文物名称",
    "时代",
    "文物类别",
    "保护级别",
    "权属",
    "保存现状",
    "省/自治区/直辖市",
    "市/州",
    "县/市/区",
    "乡镇/街道",
    "村/社区",
    "详细地址",
    "经度",
    "纬度",
    "管理责任人",
    "文物简介",
    "备注",
]


# 四普行政区代码到中文名称（常用值，可按需扩展）
PROVINCE_MAP = {
    "650000": "新疆维吾尔自治区",
}
CITY_MAP = {
    "650400": "吐鲁番市",
}
COUNTY_MAP = {
    "650421": "鄯善县",
}


# 四普 category/subcategory 到本系统“文物类别”中文标签的容错映射。
# 本系统合法值：古文化遗址、古墓葬、古建筑、石窟寺及石刻、近现代重要史迹及代表性建筑、其他
CATEGORY_MAP = {
    "0100": "古文化遗址",
    "0200": "古墓葬",
    "0300": "古建筑",
    "0400": "石窟寺及石刻",
    "0500": "近现代重要史迹及代表性建筑",
    "0600": "其他",
    # 已知：坎儿井在样例中出现 0113 / 0511，统一归入古文化遗址
    "0113": "古文化遗址",
    "0511": "古文化遗址",
}


RANK_TO_LEVEL = {
    "1": "全国重点文物保护单位",
    "2": "省（自治区、直辖市）级文物保护单位",
    "3": "市（县）级文物保护单位",
    "4": "尚未定级的不可移动文物",
}


TOWNSHIP_PATTERN = re.compile(r"([\u4e00-\u9fa5]{1,16}(?:回族乡|街道|镇|乡))")
VILLAGE_PATTERN = re.compile(r"([\u4e00-\u9fa5A-Za-z0-9]{1,24}(?:村|社区))(?:\d+组)?")


@dataclass
class FetchConfig:
    base_url: str
    endpoint: str
    detail_endpoint: str
    jsessionid: str
    user_county: str
    page_size: int
    timeout: int
    max_pages: Optional[int]
    sort_field: str
    sort_type: str
    back_status: str


class SipuClient:
    def __init__(self, cfg: FetchConfig):
        self.cfg = cfg
        self.session = requests.Session()

    def _build_url(self) -> str:
        return f"{self.cfg.base_url.rstrip('/')}/{self.cfg.endpoint.lstrip('/')}"

    def _headers(self) -> Dict[str, str]:
        base = self.cfg.base_url.rstrip("/")
        return {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
            "Origin": base,
            "Referer": f"{base}/immovableListController.do?immovableList&curr_functionId=202312110000053",
            "X-Requested-With": "XMLHttpRequest",
            "Cookie": f"JSESSIONID={self.cfg.jsessionid}",
            "User-Agent": "Mozilla/5.0",
        }

    def _decode_text(self, raw: bytes) -> str:
        # 部分页面 header 声明为 ISO-8859-1，但正文实际是 UTF-8/GBK。
        for encoding in ("utf-8", "gb18030", "gbk", "big5", "iso-8859-1"):
            try:
                return raw.decode(encoding)
            except UnicodeDecodeError:
                continue
        return raw.decode("utf-8", errors="replace")

    def fetch_page(self, page: int) -> Tuple[List[dict], int]:
        payload = {
            "page": str(page),
            "pageSize": str(self.cfg.page_size),
            "searchInputValue": "",
            "userCounty": self.cfg.user_county,
            "sortField": self.cfg.sort_field,
            "sortType": self.cfg.sort_type,
            "backStatus": self.cfg.back_status,
        }

        resp = self.session.post(
            self._build_url(),
            data=payload,
            headers=self._headers(),
            timeout=self.cfg.timeout,
        )
        resp.raise_for_status()

        data = resp.json()
        status = str(data.get("status", ""))
        if status and status != "200":
            raise RuntimeError(f"四普接口返回非成功状态: status={status}, body={data}")

        rows = data.get("data") or []
        total = int(data.get("count") or 0)
        return rows, total

    def fetch_detail_html(self, cul_rid: str, page_type: str = "") -> str:
        params = {
            "type": page_type,
            "culRid": cul_rid,
        }
        detail_url = f"{self.cfg.base_url.rstrip('/')}/{self.cfg.detail_endpoint.lstrip('/')}"
        resp = self.session.get(
            detail_url,
            params=params,
            headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Referer": f"{self.cfg.base_url.rstrip('/')}/tBBdataBasicController.do?viewDetail&id={cul_rid}",
                "Cookie": f"JSESSIONID={self.cfg.jsessionid}",
                "User-Agent": "Mozilla/5.0",
            },
            timeout=self.cfg.timeout,
        )
        resp.raise_for_status()
        return self._decode_text(resp.content)


def decode_text(raw: bytes) -> str:
    for encoding in ("utf-8", "gb18030", "gbk", "big5", "iso-8859-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def fetch_detail_html_once(cfg: FetchConfig, jsessionid: str, cul_rid: str, page_type: str = "") -> str:
    base = cfg.base_url.rstrip("/")
    detail_url = f"{base}/{cfg.detail_endpoint.lstrip('/')}"
    resp = requests.get(
        detail_url,
        params={"type": page_type, "culRid": cul_rid},
        headers={
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Referer": f"{base}/tBBdataBasicController.do?viewDetail&id={cul_rid}",
            "Cookie": f"JSESSIONID={jsessionid}",
            "User-Agent": "Mozilla/5.0",
        },
        timeout=cfg.timeout,
    )
    resp.raise_for_status()
    return decode_text(resp.content)


class ProgressBar:
    def __init__(self, total: int, width: int = 34):
        self.total = max(total, 1)
        self.width = max(width, 10)
        self.current = 0
        self.start_ts = time.time()
        self.lock = threading.Lock()

    def update(self, step: int = 1, suffix: str = "") -> None:
        with self.lock:
            self.current += step
            if self.current > self.total:
                self.current = self.total

            ratio = self.current / self.total
            done = int(self.width * ratio)
            bar = "#" * done + "-" * (self.width - done)
            elapsed = time.time() - self.start_ts
            speed = self.current / elapsed if elapsed > 0 else 0.0
            msg = (
                f"\r[progress] [{bar}] {self.current}/{self.total} "
                f"({ratio * 100:6.2f}%) {speed:5.1f} item/s"
            )
            if suffix:
                msg += f" | {suffix}"
            print(msg, end="", flush=True)

            if self.current >= self.total:
                print()


class BasicViewParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.input_values: Dict[str, str] = {}
        self.checked_inputs: List[Dict[str, str]] = []
        self._textarea_id: Optional[str] = None
        self.textarea_values: Dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        attr_map = {k: v if v is not None else "" for k, v in attrs}
        if tag == "input":
            id_value = attr_map.get("id", "")
            if id_value:
                self.input_values[id_value] = attr_map.get("value", "")
            if "checked" in attr_map:
                self.checked_inputs.append(attr_map)

        if tag == "textarea":
            self._textarea_id = attr_map.get("id", "")
            if self._textarea_id and self._textarea_id not in self.textarea_values:
                self.textarea_values[self._textarea_id] = ""

    def handle_data(self, data):
        if self._textarea_id:
            self.textarea_values[self._textarea_id] = self.textarea_values.get(self._textarea_id, "") + data

    def handle_endtag(self, tag):
        if tag == "textarea":
            self._textarea_id = None


def extract_checked_labels(parser: BasicViewParser, input_name: str) -> List[str]:
    labels: List[str] = []
    for item in parser.checked_inputs:
        if item.get("name") != input_name:
            continue
        label = (item.get("label") or "").strip()
        if label:
            labels.append(label)
    return labels


def ownership_from_labels(labels: List[str]) -> str:
    joined = "、".join(labels)
    if "国家" in joined:
        return "国有"
    if "集体" in joined:
        return "集体"
    if "私人" in joined or "个人" in joined:
        return "私人"
    if labels:
        return "其他"
    return "国有"


def parse_detail_payload(html: str) -> Dict[str, str]:
    parser = BasicViewParser()
    parser.feed(html)

    preservation_labels = extract_checked_labels(parser, "stateevaluation")
    ownership_labels = extract_checked_labels(parser, "ownership")
    impact_labels = extract_checked_labels(parser, "protectelement")
    protect_labels = extract_checked_labels(parser, "protectrule")

    is_publish_area = "是" if any(v in {"是", "1"} for v in extract_checked_labels(parser, "isPublishArea")) else "否"
    is_publish_control = "是" if any(v in {"是", "1"} for v in extract_checked_labels(parser, "isPublishControl")) else "否"

    brief = (parser.textarea_values.get("brief") or "").strip()
    remark = (parser.textarea_values.get("remark") or "").strip()

    payload = {
        "era": (parser.input_values.get("year") or "").strip(),
        "ownership": ownership_from_labels(ownership_labels),
        "preservation": preservation_labels[0].strip() if preservation_labels else "",
        "manager": (parser.input_values.get("vestin") or "").strip() or (parser.input_values.get("owner") or "").strip(),
        "brief": brief,
        "impact": "、".join([x for x in impact_labels if x.strip()]),
        "protect": "、".join([x for x in protect_labels if x.strip()]),
        "publish_status": f"保护范围:{is_publish_area}; 建设控制地带:{is_publish_control}",
        "detail_remark": remark,
    }
    return payload



def dms_like_to_decimal(text: str) -> Optional[Decimal]:
    """
    兼容四普常见格式：
    - 42-45-42.8891
    - 42,45,42.8891
    - 42 45 42.8891
    - 89.68123
    """
    raw = str(text or "").strip()
    if not raw:
        return None

    # 四普列表常见格式是 "42-45-42.8891"，这里的 '-' 是分隔符，不是负号。
    if re.fullmatch(r"\d+(?:\.\d+)?-\d+(?:\.\d+)?-\d+(?:\.\d+)?", raw):
        raw = raw.replace("-", " ")

    # 先尝试直接十进制度
    try:
        return Decimal(raw)
    except InvalidOperation:
        pass

    parts = [p for p in re.split(r"[^0-9.\-]+", raw) if p]
    if len(parts) < 3:
        return None

    try:
        degree = Decimal(parts[0])
        minute = Decimal(parts[1])
        second = Decimal(parts[2])
    except InvalidOperation:
        return None

    sign = Decimal("-1") if degree < 0 else Decimal("1")
    degree = abs(degree)
    value = degree + minute / Decimal("60") + second / Decimal("3600")
    return sign * value



def choose_category(item: dict) -> str:
    sub = str(item.get("subcategory") or "").strip()
    cat = str(item.get("category") or "").strip()
    if sub in CATEGORY_MAP:
        return CATEGORY_MAP[sub]
    if cat in CATEGORY_MAP:
        return CATEGORY_MAP[cat]
    return "其他"



def choose_level(item: dict) -> str:
    rank = str(item.get("rank") or "").strip()
    return RANK_TO_LEVEL.get(rank, "尚未定级的不可移动文物")



def resolve_region_name(code: str, mapping: Dict[str, str], fallback: str) -> str:
    text = str(code or "").strip()
    if text and text in mapping:
        return mapping[text]
    return fallback



def extract_township_and_village(address: str) -> Tuple[str, str]:
    text = str(address or "").strip()
    township = ""
    village = ""

    t_match = TOWNSHIP_PATTERN.search(text)
    if t_match:
        township = t_match.group(1)

    v_match = VILLAGE_PATTERN.search(text)
    if v_match:
        village = v_match.group(1)

    return township, village



def to_csv_row(item: dict) -> Optional[Dict[str, str]]:
    name = str(item.get("name") or "").strip()
    code = str(item.get("code") or "").strip()
    address = str(item.get("address") or "").strip()
    era = str(item.get("niandai") or "").strip() or "未详"

    lng = dms_like_to_decimal(str(item.get("longitude") or ""))
    lat = dms_like_to_decimal(str(item.get("latitude") or ""))

    if not name or not address or lng is None or lat is None:
        return None

    province = resolve_region_name(item.get("province"), PROVINCE_MAP, "新疆维吾尔自治区")
    city = resolve_region_name(item.get("city"), CITY_MAP, "吐鲁番市")
    county = resolve_region_name(item.get("country"), COUNTY_MAP, "鄯善县")
    township, village = extract_township_and_village(address)

    row = {
        "采集编号": code,
        "文物名称": name,
        "时代": era,
        "文物类别": choose_category(item),
        "保护级别": choose_level(item),
        "权属": "国有",
        "保存现状": "一般",
        "省/自治区/直辖市": province,
        "市/州": city,
        "县/市/区": county,
        "乡镇/街道": township,
        "村/社区": village,
        "详细地址": address,
        "经度": f"{lng:.8f}",
        "纬度": f"{lat:.8f}",
        "管理责任人": "",
        "文物简介": "",
        "备注": f"source_id={item.get('id', '')}; category={item.get('category', '')}; subcategory={item.get('subcategory', '')}; rank={item.get('rank', '')}",
    }
    return row


def merge_detail_into_row(row: Dict[str, str], detail: Dict[str, str]) -> Dict[str, str]:
    if detail.get("era"):
        row["时代"] = detail["era"]
    if detail.get("ownership"):
        row["权属"] = detail["ownership"]
    if detail.get("preservation"):
        row["保存现状"] = detail["preservation"]
    if detail.get("manager"):
        row["管理责任人"] = detail["manager"]
    if detail.get("brief"):
        row["文物简介"] = detail["brief"]

    extra_notes = [
        f"影响因素={detail.get('impact', '')}" if detail.get("impact") else "",
        f"保护措施={detail.get('protect', '')}" if detail.get("protect") else "",
        detail.get("publish_status", ""),
        f"detail_remark={detail.get('detail_remark', '')}" if detail.get("detail_remark") else "",
    ]
    extra_notes = [x for x in extra_notes if x]
    if extra_notes:
        row["备注"] = f"{row.get('备注', '')}; " + "; ".join(extra_notes)
    return row


def build_row_for_item(item: dict, cfg: FetchConfig, args: argparse.Namespace) -> Tuple[str, Optional[Dict[str, str]], str]:
    row = to_csv_row(item)
    if row is None:
        return "skipped", None, "坐标或基础字段缺失"

    if args.skip_detail:
        return "ok", row, ""

    cul_rid = str(item.get("id") or "").strip()
    if not cul_rid:
        return "ok", row, ""

    try:
        detail_html = fetch_detail_html_once(cfg=cfg, jsessionid=args.jsessionid, cul_rid=cul_rid)
        detail_payload = parse_detail_payload(detail_html)
        row = merge_detail_into_row(row, detail_payload)
        return "ok", row, ""
    except Exception as exc:
        if args.strict:
            return "error", None, f"详情抓取失败 culRid={cul_rid}: {exc}"
        return "detail_failed", row, f"详情抓取失败 culRid={cul_rid}: {exc}"



def fetch_all_rows(client: SipuClient) -> List[dict]:
    all_rows: List[dict] = []
    page = 1
    total = None

    while True:
        if client.cfg.max_pages is not None and page > client.cfg.max_pages:
            break

        rows, total_count = client.fetch_page(page)
        if total is None:
            total = total_count

        if not rows:
            break

        all_rows.extend(rows)
        print(f"[fetch] page={page}, fetched={len(rows)}, accumulated={len(all_rows)}, total={total_count}")

        if total_count > 0 and len(all_rows) >= total_count:
            break
        page += 1

    return all_rows



def write_csv(path: Path, rows: Iterable[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抓取四普不可移动文物并导出本系统基础数据 CSV")
    parser.add_argument("--base-url", default="http://202.41.243.152:9046", help="四普系统基础地址")
    parser.add_argument("--endpoint", default="/immovableListController.do?queryRelicList", help="查询接口路径")
    parser.add_argument("--detail-endpoint", default="/tBBdataBasicController.do?goBasicView", help="基本信息详情页接口路径")
    parser.add_argument("--jsessionid", required=True, help="登录后的 JSESSIONID")
    parser.add_argument("--user-county", default="650421", help="区县代码，如 650421")
    parser.add_argument("--page-size", type=int, default=100, help="每页条数")
    parser.add_argument("--timeout", type=int, default=25, help="请求超时秒数")
    parser.add_argument("--max-pages", type=int, default=None, help="最多抓取页数（调试用）")
    parser.add_argument("--sort-field", default="update_date", help="排序字段")
    parser.add_argument("--sort-type", default="desc", choices=["asc", "desc"], help="排序方向")
    parser.add_argument("--back-status", default="0", help="backStatus 参数")
    parser.add_argument("--output", default="data/sipu_base_data.csv", help="输出 CSV 路径")
    parser.add_argument("--skip-detail", action="store_true", help="仅使用列表数据，不抓取详情页")
    parser.add_argument("--workers", type=int, default=8, help="并发线程数（用于详情抓取与转换）")
    parser.add_argument("--strict", action="store_true", help="严格模式：遇到坏数据直接失败")
    return parser.parse_args()



def main() -> int:
    args = parse_args()

    cfg = FetchConfig(
        base_url=args.base_url,
        endpoint=args.endpoint,
        detail_endpoint=args.detail_endpoint,
        jsessionid=args.jsessionid,
        user_county=args.user_county,
        page_size=args.page_size,
        timeout=args.timeout,
        max_pages=args.max_pages,
        sort_field=args.sort_field,
        sort_type=args.sort_type,
        back_status=args.back_status,
    )

    client = SipuClient(cfg)

    try:
        source_rows = fetch_all_rows(client)
    except requests.RequestException as exc:
        print(f"[error] 网络请求失败: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"[error] 抓取失败: {exc}", file=sys.stderr)
        return 3

    converted: List[Dict[str, str]] = []
    skipped = 0
    detail_failed = 0

    progress = ProgressBar(total=len(source_rows))

    if args.workers <= 1:
        for item in source_rows:
            status, row, message = build_row_for_item(item=item, cfg=cfg, args=args)
            if status == "skipped":
                skipped += 1
                if args.strict:
                    print(f"\n[error] 严格模式下发现无法转换记录: {item}", file=sys.stderr)
                    return 4
            elif status == "error":
                print(f"\n[error] {message}", file=sys.stderr)
                return 5
            else:
                if status == "detail_failed":
                    detail_failed += 1
                    print(f"\n[warn] {message}", file=sys.stderr)
                if row is not None:
                    converted.append(row)
            progress.update()
    else:
        indexed_rows: Dict[int, Dict[str, str]] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(args.workers, 1)) as executor:
            future_map = {
                executor.submit(build_row_for_item, item, cfg, args): idx
                for idx, item in enumerate(source_rows)
            }

            for future in concurrent.futures.as_completed(future_map):
                idx = future_map[future]
                try:
                    status, row, message = future.result()
                except Exception as exc:
                    status, row, message = "error", None, f"并发任务异常: {exc}"

                if status == "skipped":
                    skipped += 1
                elif status == "error":
                    if args.strict:
                        print(f"\n[error] {message}", file=sys.stderr)
                        executor.shutdown(wait=False, cancel_futures=True)
                        return 5
                    detail_failed += 1
                    print(f"\n[warn] {message}", file=sys.stderr)
                else:
                    if status == "detail_failed":
                        detail_failed += 1
                        print(f"\n[warn] {message}", file=sys.stderr)
                    if row is not None:
                        indexed_rows[idx] = row

                progress.update()

        for idx in sorted(indexed_rows.keys()):
            converted.append(indexed_rows[idx])

    output_path = Path(args.output)
    write_csv(output_path, converted)

    print("[done] 转换完成")
    print(f"[done] 来源记录: {len(source_rows)}")
    print(f"[done] 成功写入: {len(converted)}")
    print(f"[done] 跳过记录: {skipped}")
    print(f"[done] 详情失败: {detail_failed}")
    print(f"[done] 输出文件: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
