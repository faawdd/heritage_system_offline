from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0016_alter_heritagesite_category'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='ImmovableHeritage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('survey_code', models.CharField(help_text='第四次全国文物普查统一编号，格式示例：650000-0001', max_length=50, unique=True, verbose_name='普查编号')),
                ('previous_survey_code', models.CharField(blank=True, default='', help_text='第三次全国文物普查登记编号，新发现文物可留空', max_length=50, verbose_name='原三普编号')),
                ('name', models.CharField(help_text='文物点标准名称，与登记表一致', max_length=200, verbose_name='文物名称')),
                ('former_name', models.CharField(blank=True, default='', help_text='曾使用过的其他名称，多个名称用顿号分隔', max_length=200, verbose_name='曾用名/别名')),
                ('era', models.CharField(help_text='文物所属历史时代，如"汉""唐宋""近现代"，可填年代范围', max_length=100, verbose_name='时代')),
                ('category', models.CharField(choices=[('GWZ', '古文化遗址'), ('GMZ', '古墓葬'), ('GJZ', '古建筑'), ('SKT', '石窟寺及石刻'), ('JDJW', '近现代重要史迹及代表性建筑'), ('QT', '其他')], help_text='按第四次全国文物普查六大类划分', max_length=10, verbose_name='文物类别')),
                ('heritage_type', models.CharField(blank=True, choices=[('聚落址', '聚落址'), ('城址', '城址'), ('宫殿衙署址', '宫殿衙署址'), ('宗教祭祀址', '宗教祭祀址'), ('烽燧', '烽燧'), ('长城', '长城'), ('驿道', '驿道'), ('水工设施', '水工设施'), ('窑址', '窑址'), ('矿冶遗址', '矿冶遗址'), ('手工业作坊址', '手工业作坊址'), ('岩画', '岩画'), ('古战场', '古战场'), ('其他古遗址', '其他古遗址'), ('帝王陵寝', '帝王陵寝'), ('贵族墓葬', '贵族墓葬'), ('普通墓葬', '普通墓葬'), ('墓地/墓群', '墓地/墓群'), ('城垣城楼', '城垣城楼'), ('宫殿府邸', '宫殿府邸'), ('坛庙祠堂', '坛庙祠堂'), ('衙署官府', '衙署官府'), ('学堂书院', '学堂书院'), ('驿站会馆', '驿站会馆'), ('民居建筑', '民居建筑'), ('宗教建筑', '宗教建筑'), ('楼阁亭塔', '楼阁亭塔'), ('桥涵码头', '桥涵码头'), ('堤坝渠堰', '堤坝渠堰'), ('池苑园林', '池苑园林'), ('其他古建筑', '其他古建筑'), ('石窟寺', '石窟寺'), ('摩崖石刻', '摩崖石刻'), ('碑刻', '碑刻'), ('石雕', '石雕'), ('岩刻图案', '岩刻图案'), ('重要历史事件及人物活动纪念地', '重要历史事件及人物活动纪念地'), ('重要历史事件发生地旧址', '重要历史事件发生地旧址'), ('名人故居旧居', '名人故居旧居'), ('工业遗产', '工业遗产'), ('金融商贸建筑', '金融商贸建筑'), ('文化教育建筑', '文化教育建筑'), ('医疗卫生建筑', '医疗卫生建筑'), ('交通道路设施', '交通道路设施'), ('水利设施', '水利设施'), ('军事设施', '军事设施'), ('典型风格建筑', '典型风格建筑'), ('其他近现代重要史迹', '其他近现代重要史迹'), ('其他', '其他')], default='', help_text='类别下的具体类型，可参照四普分类体系选填', max_length=30, verbose_name='文物类型')),
                ('province', models.CharField(help_text='所在省级行政区名称', max_length=50, verbose_name='省/自治区/直辖市')),
                ('city', models.CharField(blank=True, default='', help_text='所在地级市或自治州名称', max_length=50, verbose_name='市/州')),
                ('county', models.CharField(blank=True, default='', help_text='所在县级行政区名称', max_length=50, verbose_name='县/市/区')),
                ('township', models.CharField(blank=True, default='', help_text='所在乡镇或街道办事处名称', max_length=100, verbose_name='乡镇/街道')),
                ('village', models.CharField(blank=True, default='', help_text='所在行政村或社区名称', max_length=100, verbose_name='村/社区')),
                ('address', models.CharField(help_text='精确到门牌号或自然地标的完整地址描述', max_length=500, verbose_name='详细地址')),
                ('coordinate_system', models.CharField(choices=[('CGCS2000', '2000国家大地坐标系（CGCS2000）'), ('WGS84', 'WGS84坐标系'), ('BJ54', '北京54坐标系'), ('XA80', '西安80坐标系')], default='CGCS2000', help_text='经纬度所采用的大地坐标系，优先使用CGCS2000', max_length=20, verbose_name='坐标系')),
                ('longitude', models.DecimalField(decimal_places=8, help_text='WGS84/CGCS2000经度，范围 -180.00000000 ~ 180.00000000，精度保留8位小数', max_digits=11, verbose_name='经度（Longitude）')),
                ('latitude', models.DecimalField(decimal_places=8, help_text='WGS84/CGCS2000纬度，范围 -90.00000000 ~ 90.00000000，精度保留8位小数', max_digits=10, verbose_name='纬度（Latitude）')),
                ('altitude', models.DecimalField(blank=True, decimal_places=2, help_text='文物点主体所在位置的绝对海拔高度，单位：米', max_digits=8, null=True, verbose_name='海拔高程（米）')),
                ('area', models.DecimalField(blank=True, decimal_places=2, help_text='文物本体及其附属范围的占地总面积，单位：平方米', max_digits=14, null=True, verbose_name='占地面积（平方米）')),
                ('preservation_status', models.CharField(choices=[('好', '好'), ('较好', '较好'), ('一般', '一般'), ('较差', '较差'), ('差', '差')], help_text='文物整体保存状况评级（好 / 较好 / 一般 / 较差 / 差）', max_length=4, verbose_name='保存现状')),
                ('damage_cause', models.TextField(blank=True, default='', help_text='造成文物破坏或损毁的主要原因，如自然风化、人为破坏、自然灾害等', verbose_name='破坏原因')),
                ('threat_factors', models.TextField(blank=True, default='', help_text='当前对文物存在威胁的自然或人为因素，可多条描述', verbose_name='现存威胁因素')),
                ('is_disappeared', models.BooleanField(default=False, help_text='文物是否已灭失或不复存在（四普新增核查项）', verbose_name='是否已消失')),
                ('disappear_reason', models.TextField(blank=True, default='', help_text='文物灭失的具体原因，仅"是否已消失"为True时填写', verbose_name='消失原因')),
                ('is_relocated', models.BooleanField(default=False, help_text='文物点是否曾经或正在被整体迁移', verbose_name='是否涉及迁移')),
                ('relocation_note', models.TextField(blank=True, default='', help_text='迁移的原因、时间及迁移前后地址，仅迁移文物填写', verbose_name='迁移情况说明')),
                ('ownership', models.CharField(choices=[('state', '国有'), ('collective', '集体'), ('private', '私人'), ('other', '其他')], help_text='文物所有权归属类型（国有 / 集体 / 私人 / 其他）', max_length=20, verbose_name='权属')),
                ('ownership_detail', models.CharField(blank=True, default='', help_text='具体的所有权单位或个人名称', max_length=200, verbose_name='权属单位/人')),
                ('user_unit', models.CharField(blank=True, default='', help_text='实际使用或占用该文物的单位或个人', max_length=200, verbose_name='使用单位/使用人')),
                ('management_unit', models.CharField(blank=True, default='', help_text='承担文物日常管理责任的单位，如文物所、博物馆、村委会等', max_length=200, verbose_name='管理单位')),
                ('manager', models.CharField(blank=True, default='', help_text='具体负责文物日常管护的责任人姓名', max_length=100, verbose_name='管理责任人')),
                ('protection_level', models.CharField(choices=[('GB', '全国重点文物保护单位'), ('SB', '省（自治区、直辖市）级文物保护单位'), ('XB', '市（县）级文物保护单位'), ('DS', '尚未定级的不可移动文物')], help_text='文物保护单位级别，尚未核定的选"尚未定级的不可移动文物"', max_length=4, verbose_name='保护级别')),
                ('protection_announced_batch', models.CharField(blank=True, default='', help_text='核定公布的批次，如"第八批全国重点文物保护单位"', max_length=50, verbose_name='公布批次')),
                ('protection_announced_date', models.DateField(blank=True, help_text='文物保护单位核定公布的日期', null=True, verbose_name='公布日期')),
                ('has_marker_stele', models.BooleanField(default=False, help_text='现场是否已设立保护标志碑', verbose_name='是否有保护标志碑')),
                ('has_protection_zone_announced', models.BooleanField(default=False, help_text='是否经政府正式公布保护范围（四至范围）', verbose_name='是否已公布保护范围')),
                ('has_construction_control_zone_announced', models.BooleanField(default=False, help_text='是否经政府正式公布建设控制地带', verbose_name='是否已公布建设控制地带')),
                ('description', models.TextField(blank=True, default='', help_text='文物的历史背景、形制特征、价值与现状的综合描述，建议300字以上', verbose_name='文物简介')),
                ('remarks', models.TextField(blank=True, default='', help_text='其他需要补充说明的事项', verbose_name='备注')),
                ('collected_at', models.DateTimeField(blank=True, help_text='现场采集数据的日期与时间', null=True, verbose_name='采集时间')),
                ('reviewed_at', models.DateTimeField(blank=True, help_text='审核完成的日期与时间', null=True, verbose_name='审核时间')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='最后更新时间')),
                ('collector', models.ForeignKey(blank=True, help_text='现场数据采集人员（系统用户）', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='collected_heritages', to=settings.AUTH_USER_MODEL, verbose_name='采集人')),
                ('input_by', models.ForeignKey(blank=True, help_text='将数据录入系统的操作人员', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='inputted_heritages', to=settings.AUTH_USER_MODEL, verbose_name='录入人')),
                ('reviewer', models.ForeignKey(blank=True, help_text='对登记信息进行审核确认的人员', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='reviewed_heritages', to=settings.AUTH_USER_MODEL, verbose_name='审核人')),
            ],
            options={
                'verbose_name': '不可移动文物登记表（四普）',
                'verbose_name_plural': '不可移动文物登记表（四普）',
                'ordering': ['survey_code'],
            },
        ),
        migrations.CreateModel(
            name='HeritagePhoto',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', models.ImageField(help_text='建议上传JPG/PNG格式，分辨率不低于1920×1080，文件大小不超过10MB', upload_to='heritage_photos/%Y/%m/', verbose_name='照片文件')),
                ('photo_type', models.CharField(choices=[('overview', '全景照'), ('detail', '局部/细节照'), ('aerial', '航拍照'), ('signage', '保护标志碑照'), ('damage', '损毁情况照'), ('surroundings', '周边环境照'), ('other', '其他')], default='overview', help_text='照片拍摄内容的类型分类', max_length=20, verbose_name='照片类型')),
                ('direction', models.CharField(blank=True, choices=[('E', '朝东'), ('W', '朝西'), ('S', '朝南'), ('N', '朝北'), ('NE', '朝东北'), ('NW', '朝西北'), ('SE', '朝东南'), ('SW', '朝西南'), ('', '不详')], default='', help_text='相机朝向，用于描述拍摄角度', max_length=2, verbose_name='拍摄方向')),
                ('caption', models.CharField(blank=True, default='', help_text='对照片内容的简要文字说明', max_length=300, verbose_name='照片说明')),
                ('shot_at', models.DateTimeField(blank=True, help_text='照片的实际拍摄日期与时间（可从EXIF读取）', null=True, verbose_name='拍摄时间')),
                ('shot_longitude', models.DecimalField(blank=True, decimal_places=8, help_text='拍摄时的GPS经度，可从EXIF自动提取', max_digits=11, null=True, verbose_name='拍摄点经度')),
                ('shot_latitude', models.DecimalField(blank=True, decimal_places=8, help_text='拍摄时的GPS纬度，可从EXIF自动提取', max_digits=10, null=True, verbose_name='拍摄点纬度')),
                ('uploaded_at', models.DateTimeField(auto_now_add=True, verbose_name='上传时间')),
                ('is_cover', models.BooleanField(default=False, help_text='勾选后此照片将作为该文物点的代表图片显示', verbose_name='是否为封面图')),
                ('heritage', models.ForeignKey(help_text='照片归属的不可移动文物登记记录', on_delete=django.db.models.deletion.CASCADE, related_name='photos', to='core.immovableheritage', verbose_name='所属文物点')),
                ('uploaded_by', models.ForeignKey(blank=True, help_text='将照片上传至系统的操作人员', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='uploaded_heritage_photos', to=settings.AUTH_USER_MODEL, verbose_name='上传人')),
            ],
            options={
                'verbose_name': '文物点现场照片',
                'verbose_name_plural': '文物点现场照片',
                'ordering': ['-is_cover', '-shot_at', '-uploaded_at'],
            },
        ),
        migrations.AddIndex(
            model_name='immovableheritage',
            index=models.Index(fields=['survey_code'], name='core_immova_survey__7b071f_idx'),
        ),
        migrations.AddIndex(
            model_name='immovableheritage',
            index=models.Index(fields=['category'], name='core_immova_categor_d12a80_idx'),
        ),
        migrations.AddIndex(
            model_name='immovableheritage',
            index=models.Index(fields=['protection_level'], name='core_immova_protect_9040d5_idx'),
        ),
        migrations.AddIndex(
            model_name='immovableheritage',
            index=models.Index(fields=['province', 'city', 'county'], name='core_immova_provinc_432bf2_idx'),
        ),
        migrations.AddIndex(
            model_name='heritagephoto',
            index=models.Index(fields=['heritage', 'photo_type'], name='core_heritag_heritag_26948d_idx'),
        ),
        migrations.AddIndex(
            model_name='heritagephoto',
            index=models.Index(fields=['heritage', 'is_cover'], name='core_heritag_heritag_11b432_idx'),
        ),
    ]
