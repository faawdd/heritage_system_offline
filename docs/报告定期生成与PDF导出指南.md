# 报告定期生成与 PDF 导出

系统支持周报、月报、季度报、年报。报告数据来自文物档案、巡查登记和项目审批模块，生成后会保存 HTML 快照，历史数据不会随业务数据变化而改变。

## 页面操作

进入前端「工作台 → 报告中心」，选择周期后点击「生成」。打开报告页面后使用浏览器打印功能，目标选择「存储为 PDF」即可导出 PDF。报告已配置 A4 版式、分页、打印色彩和封面样式。

## 定期生成

系统已内置报告调度器。Django 应用进程启动后会自动检查已完成的周、月、季度和年度周期，并在后台生成尚未归档的报告；之后默认每小时检查一次。同一统计周期只会保留一份报告，多个 Web 进程同时运行也不会重复归档。

在 Django 后台的「报告生成计划」中可以关闭某个周期。未配置计划时，四种报告默认全部启用。也可以通过环境变量调整行为：

```bash
REPORT_AUTO_GENERATOR_ENABLED=true
REPORT_AUTO_GENERATOR_INTERVAL=3600
```

## 手动补生成

管理命令位于 `core/management/commands/generate_reports.py`：

```bash
source .venv/bin/activate
python manage.py generate_reports
```

不传 `--period` 时按启用的报告计划执行；如果数据库中尚未配置计划，则默认生成四种周期。也可以指定：

```bash
python manage.py generate_reports --period monthly
```

通常无需额外配置 cron。若部署环境会定期重启应用，或希望由独立运维任务兜底，也可以每天执行一次；命令自身会跳过已归档的统计周期：

```cron
10 8 * * * cd /srv/heritage_system && .venv/bin/python manage.py generate_reports >> logs/report_generation.log 2>&1
```

报告计划和历史报告可在 Django 后台的「报告生成计划」「业务分析报告」中查看和管理。
