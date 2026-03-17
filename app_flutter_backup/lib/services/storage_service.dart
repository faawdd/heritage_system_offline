import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';
import '../models/index.dart';

/// 本地存储服务类
class StorageService {
  static Database? _database;
  static const String dbName = 'heritage_patrol.db';

  /// 获取数据库实例
  Future<Database> get database async {
    if (_database != null) return _database!;
    _database = await _initDatabase();
    return _database!;
  }

  /// 初始化数据库
  Future<Database> _initDatabase() async {
    final dbPath = await getDatabasesPath();
    final path = join(dbPath, dbName);

    return openDatabase(
      path,
      version: 1,
      onCreate: _onCreate,
    );
  }

  /// 创建数据库表
  Future<void> _onCreate(Database db, int version) async {
    // 巡查记录表
    await db.execute('''
      CREATE TABLE inspection_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        site_id INTEGER NOT NULL,
        site_name TEXT NOT NULL,
        photo_path TEXT,
        latitude REAL,
        longitude REAL,
        inspect_time TEXT NOT NULL,
        is_normal INTEGER NOT NULL,
        issue_details TEXT,
        uploaded INTEGER NOT NULL DEFAULT 0,
        server_photo_url TEXT,
        created_at TEXT NOT NULL
      )
    ''');

    // 文物点缓存表
    await db.execute('''
      CREATE TABLE heritage_cache (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        sip_code TEXT NOT NULL,
        category TEXT NOT NULL,
        level TEXT NOT NULL,
        address TEXT NOT NULL,
        longitude REAL NOT NULL,
        latitude REAL NOT NULL,
        description TEXT NOT NULL,
        manager TEXT NOT NULL,
        cached_at TEXT NOT NULL
      )
    ''');
  }

  /// 保存巡查记录到本地
  Future<int> saveInspectionRecord(InspectionRecord record) async {
    final db = await database;
    return db.insert(
      'inspection_records',
      {
        'site_id': record.siteId,
        'site_name': record.siteName,
        'photo_path': record.photoPath,
        'latitude': record.latitude,
        'longitude': record.longitude,
        'inspect_time': record.inspectTime.toIso8601String(),
        'is_normal': record.isNormal ? 1 : 0,
        'issue_details': record.issueDetails,
        'uploaded': record.uploadedToServer ? 1 : 0,
        'server_photo_url': record.serverPhotoUrl,
        'created_at': DateTime.now().toIso8601String(),
      },
    );
  }

  /// 获取所有未上传的巡查记录
  Future<List<InspectionRecord>> getUnuploadedRecords() async {
    final db = await database;
    final records = await db.query(
      'inspection_records',
      where: 'uploaded = 0',
    );

    return records
        .map((record) => InspectionRecord(
              id: record['id'] as int,
              siteId: record['site_id'] as int,
              siteName: record['site_name'] as String,
              photoPath: record['photo_path'] as String?,
              latitude: record['latitude'] as double?,
              longitude: record['longitude'] as double?,
              inspectTime: DateTime.parse(record['inspect_time'] as String),
              isNormal: (record['is_normal'] as int) == 1,
              issueDetails: record['issue_details'] as String?,
              uploadedToServer: (record['uploaded'] as int) == 1,
              serverPhotoUrl: record['server_photo_url'] as String?,
            ))
        .toList();
  }

  /// 获取所有巡查记录
  Future<List<InspectionRecord>> getAllRecords() async {
    final db = await database;
    final records = await db.query('inspection_records');

    return records
        .map((record) => InspectionRecord(
              id: record['id'] as int,
              siteId: record['site_id'] as int,
              siteName: record['site_name'] as String,
              photoPath: record['photo_path'] as String?,
              latitude: record['latitude'] as double?,
              longitude: record['longitude'] as double?,
              inspectTime: DateTime.parse(record['inspect_time'] as String),
              isNormal: (record['is_normal'] as int) == 1,
              issueDetails: record['issue_details'] as String?,
              uploadedToServer: (record['uploaded'] as int) == 1,
              serverPhotoUrl: record['server_photo_url'] as String?,
            ))
        .toList();
  }

  /// 标记巡查记录为已上传
  Future<void> markRecordAsUploaded(int recordId, String? serverPhotoUrl) async {
    final db = await database;
    await db.update(
      'inspection_records',
      {
        'uploaded': 1,
        'server_photo_url': serverPhotoUrl,
      },
      where: 'id = ?',
      whereArgs: [recordId],
    );
  }

  /// 删除巡查记录
  Future<void> deleteRecord(int recordId) async {
    final db = await database;
    await db.delete(
      'inspection_records',
      where: 'id = ?',
      whereArgs: [recordId],
    );
  }

  /// 缓存文物点信息
  Future<void> cacheHeritages(List<HeritageSite> heritages) async {
    final db = await database;
    for (final heritage in heritages) {
      await db.insert(
        'heritage_cache',
        {
          'id': heritage.id,
          'name': heritage.name,
          'sip_code': heritage.sipCode,
          'category': heritage.category,
          'level': heritage.level,
          'address': heritage.address,
          'longitude': heritage.longitude,
          'latitude': heritage.latitude,
          'description': heritage.description,
          'manager': heritage.manager,
          'cached_at': DateTime.now().toIso8601String(),
        },
        conflictAlgorithm: ConflictAlgorithm.replace,
      );
    }
  }

  /// 获取缓存的文物点
  Future<List<HeritageSite>> getCachedHeritages() async {
    final db = await database;
    final records = await db.query('heritage_cache');

    return records
        .map((record) => HeritageSite(
              id: record['id'] as int,
              name: record['name'] as String,
              sipCode: record['sip_code'] as String,
              category: record['category'] as String,
              level: record['level'] as String,
              address: record['address'] as String,
              longitude: record['longitude'] as double,
              latitude: record['latitude'] as double,
              description: record['description'] as String,
              manager: record['manager'] as String,
            ))
        .toList();
  }

  /// 清空文物点缓存
  Future<void> clearHeritageCache() async {
    final db = await database;
    await db.delete('heritage_cache');
  }

  /// 关闭数据库
  Future<void> close() async {
    if (_database != null) {
      await _database!.close();
      _database = null;
    }
  }
}
